from datetime import datetime, timedelta, timezone

import pytest

from misp_ioc_scoring.scoring.domain.decay import DOMAIN, HASH, IP, DecayGroup
from misp_ioc_scoring.scoring.domain.simple_blocking import freshness


def test_bounds():
    group = DecayGroup('test', 1, 10)
    assert group.freshness(-0.001) is None
    assert group.freshness(10) == 0
    assert group.freshness(11) == 0
    assert group.freshness(0) == 100


@pytest.mark.parametrize('group,t,expected', [
    (DOMAIN, 158.2835, 69.687), (IP, 3, 43.16), (HASH, 30, 29.29),
])
def test_notion_reference_values(group, t, expected):
    assert group.freshness(t) == pytest.approx(expected, abs=5e-3)


@pytest.mark.parametrize('days', [0, 1, 364.9, 365])
def test_simple_blocking_freshness_uses_domain_group(days):
    as_of = datetime(2026, 11, 24, tzinfo=timezone.utc)
    expected = 100 * (1 - (days / 365) ** (1 / 0.7)) if days < 365 else 0
    assert freshness(as_of - timedelta(days=days), as_of) == pytest.approx(expected)
    assert DOMAIN.freshness(days) == pytest.approx(expected)


def test_constants():
    assert (DOMAIN.D, DOMAIN.T, IP.D, IP.T, HASH.D, HASH.T) == (0.7, 365, 1.5, 7, 2, 60)
