"""Read-only collection surface. Callers receive immutable domain snapshots."""
from dataclasses import dataclass, fields
from collections import Counter
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.domain.event_aggregates import category_counts
from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry
from misp_ioc_scoring.collection.infrastructure.persistence.models import (
    IOCModel, ObservationModel, RejectionModel, WarninglistModel,
)


@dataclass(frozen=True)
class IOCSnapshot:
    id: UUID
    type: str
    normalized_value: str
    input_revision: int
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class RejectionSnapshot:
    source_instance_id: str
    attribute_uuid: UUID
    reason: str
    misp_type: str


class CollectionReader:
    def __init__(self, engine):
        self._engine = engine

    def active_iocs(self) -> tuple[IOCSnapshot, ...]:
        with Session(self._engine) as session:
            # One SELECT gives IOC revisions and observations from the same DB snapshot.
            rows = session.execute(select(IOCModel, ObservationModel).join(
                ObservationModel, IOCModel.id == ObservationModel.ioc_id).where(
                ObservationModel.removed_at.is_(None))).all()
            groups = {}
            for ioc, model in rows:
                values = {f.name: getattr(model, f.name) for f in fields(Observation)}
                values['tags'] = tuple(values['tags'])
                if ioc.id not in groups:
                    groups[ioc.id] = (ioc, [])
                groups[ioc.id][1].append(Observation(**values))
            return tuple(IOCSnapshot(ioc.id, ioc.type, ioc.normalized_value, ioc.input_revision,
                                     tuple(observations)) for ioc, observations in groups.values())

    def current_input_revision(self, ioc_id: UUID) -> int | None:
        with Session(self._engine) as session:
            return session.scalar(select(IOCModel.input_revision).where(IOCModel.id == ioc_id))

    def event_category_counts(self):
        events = {}
        for ioc in self.active_iocs():
            for observation in ioc.observations:
                key = (observation.source_instance_id, observation.event_uuid)
                events.setdefault(key, []).append(observation)
        return {key: category_counts(observations) for key, observations in events.items()}

    def first_publications(self):
        facts = {}
        for ioc in self.active_iocs():
            publications = [o for o in ioc.observations if o.orgc_uuid is not None and o.published]
            if publications:
                first = min(publications, key=lambda o: (o.source_created_at, str(o.orgc_uuid)))
                facts[(ioc.type, ioc.normalized_value)] = (first.orgc_uuid, first.source_created_at)
        return facts

    def warninglist_membership(self, kind: str, normalized_value: str) -> bool:
        with Session(self._engine) as session:
            entries = session.scalars(select(WarninglistModel).where(WarninglistModel.supported.is_(True)))
            return any(WarninglistEntry(e.source_instance_id, e.list_name, e.list_type,
                                       e.normalized_value).matches(kind, normalized_value) for e in entries)

    def unsupported_warninglist_entries(self) -> tuple[WarninglistEntry, ...]:
        with Session(self._engine) as session:
            return tuple(WarninglistEntry(e.source_instance_id, e.list_name, e.list_type, e.normalized_value)
                         for e in session.scalars(select(WarninglistModel).where(WarninglistModel.supported.is_(False))))

    def rejections(self, reason=None, source_instance_id=None) -> tuple[RejectionSnapshot, ...]:
        query = select(RejectionModel)
        if reason is not None:
            query = query.where(RejectionModel.reason == reason)
        if source_instance_id is not None:
            query = query.where(RejectionModel.source_instance_id == source_instance_id)
        with Session(self._engine) as session:
            return tuple(RejectionSnapshot(r.source_instance_id, r.attribute_uuid, r.reason, r.misp_type)
                         for r in session.scalars(query))

    def rejection_counts(self):
        return dict(Counter((r.source_instance_id, r.reason) for r in self.rejections()))
