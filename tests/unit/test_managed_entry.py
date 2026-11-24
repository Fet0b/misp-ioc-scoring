import pytest

from misp_ioc_scoring.sharing.domain.pihole_entries import ManagedEntry, RemoteEntry

ENTRY = ManagedEntry('host.example', 'misp-ioc-scoring:abc', 7)


@pytest.mark.parametrize('remote,owned', [
    (RemoteEntry(7, 'misp-ioc-scoring:abc', (0,), True), True),
    (RemoteEntry(7, 'manual', (0,), True), False),
    (RemoteEntry('7', 'misp-ioc-scoring:abc', (0,), True), False),
    (RemoteEntry(True, 'misp-ioc-scoring:abc', (0,), True), False),
    (RemoteEntry(8, 'misp-ioc-scoring:abc', (0,), True), False),
    (RemoteEntry(7, 'misp-ioc-scoring:abc', (0, 3), True), False),
    (RemoteEntry(7, 'misp-ioc-scoring:abc', None, True), False),
    (RemoteEntry(7, 'misp-ioc-scoring:abc', (0,), False), False),
    (None, False),
])
def test_ownership(remote, owned):
    assert ENTRY.is_owned_by(remote) is owned


def test_unknown_remote_id_accepts_any_integer_and_payload_translation():
    entry = ManagedEntry('host.example', 'm')
    assert entry.is_owned_by(RemoteEntry(99, 'm', (0,), True))
    assert RemoteEntry.from_payload({'id': 1, 'comment': 'm', 'groups': [0], 'enabled': True}) == RemoteEntry(1, 'm', (0,), True)
    assert RemoteEntry.from_payload({'id': 1}).groups is None
