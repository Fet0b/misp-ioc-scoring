
import pytest
from sqlalchemy import create_engine, text

from misp_ioc_scoring.shared.database import transaction
from misp_ioc_scoring.sharing.application.sync_pihole import reconcile
from misp_ioc_scoring.sharing.infrastructure.persistence.pihole import Store
from misp_ioc_scoring.sharing.infrastructure.scheduling.scheduler import sync


class Remote:
    def __init__(self):
        self.rows = {
            "manual.example": {"id": 100, "comment": "manual", "groups": [3]},
        }
        self.adds = []
        self.removes = []
        self.timeout_after_create = False

    def validate(self):
        pass

    def close(self):
        pass

    def lookup(self, host):
        return self.rows.get(host)

    def add(self, host, marker):
        self.adds.append(host)
        self.rows[host] = {"id": len(self.adds), "comment": marker, "groups": [0], "enabled": True}
        if self.timeout_after_create:
            self.timeout_after_create = False
            raise TimeoutError

    def remove(self, host):
        self.removes.append(host)
        del self.rows[host]


@pytest.fixture
def store(engine):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE sharing.pihole_entry, sharing.pihole_attempt, sharing.pihole_policy"))
    worker = create_engine(engine.url.set(username="scoring_sharing"))
    try:
        yield Store(worker, "https://pihole.example", 60, "env:PIHOLE_TEST_PASSWORD")
    finally:
        worker.dispose()


def test_timeout_reconciliation_and_scoped_removal(store, caplog):
    remote = Remote()
    remote.timeout_after_create = True
    a, b = {"source": "a"}, {"source": "b"}
    desired = {"owned.example": [a, b], "manual.example": [a]}
    reconcile(remote, store, desired, set())
    assert store.entries()["owned.example"]["status"] == "pending"
    reconcile(remote, store, desired, set())
    assert remote.adds == ["owned.example"]
    assert store.entries()["owned.example"]["evidence"] == [a, b]
    reconcile(remote, store, {"second.example": [b]}, set())
    assert remote.removes == ["owned.example"]
    reconcile(remote, store, {"other.example": [a]}, {"a"})
    assert remote.removes == ["owned.example", "second.example"]
    reconcile(remote, store, {}, {"a"})
    assert "other.example" in remote.rows
    remote.rows["other.example"].update(groups=[7])
    reconcile(remote, store, {}, set())
    assert store.entries()["other.example"]["status"] == "unverified"
    assert remote.rows["other.example"]["groups"] == [7]
    assert remote.rows["manual.example"]["groups"] == [3]
    assert "pihole_entry_ownership_unverified" in caplog.text
    assert "other.example" not in caplog.text
    with store.engine.connect() as connection:
        statuses = connection.scalars(text("SELECT status FROM sharing.pihole_attempt")).all()
    assert {"pending", "confirmed", "ambiguous"} <= set(statuses)


def test_sync_does_not_run_when_another_worker_holds_lock(store, monkeypatch):
    client = Remote()
    monkeypatch.setattr(client, "validate", lambda: pytest.fail("overlapping Pi-hole sync"))
    with transaction(store.engine) as session:
        session.execute(text("SELECT pg_advisory_xact_lock(874203)"))
        sync(store.engine, client, store, 48)


def test_worker_publishes_only_current_evidence_and_reconciles_after_recovery(store, engine):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from misp_ioc_scoring.collection.domain.observations import Observation
    from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
    from misp_ioc_scoring.scoring.infrastructure.persistence.simple_blocking import run

    now = datetime.now(timezone.utc)
    attribute = uuid4()
    observation = Observation(
        source_instance_id="test", event_uuid=uuid4(), attribute_uuid=attribute,
        raw_value="https://owned.example/private", misp_type="url", category="Other", to_ids=True,
        orgc_uuid=None, source_created_at=now, source_modified_at=now, collected_at=now,
        event_threat_level="2", event_analysis="2", distribution="0", event_distribution="0",
        published=False,
    )
    repository = ObservationsRepository(engine, "test")
    repository.apply([observation], {attribute}, [], now)
    remote = Remote()
    try:
        run(store.engine, 48)
        sync(store.engine, remote, store, 48)
        assert remote.adds == ["owned.example"]
        assert store.entries()["owned.example"]["evidence"][0]["generation"] == 1
        repository.failed(now, "collection_failed")
        sync(store.engine, remote, store, 48)
        assert remote.removes == []
        later = now + timedelta(microseconds=1)
        with transaction(engine) as session:
            session.execute(text("UPDATE collection.endpoint_coleta SET removal_ratio=1"))
        repository.apply([], set(), [], later)
        run(store.engine, 48)
        sync(store.engine, remote, store, 48)
        assert remote.removes == ["owned.example"]
        assert set(remote.rows) == {"manual.example"}
    finally:
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE scoring.execucao_bloqueio CASCADE"))
