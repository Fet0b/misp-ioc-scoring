"""Immutable views of collected data handed to other modules through `collection.api`."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from .observations import Observation
from .rejections import IndicatorRejection
from .warninglists import WarninglistEntry


@dataclass(frozen=True)
class SourceSnapshot:
    """State of one collection endpoint; the single rule for trusting its snapshot."""
    source_instance_id: str
    generation: int
    status: str
    last_success_at: datetime | None

    def valid_until(self, max_age: timedelta) -> datetime | None:
        """End of validity of the last complete snapshot, or None if there is none."""
        if self.generation > 0 and self.status == 'completed' and self.last_success_at is not None:
            return self.last_success_at + max_age
        return None

    def trusted(self, now: datetime, max_age: timedelta) -> bool:
        limit = self.valid_until(max_age)
        return limit is not None and now < limit


# MISP distribution levels from most to least restrictive; 4 (sharing group) is narrower than 1.
RESTRICTIVENESS = {'0': 0, '4': 1, '1': 2, '2': 3, '3': 4}
INHERIT = '5'


@dataclass(frozen=True, kw_only=True)
class ObservationSnapshot(Observation):
    """Source observation together with the identity and revision of its IOC."""
    ioc_id: UUID
    normalized_value: str
    input_revision: int

    def effective_distribution(self) -> tuple[str, str | None]:
        """(distribution, sharing group id): the most restrictive of attribute and event.

        `5` inherits from the event. A sharing group (`4`) without a known group id, or
        attribute and event in different sharing groups, counts as `0` (organization only).
        """
        event = (self.event_distribution, self.event_sharing_group_id)
        attribute = event if self.distribution == INHERIT else (self.distribution, self.sharing_group_id)
        candidates = [item for item in (attribute, event) if item[0] in RESTRICTIVENESS]
        if len(candidates) < 2:
            return '0', None
        groups = {group for level, group in candidates if level == '4'}
        if any(level == '4' and group is None for level, group in candidates) or len(groups) > 1:
            return '0', None
        level = min((item[0] for item in candidates), key=RESTRICTIVENESS.get)
        return (level, groups.pop()) if level == '4' else (level, None)


@dataclass(frozen=True)
class CollectionSnapshot:
    """Everything read from `collection` in one transaction."""
    sources: dict[str, SourceSnapshot]
    observations: tuple[ObservationSnapshot, ...]
    warninglists: tuple[WarninglistEntry, ...]
    rejections: tuple[IndicatorRejection, ...]
