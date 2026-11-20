import pytest

from misp_ioc_scoring.sharing.domain.pihole_hostname import hostname
from misp_ioc_scoring.sharing.domain.pihole_policy import eligible
from misp_ioc_scoring.sharing.application.sync_pihole import reconcile


@pytest.mark.parametrize("kind,value,expected", [
    ("url", "https://Sub.Example.org:8443/path?token=x", "sub.example.org"),
    ("domain", "exämple.org.", "xn--exmple-cua.org"),
    ("url", "https://127.0.0.1/path", None),
    ("url", "https://[bad", None),
    ("link", "https://example.org", None),
])
def test_dns_hostname(kind, value, expected):
    assert hostname(kind, value) == expected


def test_score_cutoff():
    assert eligible("default", block=True)
    assert eligible("carioca", block=False, score=50, cutoff=50)
    assert not eligible("carioca", block=True, score=49, cutoff=50)
    assert not eligible("default", block=True, trusted=False)


class FakePiHole:
    def __init__(self):
        self.rows = {"manual.example": {"id": 1, "comment": "manual"}}
        self.timeout = True

    def lookup(self, host):
        return self.rows.get(host)

    def add(self, host, marker):
        self.rows[host] = {"id": 2, "comment": marker, "groups": [0], "enabled": True}
        if self.timeout:
            self.timeout = False
            raise TimeoutError

    def remove(self, host):
        del self.rows[host]


class MemoryStore:
    def __init__(self):
        self.rows = {}

    def entries(self):
        return self.rows.copy()

    def save(self, host, marker, remote_id, status, evidence):
        self.rows[host] = dict(marker=marker, remote_id=remote_id, status=status, evidence=evidence)

    def attempt(self, host, operation, status):
        pass


def test_reconcile_timeout_and_preserve_unavailable_source_and_manual_entries():
    client, store = FakePiHole(), MemoryStore()
    host = "managed.example"
    source = {"source": "peer-A"}
    desired = {host: [source], "manual.example": [source]}
    reconcile(client, store, desired, set())
    assert store.rows[host]["status"] == "pending"
    reconcile(client, store, desired, set())
    assert store.rows[host]["status"] == "confirmed"
    reconcile(client, store, {}, {"peer-A"})
    assert host in client.rows
    reconcile(client, store, {}, set())
    assert client.rows == {"manual.example": {"id": 1, "comment": "manual"}}


def test_remote_marker_change_prevents_removal():
    client, store = FakePiHole(), MemoryStore()
    client.timeout = False
    host = "managed.example"
    reconcile(client, store, {host: [{"source": "peer-A"}]}, set())
    client.rows[host]["comment"] = "manual change"
    reconcile(client, store, {}, set())
    assert host in client.rows
    assert store.rows[host]["status"] == "unverified"
