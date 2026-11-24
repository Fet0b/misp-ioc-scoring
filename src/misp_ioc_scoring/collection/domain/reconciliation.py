"""Consolidation of one complete source snapshot into IOCs (pure; no persistence).

Rules that used to live in the repository: older updates are ignored, invalid or
unsupported values become rejections and deactivate the observation, valid values map
to the IOC identity `(type, normalized value)`, earlier rejections are resolved,
observations missing from the snapshot are removed, and only CARIOCA inputs raise the
IOC revision. A mass removal above `removal_ratio` refuses the whole reconciliation.
"""
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from misp_ioc_scoring.shared.errors import OperationalError

from .indicators import IOC
from .input_revision import inputs_changed
from .normalization import IndicatorRejected, normalize
from .rejections import IndicatorRejection


def guard_removals(active_count: int, removal_count: int, maximum_ratio: float) -> None:
    if active_count and removal_count / active_count > maximum_ratio:
        raise OperationalError('collection_removal_limit_exceeded')


@dataclass(frozen=True)
class NewIOC:
    id: UUID
    ioc: IOC


@dataclass
class Changeset:
    inserts: list = field(default_factory=list)  # (Observation, ioc_id)
    updates: list = field(default_factory=list)  # (Observation, ioc_id): replaces every field
    new_iocs: list = field(default_factory=list)  # NewIOC
    rejections: list = field(default_factory=list)  # IndicatorRejection to upsert
    resolved_rejections: set = field(default_factory=set)  # attribute UUIDs whose rejections go away
    removals: set = field(default_factory=set)  # attribute UUIDs marked removed at `collected_at`
    revised_iocs: set = field(default_factory=set)  # IOC ids whose input revision goes up

    def counts(self):
        rejected = {}
        for rejection in self.rejections:
            rejected[rejection.reason] = rejected.get(rejection.reason, 0) + 1
        return {'applied': len(self.inserts) + len(self.updates), 'rejected': rejected,
                'removed': len(self.removals)}


def identity_keys(received):
    """IOC identities `(type, normalized value)` that the received observations may need."""
    keys = set()
    for observation in received:
        try:
            keys.add((observation.misp_type, normalize(observation.misp_type, observation.raw_value)))
        except IndicatorRejected:
            pass
    return keys


def reconcile_snapshot(existing, received, collected_at, removal_ratio, *, iocs, active_uuids=None,
                       new_id=uuid4) -> Changeset:
    """Plan the writes for one source.

    `existing`: attribute UUID -> stored `ObservationSnapshot` of the source (active and removed);
    `received`: the complete snapshot; `iocs`: `(type, normalized value)` -> IOC id already known.
    """
    active_uuids = {o.attribute_uuid for o in received} if active_uuids is None else active_uuids
    active = [o for o in existing.values() if o.removed_at is None]
    removals = [o for o in active if o.attribute_uuid not in active_uuids]
    guard_removals(len(active), len(removals), removal_ratio)

    changes = Changeset()
    iocs = dict(iocs)
    for observation in received:
        stored = existing.get(observation.attribute_uuid)
        if stored and stored.source_modified_at > observation.source_modified_at:
            continue
        try:
            value = normalize(observation.misp_type, observation.raw_value)
        except IndicatorRejected as error:
            changes.rejections.append(IndicatorRejection(
                source_instance_id=observation.source_instance_id, event_uuid=observation.event_uuid,
                attribute_uuid=observation.attribute_uuid, misp_type=observation.misp_type,
                raw_value=observation.raw_value, reason=error.reason, rejected_at=collected_at,
                attribute_id=observation.attribute_id))
            if stored and stored.removed_at is None:
                changes.removals.add(stored.attribute_uuid)
                changes.revised_iocs.add(stored.ioc_id)
            continue
        key = (observation.misp_type, value)
        ioc_id = iocs.get(key)
        if ioc_id is None:
            ioc_id = new_id()
            iocs[key] = ioc_id
            changes.new_iocs.append(NewIOC(ioc_id, IOC(*key)))
        if stored:
            if inputs_changed(stored, observation) or stored.ioc_id != ioc_id:
                changes.revised_iocs.update((stored.ioc_id, ioc_id))
            changes.updates.append((observation, ioc_id))
        else:
            changes.inserts.append((observation, ioc_id))
            changes.revised_iocs.add(ioc_id)
        changes.resolved_rejections.add(observation.attribute_uuid)
    for stored in removals:
        changes.removals.add(stored.attribute_uuid)
        changes.revised_iocs.add(stored.ioc_id)
    return changes
