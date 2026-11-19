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


def blocking_snapshot(session):
    """Read under the caller's collection advisory lock."""
    from .infrastructure.persistence.models import EndpointModel

    endpoints = {item.id: item for item in session.scalars(select(EndpointModel))}
    observations = session.execute(select(ObservationModel, IOCModel.normalized_value)
                                   .join(IOCModel, IOCModel.id == ObservationModel.ioc_id)).all()
    warnings = tuple(session.scalars(select(WarninglistModel)))
    rejected = tuple(session.scalars(select(RejectionModel)))
    return endpoints, observations, warnings, rejected


def blocking_warninglist_membership(entries, kind, value):
    from ipaddress import ip_address
    from urllib.parse import urlsplit

    host = urlsplit(value).hostname if kind == "url" else value
    host_kind = "domain"
    try:
        ip_address(host)
        host_kind = "ip-dst"
    except ValueError:
        pass
    uncertain = False
    for item in entries:
        entry = WarninglistEntry(item.source_instance_id, item.list_name,
                                 item.list_type, item.normalized_value)
        if not item.supported or not entry.supported:
            uncertain = True
        elif entry.matches(kind, value) or (kind == "url" and entry.matches(host_kind, host)):
            return True
    return None if uncertain else False


def active_blocking_values(session):
    return session.execute(select(
        ObservationModel.source_instance_id, ObservationModel.attribute_uuid,
        ObservationModel.misp_type, ObservationModel.category, IOCModel.normalized_value,
    ).join(IOCModel, IOCModel.id == ObservationModel.ioc_id).where(
        ObservationModel.removed_at.is_(None),
        ObservationModel.misp_type.in_(("domain", "url")),
    )).all()


def unavailable_blocking_sources(session, now, max_age):
    from .infrastructure.persistence.models import EndpointModel

    return set(session.scalars(select(EndpointModel.id).where(
        (EndpointModel.generation == 0) | (EndpointModel.status != "completed")
        | EndpointModel.last_success_at.is_(None)
        | (EndpointModel.last_success_at <= now - max_age)
    )))


def blocking_generations(session):
    from .infrastructure.persistence.models import EndpointModel

    return dict(session.execute(select(EndpointModel.id, EndpointModel.generation)).tuples().all())
