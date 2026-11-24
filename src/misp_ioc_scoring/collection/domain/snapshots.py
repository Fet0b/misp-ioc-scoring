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


@dataclass(frozen=True, kw_only=True)
class ObservationSnapshot(Observation):
    """Source observation together with the identity and revision of its IOC."""
    ioc_id: UUID
    normalized_value: str
    input_revision: int


@dataclass(frozen=True)
class CollectionSnapshot:
    """Everything read from `collection` in one transaction."""
    sources: dict[str, SourceSnapshot]
    observations: tuple[ObservationSnapshot, ...]
    warninglists: tuple[WarninglistEntry, ...]
    rejections: tuple[IndicatorRejection, ...]
