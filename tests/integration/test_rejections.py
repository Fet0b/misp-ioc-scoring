from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.infrastructure.persistence.models import IOCModel, RejectionModel
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository


def test_rejections_are_idempotent_and_resolved_atomically(engine):
    now = datetime(2026, 11, 10, tzinfo=timezone.utc)
    observation = Observation('test', uuid4(), uuid4(), 'bad domain', 'domain',
                              'Network activity', True, uuid4(), now, now, now, '2', '0', '5', '1', True)
    repository = ObservationsRepository(engine, 'test')
    for _ in range(2):
        repository.apply([observation], {observation.attribute_uuid}, [], now)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(IOCModel)) == 0
        assert session.scalar(select(func.count()).select_from(RejectionModel)) == 1
    repository.apply([replace(observation, raw_value='example.com')], {observation.attribute_uuid}, [], now)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(IOCModel)) == 1
        assert session.scalar(select(func.count()).select_from(RejectionModel)) == 0
