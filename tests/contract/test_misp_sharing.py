"""MISP sharing contract with simulated MISP responses (adapter + use case)."""
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from misp_ioc_scoring.shared.errors import OperationalError
from misp_ioc_scoring.sharing.adapters.synchronization import MispSynchronization
from misp_ioc_scoring.sharing.application.share_eligible import share_eligible
from misp_ioc_scoring.sharing.domain.sharing import AttemptState as S, PeerPolicy
from tests.support.carioca import AS_OF, observation, uid
from tests.support.sharing import MemoryStore, Reader, policy, run, score

MAX_AGE = timedelta(hours=48)
PEER = PeerPolicy('peer-a', 'https://peer-a.example', 'env:PEER_A', 50, '3')


class LocalMisp:
    """Simulated local MISP: events, attributes, sharing groups and publish."""

    def __init__(self, peer):
        self.events, self.attributes, self.calls, self.peer = {}, {}, [], peer
        self.timeout_on_publish = False

    def call(self, operation, **kwargs):
        self.calls.append(operation)
        if operation == 'sharing_groups':
            return [{'SharingGroup': {'id': 7, 'uuid': 'sg-uuid-7'},
                     'SharingGroupServer': [{'Server': {'url': 'https://peer-a.example/'}}]}]
        if operation == 'event_exists':
            return kwargs['event'] in self.events
        if operation == 'add_event':
            self.events[kwargs['event']['uuid']] = kwargs['event']
            return {'Event': kwargs['event']}
        if operation == 'attribute_exists':
            return kwargs['attribute'] in self.attributes and not self.attributes[kwargs['attribute']].get('deleted')
        if operation in ('add_attribute', 'update_attribute'):
            self.attributes[kwargs['attribute']['uuid']] = dict(kwargs['attribute'])
            return {}
        if operation == 'delete_attribute':
            self.attributes[kwargs['attribute']]['deleted'] = True
            return {}
        if operation == 'publish':
            if self.timeout_on_publish:
                raise OperationalError('misp_request_failed')
            self.peer.receive({u: a for u, a in self.attributes.items() if not a.get('deleted')})
            return {'message': 'Job queued'}
        raise AssertionError(operation)


class PeerMisp:
    def __init__(self):
        self.received, self.accept = {}, None
        self.unreachable = False

    def receive(self, attributes):
        accepted = attributes if self.accept is None else {u: a for u, a in attributes.items() if self.accept(a)}
        self.received = accepted

    def call(self, operation, **kwargs):
        if self.unreachable:
            raise OperationalError('misp_request_failed')
        assert operation == 'attribute_exists'
        return kwargs['attribute'] in self.received


def setup():
    peer = PeerMisp()
    local = LocalMisp(peer)
    return local, peer, MispSynchronization(local, lambda p: peer)


def obs(name, distribution, sg=None):
    return observation(name, distribution=distribution, event_distribution='3', sharing_group_id=sg)


def reader(observations, scores=None):
    return Reader(run(), scores or [score('a.example', 80)], {uid('ioc:a.example'): observations})


def rounds(n, read, sync, store, **kwargs):
    for _ in range(n):
        share_eligible(AS_OF, read, sync, store, policy(PEER, **kwargs), max_age=MAX_AGE)


def test_idempotent_outbound_event_and_deterministic_attribute():
    local, peer, sync = setup()
    store = MemoryStore()
    rounds(2, reader((obs('a', '2'),)), sync, store)
    expected = uuid5(NAMESPACE_URL, f'misp-ioc-scoring:outbound-attribute:peer-a:{uid("ioc:a.example")}')
    assert list(local.events) == [str(PEER.outbound_event_uuid)] and local.calls.count('add_event') == 1
    assert list(local.attributes) == [str(expected)]
    attribute = local.attributes[str(expected)]
    assert attribute['to_ids'] is True and attribute['distribution'] == '2' and attribute['value'] == 'a.example'
    assert local.events[str(PEER.outbound_event_uuid)]['distribution'] == '3'


def test_sharing_group_distribution_is_kept_never_wider():
    local, peer, sync = setup()
    store = MemoryStore()
    rounds(1, reader((obs('a', '4', sg='7'), obs('b', '3'))), sync, store)
    attempt = store.state('a.example')
    assert (attempt.outbound_distribution, attempt.outbound_sharing_group_uuid) == ('4', 'sg-uuid-7')
    assert local.attributes[str(attempt.outbound_attribute_uuid)]['sharing_group_id'] == '7'


def test_requested_then_confirmed_only_after_reading_peer():
    local, peer, sync = setup()
    store = MemoryStore()
    rounds(1, reader((obs('a', '3'),)), sync, store)
    assert store.state('a.example').state == S.REQUESTED
    rounds(1, reader((obs('a', '3'),)), sync, store)
    assert store.state('a.example').state == S.CONFIRMED


def test_timeout_becomes_ambiguous_and_is_reconciled_by_reading_first():
    local, peer, sync = setup()
    local.timeout_on_publish = True
    store = MemoryStore()
    rounds(1, reader((obs('a', '3'),)), sync, store)
    assert store.state('a.example').state == S.AMBIGUOUS
    local.timeout_on_publish = False
    peer.received = {str(store.state('a.example').outbound_attribute_uuid): {}}  # it did arrive
    publishes = local.calls.count('publish')
    rounds(1, reader((obs('a', '3'),)), sync, store)
    assert store.state('a.example').state == S.CONFIRMED
    assert local.calls.count('publish') == publishes


def test_partial_acceptance_confirms_only_accepted_items():
    local, peer, sync = setup()
    peer.accept = lambda attribute: attribute['value'] == 'a.example'
    store = MemoryStore()
    scores = [score('a.example', 80), score('b.example', 70, rank=2)]
    read = Reader(run(), scores, {uid('ioc:a.example'): (obs('a', '3'),), uid('ioc:b.example'): (obs('b', '3'),)})
    rounds(2, read, sync, store)
    assert store.state('a.example').state == S.CONFIRMED
    assert store.state('b.example').state == S.REQUESTED


def test_lower_distribution_updates_and_ineligible_is_soft_deleted_before_publish():
    local, peer, sync = setup()
    store = MemoryStore()
    rounds(2, reader((obs('a', '3'),)), sync, store)
    uuid = str(store.state('a.example').outbound_attribute_uuid)
    rounds(1, reader((obs('a', '1'),)), sync, store)
    assert local.attributes[uuid]['distribution'] == '1'
    local.calls.clear()
    rounds(1, reader((obs('a', '0'),)), sync, store)
    assert local.attributes[uuid]['deleted'] is True
    assert local.calls.index('delete_attribute') < local.calls.index('publish')
    assert store.state('a.example').state == S.INELIGIBLE
    assert store.state('a.example').reason == 'distribution_not_allowed'


def test_limited_retries_end_as_failed():
    local, peer, sync = setup()
    local.timeout_on_publish = True
    peer.unreachable = True
    store = MemoryStore()
    later = AS_OF
    for _ in range(4):
        share_eligible(later, reader((obs('a', '3'),)), sync, store, policy(PEER, attempts=2, backoff=1),
                       max_age=MAX_AGE + timedelta(hours=1))
        later += timedelta(minutes=5)
    assert store.state('a.example').state == S.FAILED
