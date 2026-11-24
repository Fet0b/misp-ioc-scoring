from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from misp_ioc_scoring.entrypoints.scoring_sharing import run_carioca_scoring
from misp_ioc_scoring.scoring import api
from misp_ioc_scoring.shared.database import transaction
from tests.support.carioca import configuration
from tests.support.collected import collect, observation, uid


@pytest.fixture
def scored(engine):
    now = datetime.now(timezone.utc)
    collect(engine, [observation(f'o{n}', f'host{n}.example', as_of=now, org='AB'[n % 2], event=f'e{n % 3}',
                                 age_days=5 + 30 * n, sa=str(n % 3)) for n in range(6)]
            + [observation('old', 'old.example', as_of=now, age_days=500)], now)
    summary = run_carioca_scoring(engine, configuration(top_n=3))
    yield engine, summary
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE scoring.execucao_scoring, scoring.configuracao_carioca CASCADE'))


def test_current_run_ignores_failed_and_running(scored):
    engine, summary = scored
    with transaction(engine) as session:
        session.execute(text("""INSERT INTO scoring.execucao_scoring (id, as_of, finished_at, status, warnings)
            VALUES (gen_random_uuid(), now(), now() + interval '1 hour', 'failed', '[]'),
                   (gen_random_uuid(), now(), NULL, 'running', '[]')"""))
    with transaction(engine) as session:
        run = api.current_carioca_run(session)
        assert run.id == summary.run_id and run.top_n == 3 and run.configuration_version == 'test-1'


def test_scores_filter_order_and_pages(scored):
    engine, summary = scored
    with transaction(engine) as session:
        everything = list(api.carioca_scores(session, summary.run_id, page_size=2))
        assert [s.rank for s in everything] == list(range(1, 7))
        assert [s.priority_score for s in everything] == sorted((s.priority_score for s in everything), reverse=True)
        assert [s.rank for s in api.carioca_scores(session, summary.run_id, top_n_only=True)] == [1, 2, 3]
        cut = everything[2].priority_score
        assert all(s.priority_score >= cut for s in api.carioca_scores(session, summary.run_id, min_score=cut))
        assert [e.reason for e in api.exclusions(session, summary.run_id)] == ['expired']


def test_explain_winner_sigma_degenerate_and_proxy(scored):
    engine, summary = scored
    with transaction(engine) as session:
        top = next(api.carioca_scores(session, summary.run_id))
        explanation = api.explain(session, summary.run_id, top.ioc_id)
        assert explanation.winning_observation == (top.source_instance_id, top.attribute_uuid)
        assert explanation.observations_evaluated == 1 and explanation.rank == 1 and explanation.in_top_n
        assert set(explanation.sigma_by_category) == {'Network activity'}
        warnings = api.current_carioca_run(session).warnings
        assert set(explanation.minmax_degenerate) == {w.split(':')[1] for w in warnings if w.startswith('minmax')}
        assert 'orgc' in explanation.source_proxy_limitation
        assert 0 <= explanation.components["CADE' (MinMax entre eventos)"] <= 100
        excluded = api.explain(session, summary.run_id, uid('missing'))
        assert excluded is None
        old = api.exclusions(session, summary.run_id)[0]
        assert api.explain(session, summary.run_id, old.ioc_id).exclusion_reason == 'expired'
