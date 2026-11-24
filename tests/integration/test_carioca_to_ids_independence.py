"""CARIOCA results for to_ids=true IOCs do not depend on MISP_TO_IDS_ONLY."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from misp_ioc_scoring.scoring.application.score_population import calculate
from misp_ioc_scoring.collection.api import collection_snapshot
from misp_ioc_scoring.shared.database import transaction
from tests.support.carioca import configuration
from tests.support.collected import collect, observation


def scores(engine, as_of):
    with transaction(engine) as session:
        _, _, results, exclusions, _ = calculate(as_of, collection_snapshot(session), configuration())
    actionable = {r.ioc_id: (r.priority_score, r.rank, r.in_top_n) for r in results}
    return actionable, dict(exclusions)


def test_scores_identical_with_and_without_context_attributes(engine):
    as_of = datetime.now(timezone.utc)
    actionable = [observation('a', 'a.example', as_of=as_of, org='A', event='e1'),
                  observation('b', 'b.example', as_of=as_of, org='B', event='e2', sa='2'),
                  observation('c', 'c.example', as_of=as_of, org='B', event='e1', age_days=100)]
    context = [observation('x', 'x.example', as_of=as_of, org='C', event='e1', to_ids=False),
               observation('y', 'a.example', as_of=as_of, org='C', event='e3', to_ids=False, created_days=90),
               observation('z', 'z.example', as_of=as_of, org='B', event='e2', to_ids=False,
                           category='Payload delivery')]
    collect(engine, actionable, as_of)
    only_to_ids, only_exclusions = scores(engine, as_of)
    with engine.begin() as connection:
        connection.execute(text('UPDATE collection.endpoint_coleta SET to_ids_only=false'))
    collect(engine, actionable + context, as_of + timedelta(seconds=1))
    everything, all_exclusions = scores(engine, as_of)
    assert everything == only_to_ids
    assert {k: v for k, v in all_exclusions.items() if k in only_exclusions} == only_exclusions
    assert set(all_exclusions.values()) <= {'not_to_ids'}
