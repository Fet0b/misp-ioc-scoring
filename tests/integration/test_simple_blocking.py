from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.scoring.api import blocking_decision
from misp_ioc_scoring.scoring.infrastructure.persistence.simple_blocking import run
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
        assert row["block"] and row["attribute_uuid"] == attribute
    repository.failed(now, "test_failure")
    with transaction(engine) as session:
        assert not blocking_decision(session, "test", attribute_uuid=attribute)["block"]
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE scoring.execucao_bloqueio CASCADE"))
