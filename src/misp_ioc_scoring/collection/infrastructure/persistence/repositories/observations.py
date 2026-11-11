"""Atomic observation upsert and full-snapshot reconciliation per endpoint."""
from dataclasses import asdict
from uuid import uuid4
from sqlalchemy import delete, select, update
from misp_ioc_scoring.collection.application.reconcile import guard_removals
from misp_ioc_scoring.collection.application.status import report_status
from misp_ioc_scoring.collection.domain.normalization import normalize, IndicatorRejected
from misp_ioc_scoring.collection.domain.input_revision import inputs_changed
from misp_ioc_scoring.collection.infrastructure.persistence.models import (
    EndpointModel, IOCModel, ObservationModel, RejectionModel, WarninglistModel,
)
from misp_ioc_scoring.shared.database import transaction
from misp_ioc_scoring.shared.errors import OperationalError


class ObservationsRepository:
    def __init__(self, engine, source_instance_id):
        self.engine = engine
        self.source_instance_id = source_instance_id

    def checkpoint(self):
        with transaction(self.engine) as session:
            return session.get(EndpointModel, self.source_instance_id).last_successful_checkpoint

    def apply(self, observations, active_uuids, warninglists, collected_at):
        with transaction(self.engine) as session:
            endpoint = session.scalar(select(EndpointModel).where(
                EndpointModel.id == self.source_instance_id).with_for_update(nowait=True))
            if endpoint.last_successful_checkpoint and endpoint.last_successful_checkpoint > collected_at:
                raise OperationalError('collection_checkpoint_superseded')
            active = list(session.scalars(select(ObservationModel).where(
                ObservationModel.source_instance_id == self.source_instance_id,
                ObservationModel.removed_at.is_(None))))
            removals = [o for o in active if o.attribute_uuid not in active_uuids]
            guard_removals(len(active), len(removals), endpoint.removal_ratio)
            changed = set()
            for observation in observations:
                existing = session.scalar(select(ObservationModel).where(
                    ObservationModel.source_instance_id == self.source_instance_id,
                    ObservationModel.attribute_uuid == observation.attribute_uuid))
                if existing and existing.source_modified_at > observation.source_modified_at:
                    continue
                try:
                    value = normalize(observation.misp_type, observation.raw_value)
                except IndicatorRejected as error:
                    rejection = session.scalar(select(RejectionModel).where(
                        RejectionModel.source_instance_id == self.source_instance_id,
                        RejectionModel.attribute_uuid == observation.attribute_uuid,
                        RejectionModel.reason == error.reason))
                    values = dict(source_instance_id=self.source_instance_id,
                                  event_uuid=observation.event_uuid, attribute_uuid=observation.attribute_uuid,
                                  misp_type=observation.misp_type, raw_value=observation.raw_value,
                                  reason=error.reason, detail='indicator_rejected', rejected_at=collected_at)
                    if rejection:
                        for key, val in values.items():
                            setattr(rejection, key, val)
                    else:
                        session.add(RejectionModel(**values))
                    if existing and existing.removed_at is None:
                        existing.removed_at = collected_at
                        changed.add(existing.ioc_id)
                    continue
                ioc = session.scalar(select(IOCModel).where(IOCModel.type == observation.misp_type,
                                                          IOCModel.normalized_value == value))
                if ioc is None:
                    ioc = IOCModel(id=uuid4(), type=observation.misp_type, normalized_value=value,
                                   input_revision=0, created_at=collected_at, updated_at=collected_at)
                    session.add(ioc)
                    session.flush()
                values = asdict(observation)
                values['tags'] = list(values['tags'])
                if existing:
                    if inputs_changed(existing, observation) or existing.ioc_id != ioc.id:
                        changed.update((existing.ioc_id, ioc.id))
                    for key, val in values.items():
                        setattr(existing, key, val)
                    existing.ioc_id = ioc.id
                else:
                    session.add(ObservationModel(ioc_id=ioc.id, **values))
                    changed.add(ioc.id)
                session.execute(delete(RejectionModel).where(
                    RejectionModel.source_instance_id == self.source_instance_id,
                    RejectionModel.attribute_uuid == observation.attribute_uuid))
            for observation in removals:
                observation.removed_at = collected_at
                changed.add(observation.ioc_id)
            for ioc_id in changed:
                session.execute(update(IOCModel).where(IOCModel.id == ioc_id).values(
                    input_revision=IOCModel.input_revision + 1, updated_at=collected_at))
            session.execute(delete(WarninglistModel).where(WarninglistModel.source_instance_id == self.source_instance_id))
            unique_entries = {(w.list_name, w.list_type, w.normalized_value): w for w in warninglists}
            for entry in unique_entries.values():
                session.add(WarninglistModel(**asdict(entry), supported=entry.supported, collected_at=collected_at))
            endpoint.last_successful_checkpoint = collected_at
            endpoint.last_run_at = collected_at
            endpoint.last_success_at = collected_at
            endpoint.status = 'completed'
            endpoint.error = None
            endpoint.warnings = []
        report_status(self.source_instance_id, 'completed')

    def failed(self, collected_at, code):
        with transaction(self.engine) as session:
            endpoint = session.get(EndpointModel, self.source_instance_id)
            endpoint.last_run_at = collected_at
            endpoint.status = 'failed'
            endpoint.error = code
            if code == 'collection_removal_limit_exceeded':
                endpoint.warnings = [code]
        report_status(self.source_instance_id, 'failed', code)
