from dataclasses import replace
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from misp_ioc_scoring.sharing.domain.sharing import AttemptState as S, ShareAttempt
from misp_ioc_scoring.sharing.infrastructure.persistence.misp import SqlSharingStore
from tests.support.carioca import uid
from tests.support.sharing import PEER, policy


@pytest.fixture
def store(engine):
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE sharing.tentativa_compartilhamento, sharing.peer_misp, '
                                'sharing.politica_compartilhamento'))
    worker = create_engine(engine.url.set(username='scoring_sharing'))
    try:
        sharing = SqlSharingStore(worker, policy(PEER))
        sharing.record_policy(datetime.now(timezone.utc))
        yield sharing
    finally:
        worker.dispose()


def attempt(state, **changes):
    base = ShareAttempt(PEER.peer_id, uid('ioc'), state, uid('run'), 'policy', PEER.outbound_attribute_uuid(uid('ioc')))
    return replace(base, **changes)


def test_policy_without_secrets_and_peer_reference(store, engine):
    with engine.connect() as connection:
        peers, = connection.execute(text('SELECT peers FROM sharing.politica_compartilhamento')).one()
        assert 'env:PEER_A' not in str(peers) and peers['peers'][0]['peer_id'] == 'peer-a'
        assert connection.execute(text('SELECT credential_secret_ref FROM sharing.peer_misp')).scalar() == 'env:PEER_A'
    store.suspend('stale_score', datetime.now(timezone.utc))
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT suspension_reason FROM sharing.politica_compartilhamento')) == 'stale_score'
    store.resume()
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT suspended_at FROM sharing.politica_compartilhamento')) is None


def test_one_current_attempt_per_peer_and_ioc(store, engine):
    for state in (S.ELIGIBLE, S.REQUESTED, S.AMBIGUOUS, S.CONFIRMED):
        store.save(attempt(state, attempts=1, last_error='x' * 300 if state == S.AMBIGUOUS else None,
                           outbound_distribution='2'))
    stored = store.attempts(PEER.peer_id)
    assert list(stored) == [uid('ioc')] and stored[uid('ioc')].state == S.CONFIRMED
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT count(*) FROM sharing.tentativa_compartilhamento')) == 1
    store.save(attempt(S.INELIGIBLE, reason='warninglist'))
    assert store.attempts(PEER.peer_id)[uid('ioc')].reason == 'warninglist'


def test_collector_cannot_write_sharing(store, engine):
    collector = create_engine(engine.url.set(username='collector'))
    try:
        with pytest.raises(DBAPIError), collector.begin() as connection:
            connection.execute(text('DELETE FROM sharing.tentativa_compartilhamento'))
    finally:
        collector.dispose()
