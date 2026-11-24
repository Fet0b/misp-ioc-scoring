"""Fakes for MISP sharing tests."""
from dataclasses import replace
from datetime import timedelta

from misp_ioc_scoring.scoring.domain.carioca_results import CariocaRun, CariocaScore
from misp_ioc_scoring.sharing.domain.sharing import PeerPolicy
from misp_ioc_scoring.sharing.infrastructure.peer_configuration import LocalInstance, SharingPolicy
from tests.support.carioca import AS_OF, uid

PEER = PeerPolicy('peer-a', 'https://peer-a.example', 'env:PEER_A', 50, '3')


def run(name='run', age_hours=1):
    return CariocaRun(uid(name), AS_OF, AS_OF - timedelta(hours=age_hours), 'v', 'hash', 10, ())


def score(name, priority=80, rank=1, in_top_n=True, kind='domain'):
    return CariocaScore(uid('ioc:' + name), kind, name, priority, rank, in_top_n, 1, AS_OF, 's1', uid('attr:' + name))


def policy(*peers, attempts=3, backoff=10):
    return SharingPolicy(LocalInstance('https://local.example', 'env:LOCAL'), peers or (PEER,), 60, attempts, backoff)


class Reader:
    def __init__(self, current, scores, observations, warninglists=None):
        self.current, self.scores, self.obs, self.lists = current, scores, observations, warninglists or {}

    def current_carioca_run(self):
        return self.current

    def carioca_scores(self, run_id):
        return list(self.scores)

    def observations(self, ioc_ids):
        return {ioc: self.obs[ioc] for ioc in ioc_ids if ioc in self.obs}

    def warninglists(self):
        return self.lists


class MemoryStore:
    policy_hash = 'policy'

    def __init__(self):
        self.rows, self.suspended = {}, None

    def suspend(self, reason, at):
        self.suspended = reason

    def resume(self):
        self.suspended = None

    def attempts(self, peer_id):
        return {ioc: a for (peer, ioc), a in self.rows.items() if peer == peer_id}

    def save(self, attempt):
        self.rows[(attempt.peer_id, attempt.ioc_id)] = attempt

    def state(self, name, peer='peer-a'):
        return self.rows[(peer, uid('ioc:' + name))]


class FakeSync:
    """In-memory MISP: local outbound events and what each peer has received."""

    def __init__(self, groups=None):
        self.groups = groups or {}
        self.local, self.peer_has, self.calls = {}, set(), []
        self.fail_publish = self.fail_confirm = False
        self.deliver = True

    def sharing_group_members(self):
        return self.groups

    def peer_groups(self, peer, members):
        return {gid for gid, (_, servers) in members.items() if peer.base_url in servers}

    def ensure_event(self, peer, members):
        self.calls.append('ensure')

    def upsert(self, peer, attempt, score):
        self.calls.append(('upsert', score.normalized_value, attempt.outbound_distribution))
        self.local[attempt.outbound_attribute_uuid] = (score.normalized_value, attempt.outbound_distribution)

    def remove(self, peer, attribute_uuid):
        self.calls.append(('remove', attribute_uuid))
        self.local.pop(attribute_uuid, None)
        self.peer_has.discard(attribute_uuid)

    def publish(self, peer):
        self.calls.append('publish')
        if self.fail_publish:
            raise TimeoutError
        if self.deliver:
            self.peer_has.update(self.local)

    def confirmed(self, peer, attribute_uuid):
        if self.fail_confirm:
            raise TimeoutError
        return attribute_uuid in self.peer_has
