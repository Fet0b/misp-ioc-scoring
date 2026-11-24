from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from misp_ioc_scoring.collection.application.collect import collect
from misp_ioc_scoring.collection.domain.reconciliation import guard_removals
from misp_ioc_scoring.shared.errors import OperationalError


class Repository:
    source_instance_id = 'test'

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


def test_incremental_attribute_absent_from_full_snapshot_is_not_published():
    class Source:
        def observations(self, collected_at, since=None):
            if since is not None:
                yield SimpleNamespace(attribute_uuid="removed-between-queries")

        def warninglists(self):
            return []

    repository = Repository()
    collect(Source(), repository, datetime.now(timezone.utc), overlap_minutes=5,
            attempts=1, backoff_seconds=2)
    assert repository.applied[0][:3] == ([], set(), [])


def test_status_log_counts_rejections_by_reason_and_source_without_values(caplog):
    import json
    import logging
    from misp_ioc_scoring.shared.logging import JsonFormatter

    class Source:
        def observations(self, collected_at, since=None):
            return []

        def warninglists(self):
            return []

    repository = Repository()
    repository.apply = lambda *args: {'applied': 3, 'removed': 1, 'rejected': {'invalid': 2, 'unsupported': 1}}
    caplog.set_level(logging.INFO)
    collect(Source(), repository, datetime.now(timezone.utc), overlap_minutes=5, attempts=1, backoff_seconds=1)
    record = next(r for r in caplog.records if getattr(r, 'event', None) == 'collection_status')
    payload = json.loads(JsonFormatter().format(record))
    assert payload['status'] == 'completed' and payload['count'] == '3' and payload['removed'] == '1'
    assert "'invalid': 2" in payload['rejections'] and "'test'" in payload['rejections']
