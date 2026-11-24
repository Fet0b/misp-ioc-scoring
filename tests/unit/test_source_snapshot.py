from datetime import datetime, timedelta, timezone

import pytest

from misp_ioc_scoring.collection.domain.snapshots import SourceSnapshot

NOW = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
MAX_AGE = timedelta(hours=48)


@pytest.mark.parametrize('generation,status,last_success,trusted', [
    (0, 'completed', NOW - timedelta(hours=1), False),
    (3, 'failed', NOW - timedelta(hours=1), False),
    (3, 'scheduled', NOW - timedelta(hours=1), False),
    (3, 'completed', None, False),
    (3, 'completed', NOW - MAX_AGE, False),
    (3, 'completed', NOW - MAX_AGE - timedelta(seconds=1), False),
    (3, 'completed', NOW - MAX_AGE + timedelta(microseconds=1), True),
    (1, 'completed', NOW, True),
])
def test_trusted_matches_unavailable_sources_sql(generation, status, last_success, trusted):
    source = SourceSnapshot('peer', generation, status, last_success)
    assert source.trusted(NOW, MAX_AGE) is trusted


def test_valid_until_only_for_completed_snapshot():
    assert SourceSnapshot('peer', 2, 'completed', NOW).valid_until(MAX_AGE) == NOW + MAX_AGE
    assert SourceSnapshot('peer', 2, 'failed', NOW).valid_until(MAX_AGE) is None
    assert SourceSnapshot('peer', 0, 'completed', NOW).valid_until(MAX_AGE) is None
