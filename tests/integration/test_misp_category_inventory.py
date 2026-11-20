import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import create_engine

from misp_ioc_scoring.collection.adapters.schemas import EventPayload
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from tools.misp_category_inventory import inventory


def test_inventory_includes_nested_categories_and_marks_unavailable_source(engine):
    now = datetime.now(timezone.utc)
    observations = list(EventPayload.model_validate({
        "uuid": str(uuid4()), "date": now, "timestamp": now, "threat_level_id": 2,
        "analysis": 2, "distribution": 0, "published": True,
        "Object": [{"Attribute": [{
            "uuid": str(uuid4()), "type": "url", "value": "https://private.example/value",
            "category": "Other", "to_ids": True, "timestamp": now,
        }]}],
    }).observations("test", now))
    repository = ObservationsRepository(engine, "test")
    repository.apply(observations, {observations[0].attribute_uuid}, [], now)
    repository.failed(now, "test_failure")
    observer = create_engine(engine.url.set(username="observer"))
    try:
        with observer.connect() as connection:
            report = inventory(connection)
    finally:
        observer.dispose()
    assert report == {
        "sources": [{"source_instance_id": "test", "status": "unavailable"}],
        "counts": [{"source_instance_id": "test", "misp_type": "url", "category": "Other",
                    "attributes": 1, "earliest": now, "latest": now}],
    }
    assert "private.example" not in json.dumps(report, default=str)
