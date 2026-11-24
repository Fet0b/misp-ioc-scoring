"""Atomic persistence of one source snapshot; the consolidation rules live in the domain."""
from dataclasses import asdict, fields
from sqlalchemy import delete, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.domain.reconciliation import identity_keys, reconcile_snapshot
from misp_ioc_scoring.collection.domain.snapshots import ObservationSnapshot
from misp_ioc_scoring.collection.infrastructure.persistence.models import (
    EndpointModel, IOCModel, ObservationModel, RejectionModel, WarninglistModel,
)
from misp_ioc_scoring.shared.database import transaction
from misp_ioc_scoring.shared.errors import OperationalError

_CHUNK = 5000
_FIELDS = [f.name for f in fields(Observation)]


def _chunks(items):
    items = list(items)
    for start in range(0, len(items), _CHUNK):
        yield items[start:start + _CHUNK]


def _snapshot(model, ioc):
    values = {name: getattr(model, name) for name in _FIELDS}
    values['tags'] = tuple(values['tags'] or ())
    return ObservationSnapshot(**values, ioc_id=model.ioc_id, normalized_value=ioc.normalized_value,
                               input_revision=ioc.input_revision)


def _values(observation):
    values = asdict(observation)
    values['tags'] = list(values['tags'])
    return values


class ObservationsRepository:
    def __init__(self, engine, source_instance_id):
        self.engine = engine
        self.source_instance_id = source_instance_id

    def checkpoint(self):
        with transaction(self.engine) as session:
            return session.get(EndpointModel, self.source_instance_id).last_successful_checkpoint

    def apply(self, observations, active_uuids, warninglists, collected_at):
        """Reconcile a complete snapshot of this source; returns applied/rejected/removed counts."""
        with transaction(self.engine) as session:
            session.execute(text("SELECT pg_advisory_xact_lock(874201)"))
            endpoint = session.scalar(select(EndpointModel).where(
                EndpointModel.id == self.source_instance_id).with_for_update(nowait=True))
            if endpoint.last_run_at and endpoint.last_run_at > collected_at:
                raise OperationalError('collection_checkpoint_superseded')
            stored = {model.attribute_uuid: (model, ioc) for model, ioc in session.execute(
                select(ObservationModel, IOCModel).join(IOCModel, IOCModel.id == ObservationModel.ioc_id)
                .where(ObservationModel.source_instance_id == self.source_instance_id))}
            iocs = {}
            for chunk in _chunks(identity_keys(observations)):
                iocs.update({(kind, value): ioc_id for ioc_id, kind, value in session.execute(
                    select(IOCModel.id, IOCModel.type, IOCModel.normalized_value)
                    .where(tuple_(IOCModel.type, IOCModel.normalized_value).in_(chunk)))})
            changes = reconcile_snapshot(
                {uuid: _snapshot(model, ioc) for uuid, (model, ioc) in stored.items()},
                observations, collected_at, endpoint.removal_ratio, iocs=iocs, active_uuids=active_uuids)

            for item in changes.new_iocs:
                session.add(IOCModel(id=item.id, type=item.ioc.type, normalized_value=item.ioc.normalized_value,
                                     input_revision=0, created_at=collected_at, updated_at=collected_at))
            session.flush()
            for observation, ioc_id in changes.inserts:
                session.add(ObservationModel(ioc_id=ioc_id, **_values(observation)))
            for observation, ioc_id in changes.updates:
                model = stored[observation.attribute_uuid][0]
                for key, value in _values(observation).items():
                    setattr(model, key, value)
                model.ioc_id = ioc_id
            for uuid in changes.removals:
                stored[uuid][0].removed_at = collected_at
            session.flush()
            for rejection in changes.rejections:
                values = dict(source_instance_id=rejection.source_instance_id, event_uuid=rejection.event_uuid,
                              attribute_uuid=rejection.attribute_uuid, misp_type=rejection.misp_type,
                              attribute_id=rejection.attribute_id, raw_value=rejection.raw_value,
                              reason=rejection.reason, detail=rejection.detail, rejected_at=rejection.rejected_at)
                query = insert(RejectionModel).values(**values)
                session.execute(query.on_conflict_do_update(
                    index_elements=['source_instance_id', 'attribute_uuid', 'reason'],
                    set_={key: query.excluded[key] for key in values}))
            for chunk in _chunks(changes.resolved_rejections):
                session.execute(delete(RejectionModel).where(
                    RejectionModel.source_instance_id == self.source_instance_id,
                    RejectionModel.attribute_uuid.in_(chunk)))
            for chunk in _chunks(changes.revised_iocs):
                session.execute(update(IOCModel).where(IOCModel.id.in_(chunk)).values(
                    input_revision=IOCModel.input_revision + 1, updated_at=collected_at))
            session.execute(delete(WarninglistModel).where(WarninglistModel.source_instance_id == self.source_instance_id))
            unique_entries = {(w.list_name, w.list_type, w.normalized_value): w for w in warninglists}
            for entry in unique_entries.values():
                session.add(WarninglistModel(**asdict(entry), supported=entry.supported, collected_at=collected_at))
            endpoint.last_successful_checkpoint = collected_at
            endpoint.last_run_at = collected_at
            endpoint.last_success_at = collected_at
            endpoint.generation += 1
            endpoint.status = 'completed'
            endpoint.error = None
            endpoint.warnings = []
        return changes.counts()

    def failed(self, collected_at, code):
        with transaction(self.engine) as session:
            session.execute(text("SELECT pg_advisory_xact_lock(874201)"))
            endpoint = session.get(EndpointModel, self.source_instance_id)
            if endpoint.last_run_at and endpoint.last_run_at > collected_at:
                return
            endpoint.generation += 1
            endpoint.last_run_at = collected_at
            endpoint.status = 'failed'
            endpoint.error = code
            if code == 'collection_removal_limit_exceeded':
                endpoint.warnings = [code]
