from datetime import timedelta

import pytest

from misp_ioc_scoring.scoring.domain.carioca_components import attribute_score, event_score
from misp_ioc_scoring.scoring.domain.carioca_inputs import analysis, threat_level
from misp_ioc_scoring.scoring.domain.decay import DOMAIN, HASH, IP
from tests.support.carioca import AS_OF

ALPHA = {'threat_level': 0.4, 'analysis': 0.2, 'cade': 0.4}


def test_threat_level_and_analysis_mappings():
    assert [threat_level(v) for v in ('1', '2', '3', '4')] == [100, 66, 33, 0]
    assert [analysis(v) for v in ('0', '1', '2')] == [0, 50, 100]
    assert threat_level('5') is None and threat_level(None) is None and analysis('9') is None


def test_event_score_reference_cases():
    # hotels-stays55501.com: TL 33, SA 50, CADE' 19.544 -> E 31.017
    assert event_score(33, 50, 19.544, ALPHA) == pytest.approx(31.0176, abs=1e-4)
    # event 19 in the v2 calculation (raw CADE): TL 100, SA 100, CADE 18.7994 -> 67.5198
    assert event_score(100, 100, 18.7994, ALPHA) == pytest.approx(67.5198, abs=1e-4)


@pytest.mark.parametrize('group,days,expected', [(DOMAIN, 158.2835, 69.687), (IP, 3, 43.16), (HASH, 30, 29.29)])
def test_freshness_against_as_of_not_clock(group, days, expected):
    assert attribute_score(group, AS_OF - timedelta(days=days), AS_OF) == pytest.approx(expected, abs=5e-3)
    assert attribute_score(group, AS_OF + timedelta(days=1), AS_OF) is None
