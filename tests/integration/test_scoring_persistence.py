from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from misp_ioc_scoring.entrypoints.scoring_sharing import run_carioca_scoring
from misp_ioc_scoring.scoring.api import current_carioca_run
from misp_ioc_scoring.scoring.infrastructure.persistence.carioca import CariocaRunner
from misp_ioc_scoring.shared.database import transaction
from tests.support.carioca import configuration
from tests.support.collected import collect, observation


@pytest.fixture
def scored(engine):
    now = datetime.now(timezone.utc)
    collect(engine, [observation('a', 'a.example', as_of=now, org='A', event='e1'),
                     observation('b', 'b.example', as_of=now, org='B', event='e2', sa='2'),
                     observation('b2', 'b.example', as_of=now, org='A', event='e1', source='test'),
                     observation('u', 'https://u.example/', 'url', as_of=now)], now)
    yield engine
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE scoring.execucao_scoring, scoring.configuracao_carioca CASCADE'))


def test_run_is_persisted_with_statistics_and_unique_rows(scored):
    summary = run_carioca_scoring(scored, configuration())
    with scored.connect() as connection:
        run = connection.execute(text('SELECT * FROM scoring.execucao_scoring')).mappings().one()
        assert (run['status'], run['valid_population'], run['excluded'], run['observations_evaluated']) == (
            'completed', 2, 1, 3)
        assert connection.scalar(text('SELECT count(*) FROM scoring.avaliacao_observacao')) == 3
        assert connection.scalar(text('SELECT count(*) FROM scoring.resultado_score')) == 2
        assert connection.execute(text('SELECT reason FROM scoring.exclusao_score')).scalar_one() == (
            'type_without_decay_group')
        stats = connection.execute(text('SELECT * FROM scoring.estatisticas_populacao')).mappings().one()
        assert len(stats['sigma_by_category']) == 16 and len(stats['organizations']) == 2
    assert summary.valid_population == 2
    run_carioca_scoring(scored, configuration())
    with scored.connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM scoring.configuracao_carioca')) == 1
        assert connection.scalar(text('SELECT count(DISTINCT scoring_run_id) FROM scoring.resultado_score')) == 2


def test_failed_run_does_not_replace_current_and_lock_prevents_overlap(scored):
    run_carioca_scoring(scored, configuration())
    with transaction(scored) as session:
        current = current_carioca_run(session)
    run_id = uuid4()
    with pytest.raises(RuntimeError):
        with CariocaRunner(scored, lambda: run_id) as store:
            raise RuntimeError('boom')
    with transaction(scored) as session:
        assert current_carioca_run(session) == current
        assert session.scalar(text("SELECT status FROM scoring.execucao_scoring WHERE id=:id"), {'id': run_id}) == 'failed'
    with transaction(scored) as session:
        session.execute(text('SELECT pg_advisory_xact_lock(874204)'))
        assert run_carioca_scoring(scored, configuration()) is None


def test_collector_cannot_write_scoring(scored):
    collector = create_engine(scored.url.set(username='collector'))
    try:
        with pytest.raises(DBAPIError), collector.begin() as connection:
            connection.execute(text("INSERT INTO scoring.exclusao_score VALUES (gen_random_uuid(), gen_random_uuid(), 'expired')"))
    finally:
        collector.dispose()
