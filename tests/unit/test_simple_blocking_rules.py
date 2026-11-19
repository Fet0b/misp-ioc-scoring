from datetime import datetime, timedelta, timezone

import pytest

from misp_ioc_scoring.scoring.domain.simple_blocking import decision


@pytest.mark.parametrize("changes,expected", [
    ({}, "eligible"),
    ({"kind": "url"}, "eligible"),
    ({"kind": "hostname"}, "type"),
    ({"to_ids": False}, "to_ids"),
    ({"analysis": "1"}, "analysis"),
    ({"removed": True}, "removed"),
    ({"warning": True}, "warninglist"),
    ({"warning": None}, "indeterminate"),
    ({"age": 365}, "expired"),
    ({"age": -1}, "indeterminate"),
])
def test_decision(changes, expected):
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fields = dict(kind="domain", to_ids=True, analysis="2", removed=False, warning=False)
    age = changes.pop("age", 364)
    fields.update(changes)
    assert decision(**fields, timestamp=now - timedelta(days=age), as_of=now) == expected
