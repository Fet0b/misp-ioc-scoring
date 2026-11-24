from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from misp_ioc_scoring.collection.api import collection_snapshot
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.shared.database import transaction


def test_legacy_empty_snapshot_and_serialized_generation(engine):
    now = datetime.now(timezone.utc)
    repository = ObservationsRepository(engine, "test")
    with transaction(engine) as session:
        session.execute(text("UPDATE collection.endpoint_coleta SET status='completed', last_success_at=:now"),
                        {"now": now})
        snapshot = collection_snapshot(session)
        assert snapshot.sources["test"].generation == 0
        assert not (snapshot.observations or snapshot.warninglists or snapshot.rejections)
    repository.apply([], set(), [], now)
    with ThreadPoolExecutor(max_workers=2) as workers:
        failures = [workers.submit(repository.failed, now + timedelta(seconds=1), "test_failure")
                    for _ in range(2)]
        for failure in failures:
            failure.result()
    with transaction(engine) as session:
        snapshot = collection_snapshot(session)
        assert snapshot.sources["test"].generation == 3
        assert snapshot.sources["test"].status == "failed"
        assert snapshot.sources["test"].last_success_at == now
        assert not (snapshot.observations or snapshot.warninglists or snapshot.rejections)


def test_older_collection_cannot_restore_trust_after_newer_failure(engine):
    import pytest

    from misp_ioc_scoring.shared.errors import OperationalError

    now = datetime.now(timezone.utc)
    repository = ObservationsRepository(engine, "test")
    repository.failed(now, "test_failure")
    with pytest.raises(OperationalError, match="collection_checkpoint_superseded"):
        repository.apply([], set(), [], now - timedelta(seconds=1))
    with transaction(engine) as session:
        sources = collection_snapshot(session).sources
        assert sources["test"].status == "failed"
        assert sources["test"].generation == 1
