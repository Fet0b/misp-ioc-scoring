from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.entrypoints.scoring_sharing import run_carioca_scoring
from misp_ioc_scoring.scoring.infrastructure.persistence.candidates import SqlCandidateStore
from misp_ioc_scoring.scoring.infrastructure.persistence.carioca import CariocaRunner
from tests.support.carioca import configuration
from tests.support.collected import observation


@pytest.fixture
def collected(engine):
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE scoring.candidato_rescoring'))
    now = datetime.now(timezone.utc)
    items = [observation('a', 'a.example', as_of=now), observation('b', 'b.example', as_of=now, org='B')]
    repository = ObservationsRepository(engine, 'test')
    repository.apply(items, {o.attribute_uuid for o in items}, [], now)
    yield engine, repository, items, now
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE scoring.execucao_scoring, scoring.configuracao_carioca CASCADE'))
        connection.execute(text('TRUNCATE scoring.candidato_rescoring'))


def rows(engine):
    with engine.connect() as connection:
        return {r.ioc_id: r for r in connection.execute(text('SELECT * FROM scoring.candidato_rescoring'))}


def test_upsert_and_scoring_does_not_remark(collected):
    engine, repository, items, now = collected
    run_carioca_scoring(engine, configuration())
    first = rows(engine)
    assert len(first) == 2 and not any(r.pending for r in first.values())
    assert {r.scored_revision for r in first.values()} == {1}
    run_carioca_scoring(engine, configuration())
    assert {k: (r.pending, r.marked_at) for k, r in rows(engine).items()} == {
        k: (r.pending, r.marked_at) for k, r in first.items()}
    repository.apply([replace(items[0], event_analysis='2'), items[1]],
                     {o.attribute_uuid for o in items}, [], now + timedelta(seconds=1))
    run_carioca_scoring(engine, configuration())
    after = rows(engine)
    assert sorted(r.scored_revision for r in after.values()) == [1, 2]
    assert not any(r.pending for r in after.values())


def test_revision_change_during_calculation_keeps_pending(collected, monkeypatch):
    engine, repository, items, now = collected
    original = SqlCandidateStore.current_revisions

    def changed(self, ioc_ids):
        return {ioc: revision + 1 for ioc, revision in original(self, ioc_ids).items()}

    monkeypatch.setattr(SqlCandidateStore, 'current_revisions', changed)
    run_carioca_scoring(engine, configuration())
    assert all(r.pending and r.last_error == 'input_changed_during_scoring' for r in rows(engine).values())


def test_scoring_failure_keeps_pending(collected):
    engine, repository, items, now = collected
    run_carioca_scoring(engine, configuration())
    repository.apply([replace(items[0], event_analysis='2'), items[1]],
                     {o.attribute_uuid for o in items}, [], now + timedelta(seconds=1))
    with engine.begin() as connection:
        connection.execute(text("UPDATE scoring.candidato_rescoring SET pending = true"))
    with pytest.raises(RuntimeError):
        with CariocaRunner(engine) as store:
            raise RuntimeError('boom')
    assert all(r.pending and r.last_error == 'carioca_run_failed' for r in rows(engine).values())
