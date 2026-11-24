"""FR-021 / SC-010: equivalent domain data from two MISP endpoints give the same decisions."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from misp_ioc_scoring.collection.api import collection_snapshot
from misp_ioc_scoring.collection.infrastructure.persistence.models import EndpointModel
from misp_ioc_scoring.scoring.application.score_candidates import active_revisions
from misp_ioc_scoring.scoring.application.score_population import calculate
from misp_ioc_scoring.scoring.application.simple_blocking import evaluate
from misp_ioc_scoring.shared.database import transaction
from misp_ioc_scoring.sharing.domain.sharing import decide_distribution
from tests.support.carioca import configuration
from tests.support.collected import collect, observation


def outcome(engine, source, as_of):
    items = [observation('a', 'a.example', as_of=as_of, source=source, org='A', event='e1', sa='2'),
             observation('b', 'b.example', as_of=as_of, source=source, org='B', event='e2', age_days=200),
             observation('c', 'https://c.example/x', 'url', as_of=as_of, source=source, org='A', event='e1'),
             observation('d', 'd.example', as_of=as_of, source=source, org='B', event='e2', distribution='0')]
    collect(engine, items, as_of - timedelta(minutes=1), source=source)
    with transaction(engine) as session:
        snapshot = collection_snapshot(session)
    by_value = {o.ioc_id: o.normalized_value for o in snapshot.observations}
    _, _, results, exclusions, _ = calculate(as_of, snapshot, configuration())
    scores = {r.normalized_value: (round(r.priority_score, 9), r.rank, r.in_top_n) for r in results}
    excluded = {by_value[ioc]: str(reason) for ioc, reason in exclusions}
    by_attribute = {o.attribute_uuid: o.normalized_value for o in snapshot.observations}
    blocking = {by_attribute[d.attribute_uuid]: (d.block, str(d.reason))
                for d in evaluate(snapshot, as_of, timedelta(hours=48))}
    candidates = {by_value[ioc]: revision for ioc, revision in active_revisions(snapshot).items()}
    distribution = {}
    for ioc, value in by_value.items():
        decision = decide_distribution([o for o in snapshot.observations if o.ioc_id == ioc], set())
        distribution[value] = decision and decision.distribution
    return scores, excluded, blocking, candidates, distribution


def test_two_endpoints_same_results(engine):
    as_of = datetime.now(timezone.utc)
    with transaction(engine) as session:
        session.add(EndpointModel(id='other', base_url='https://other.example', credential_secret_ref='env:KEY',
                                  interval_seconds=60, to_ids_only=True, removal_ratio=.2))
    first = outcome(engine, 'test', as_of)
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE collection.observacao_origem, collection.ioc CASCADE'))
    second = outcome(engine, 'other', as_of)
    assert first == second
    assert first[0] and first[1] == {'https://c.example/x': 'type_without_decay_group'}
