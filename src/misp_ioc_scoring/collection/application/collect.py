"""Synchronous transaction boundary with bounded retries and safe checkpoints."""
from datetime import timedelta
from typing import Protocol
import time
from misp_ioc_scoring.shared.errors import OperationalError


class CollectionRepository(Protocol):
    def checkpoint(self): ...
    def apply(self, observations, active_uuids, warninglists, collected_at): ...
    def failed(self, collected_at, code): ...


class Source(Protocol):
    def observations(self, collected_at, since=None): ...
    def warninglists(self): ...


def collect(source: Source, repository: CollectionRepository, collected_at, *,
            overlap_minutes: float, attempts: int, backoff_seconds: float, sleep=time.sleep):
    checkpoint = repository.checkpoint()
    since = checkpoint - timedelta(minutes=overlap_minutes) if checkpoint else None
    for attempt in range(attempts):
        try:
            observations = list(source.observations(collected_at, since))
            # A complete identity snapshot is mandatory: absence in an incremental window
            # cannot be interpreted as a removal. Full records also recover shifted pages.
            snapshot = list(source.observations(collected_at)) if since else observations
            by_uuid = {o.attribute_uuid: o for o in observations}
            by_uuid.update({o.attribute_uuid: o for o in snapshot})
            warninglists = list(source.warninglists())
            repository.apply(list(by_uuid.values()), {o.attribute_uuid for o in snapshot},
                             warninglists, collected_at)
            return
        except Exception as error:
            code = error.code if isinstance(error, OperationalError) else 'collection_failed'
            if attempt + 1 == attempts:
                repository.failed(collected_at, code)
                raise OperationalError(code) from None
            sleep(backoff_seconds * 2 ** attempt)
