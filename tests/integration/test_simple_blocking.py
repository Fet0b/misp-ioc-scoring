from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.scoring.api import blocking_decision
from misp_ioc_scoring.entrypoints.scoring_sharing import run_simple_blocking as run
from misp_ioc_scoring.shared.database import transaction


def test_collected_attribute_and_stale_decision(engine):
    now = datetime.now(timezone.utc)
    attribute = uuid4()
    observation = Observation(
        source_instance_id="test", event_uuid=uuid4(), attribute_uuid=attribute,
        raw_value="bad.example", misp_type="domain", category="Network activity", to_ids=True,
        orgc_uuid=None, source_created_at=now, source_modified_at=now, collected_at=now,
        event_threat_level="2", event_analysis="2", distribution="0", event_distribution="0",
        published=False, attribute_id=42)
    repository = ObservationsRepository(engine, "test")
    repository.apply([observation], {attribute}, [], now)
    run(engine, 48)
    with transaction(engine) as session:
        row = blocking_decision(session, "test", attribute_id=42)
        assert row.block and row.attribute_uuid == attribute
    repository.failed(now, "test_failure")
    with transaction(engine) as session:
        assert not blocking_decision(session, "test", attribute_uuid=attribute).block
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE scoring.execucao_bloqueio CASCADE"))


def test_effective_decision_expires_and_observer_cannot_write(engine):
    from datetime import timedelta
    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.exc import DBAPIError

    now = datetime.now(timezone.utc)
    attribute = uuid4()
    timestamp = now - timedelta(days=364)
    observation = Observation(
        source_instance_id="test", event_uuid=uuid4(), attribute_uuid=attribute,
        raw_value="expired.example", misp_type="domain", category="Network activity", to_ids=True,
        orgc_uuid=None, source_created_at=timestamp, source_modified_at=timestamp, collected_at=now,
        event_threat_level="2", event_analysis="2", distribution="0", event_distribution="0",
        published=False)
    ObservationsRepository(engine, "test").apply([observation], {attribute}, [], now)
    run(engine, 48)
    with transaction(engine) as session:
        session.execute(text("UPDATE scoring.decisao_bloqueio SET expires_at = now() WHERE attribute_uuid = :id"),
                        {"id": attribute})
    observer = create_engine(engine.url.set(username="observer"))
    try:
        with transaction(observer) as session:
            row = blocking_decision(session, "test", attribute_uuid=attribute)
            assert row.reason == "expired" and row.block is False
            assert row.attribute_id is None
            assert blocking_decision(session, "other", attribute_uuid=attribute) is None
        with pytest.raises(DBAPIError), transaction(observer) as session:
            session.execute(text("DELETE FROM scoring.decisao_bloqueio"))
    finally:
        observer.dispose()
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE scoring.execucao_bloqueio CASCADE"))


def test_runner_records_failure_and_skips_when_locked(engine):
    from uuid import uuid4
    import pytest
    from misp_ioc_scoring.scoring.infrastructure.persistence.simple_blocking import BlockingRunner

    run_id = uuid4()
    now = datetime.now(timezone.utc)
    with pytest.raises(RuntimeError):
        with BlockingRunner(engine, uuid4) as store:
            store.start(run_id, now)
            raise RuntimeError("boom")
    with engine.connect() as connection:
        status, as_of = connection.execute(text(
            "SELECT status, as_of FROM scoring.execucao_bloqueio WHERE id=:id"), {"id": run_id}).one()
    assert (status, as_of) == ("failed", now)
    with transaction(engine) as session:
        session.execute(text("SELECT pg_advisory_xact_lock(874202)"))
        with BlockingRunner(engine, uuid4) as store:
            assert store is None
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE scoring.execucao_bloqueio CASCADE"))
