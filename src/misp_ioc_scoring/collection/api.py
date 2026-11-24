"""Read-only collection surface. Callers receive immutable domain snapshots."""
from dataclasses import dataclass, fields
from collections import Counter
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.domain.event_aggregates import CATEGORIES
from misp_ioc_scoring.collection.domain.rejections import IndicatorRejection
from misp_ioc_scoring.collection.domain.snapshots import CollectionSnapshot, ObservationSnapshot, SourceSnapshot
from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry
from misp_ioc_scoring.collection.infrastructure.persistence.models import (
    EndpointModel, IOCModel, ObservationModel, RejectionModel, WarninglistModel,
)


@dataclass(frozen=True)
class RejectionSnapshot:
    source_instance_id: str
    attribute_uuid: UUID
    reason: str
    misp_type: str


class CollectionReader:
    def __init__(self, engine):
        self._engine = engine

    def current_input_revision(self, ioc_id: UUID) -> int | None:
        with Session(self._engine) as session:
            return session.scalar(select(IOCModel.input_revision).where(IOCModel.id == ioc_id))

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


def _source(model) -> SourceSnapshot:
    return SourceSnapshot(model.id, model.generation, model.status, model.last_success_at)


def _observation(model, normalized_value, input_revision) -> ObservationSnapshot:
    values = {f.name: getattr(model, f.name) for f in fields(Observation)}
    values['tags'] = tuple(values['tags'] or ())
    return ObservationSnapshot(**values, ioc_id=model.ioc_id, normalized_value=normalized_value,
                               input_revision=input_revision)


def collection_snapshot(session) -> CollectionSnapshot:
    """Sources, active and removed observations, warninglists and rejections.

    Reads inside the caller's transaction. Callers that need a stable view hold the
    collection advisory lock (874201) or use REPEATABLE READ.
    """
    sources = {model.id: _source(model) for model in session.scalars(select(EndpointModel))}
    rows = session.execute(select(ObservationModel, IOCModel.normalized_value, IOCModel.input_revision)
                           .join(IOCModel, IOCModel.id == ObservationModel.ioc_id)).all()
    warninglists = tuple(WarninglistEntry(e.source_instance_id, e.list_name, e.list_type, e.normalized_value)
                         for e in session.scalars(select(WarninglistModel)))
    rejections = tuple(IndicatorRejection(
        source_instance_id=r.source_instance_id, event_uuid=r.event_uuid, attribute_uuid=r.attribute_uuid,
        misp_type=r.misp_type, raw_value=r.raw_value, reason=r.reason, rejected_at=r.rejected_at,
        detail=r.detail, attribute_id=r.attribute_id) for r in session.scalars(select(RejectionModel)))
    return CollectionSnapshot(sources, tuple(_observation(*row) for row in rows), warninglists, rejections)


def untrusted_sources(session, now, max_age) -> set[str]:
    """Sources whose last complete snapshot is missing, failed or older than `max_age`."""
    return {model.id for model in session.scalars(select(EndpointModel))
            if not _source(model).trusted(now, max_age)}


def source_generations(session) -> dict[str, int]:
    return {source: generation for source, generation in
            session.execute(select(EndpointModel.id, EndpointModel.generation))}


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
