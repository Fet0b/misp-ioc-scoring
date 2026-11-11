from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from misp_ioc_scoring.collection.application.collect import collect
from misp_ioc_scoring.collection.application.reconcile import guard_removals
from misp_ioc_scoring.shared.errors import OperationalError


class Repository:
    def __init__(self):
        self.applied = []
        self.failures = []
    def checkpoint(self):
        return datetime(2026, 11, 1, tzinfo=timezone.utc)
    def apply(self, *args):
        self.applied.append(args)
    def failed(self, *args):
        self.failures.append(args)


def test_partial_page_failure_retries_whole_window_without_checkpoint():
    class Source:
        calls = 0
        def observations(self, collected_at, since=None):
            self.calls += 1
            yield SimpleNamespace(attribute_uuid='one')
            raise OperationalError('misp_unavailable')
        def warninglists(self):
            return []
    repository = Repository()
    delays = []
    with pytest.raises(OperationalError, match='misp_unavailable'):
        collect(Source(), repository, datetime.now(timezone.utc), overlap_minutes=5,
                attempts=3, backoff_seconds=2, sleep=delays.append)
    assert delays == [2, 4]
    assert not repository.applied
    assert len(repository.failures) == 1


def test_removal_guard_boundary():
    guard_removals(10, 2, .2)
    with pytest.raises(OperationalError, match='collection_removal_limit_exceeded'):
        guard_removals(10, 3, .2)
