from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.infrastructure.persistence.models import IOCModel, ObservationModel
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.shared.errors import OperationalError

NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)


def observation(raw='EXAMPLE.COM'):
    return Observation('test', uuid4(), uuid4(), raw, 'domain', 'Network activity',
                       True, uuid4(), NOW, NOW, NOW, '2', '0', '5', '1', True)


def test_idempotent_upsert_and_provenance(engine):
    repository = ObservationsRepository(engine, 'test')
    one = observation()
    two = observation('example.com')
    for _ in range(2):
        repository.apply([one, two], {one.attribute_uuid, two.attribute_uuid}, [], NOW)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(IOCModel)) == 1
        assert session.scalar(select(func.count()).select_from(ObservationModel)) == 2
        assert session.scalar(select(IOCModel.input_revision)) == 1
    assert repository.checkpoint() == NOW


def test_guard_rolls_back_entire_window_without_checkpoint(engine):
    repository = ObservationsRepository(engine, 'test')
    one = observation()
    repository.apply([one], {one.attribute_uuid}, [], NOW)
    with pytest.raises(OperationalError, match='collection_removal_limit_exceeded'):
        repository.apply([], set(), [], NOW + timedelta(hours=1))
    assert repository.checkpoint() == NOW
    with Session(engine) as session:
        assert session.scalar(select(ObservationModel.removed_at)) is None


def test_only_relevant_changes_increment_revision(engine):
    repository = ObservationsRepository(engine, 'test')
    one = observation()
    repository.apply([one], {one.attribute_uuid}, [], NOW)
    repository.apply([replace(one, tags=('tag',))], {one.attribute_uuid}, [], NOW)
    with Session(engine) as session:
        assert session.scalar(select(IOCModel.input_revision)) == 1
    repository.apply([replace(one, event_analysis='1')], {one.attribute_uuid}, [], NOW)
    with Session(engine) as session:
        assert session.scalar(select(IOCModel.input_revision)) == 2


def test_removal_preserves_observation_and_other_endpoint_checkpoint(engine):
    from misp_ioc_scoring.collection.infrastructure.persistence.models import EndpointModel
    from misp_ioc_scoring.shared.database import transaction
    with transaction(engine) as session:
        endpoint = session.get(EndpointModel, 'test')
        endpoint.removal_ratio = 1
        session.add(EndpointModel(id='other', base_url='https://other.example', credential_secret_ref='env:KEY',
                                 interval_seconds=120, to_ids_only=True, removal_ratio=.2))
    repository = ObservationsRepository(engine, 'test')
    one = observation()
    repository.apply([one], {one.attribute_uuid}, [], NOW)
    later = NOW + timedelta(hours=1)
    repository.apply([], set(), [], later)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ObservationModel)) == 1
        assert session.scalar(select(ObservationModel.removed_at)) == later
        assert session.get(EndpointModel, 'other').last_successful_checkpoint is None
    assert repository.checkpoint() == later
