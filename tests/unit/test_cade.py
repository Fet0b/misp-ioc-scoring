"""Level 1 of SC-015: σ is test input (raw population σ from the Notion page)."""
import pytest

from misp_ioc_scoring.scoring.domain.cade import cade, category_score, counts_by_event, estimate_sigma
from misp_ioc_scoring.scoring.domain.carioca_configuration import SigmaEstimator
from misp_ioc_scoring.scoring.domain.priority import minmax
from tests.support.carioca import observation

RAW = SigmaEstimator('population_std', 'notion', 'indicator')
CATEGORIES = ['Network activity', 'Payload delivery', 'Other'] + [f'c{i}' for i in range(13)]
BETA = {category: 1 / 16 for category in CATEGORIES}


def test_category_score_formula():
    assert category_score(60, 917.29, RAW) == pytest.approx(0.2137, abs=1e-4)
    assert category_score(48, 165.15, RAW) == pytest.approx(4.1359, abs=2e-4)
    assert category_score(10, 0.45, RAW) == pytest.approx(100.0, abs=1e-4)
    assert category_score(0, 3.0, RAW) == 0


def test_hotels_stays_cade():
    counts = dict.fromkeys(CATEGORIES, 0) | {'Network activity': 60, 'Payload delivery': 48, 'Other': 10}
    sigmas = dict.fromkeys(CATEGORIES, 1.0) | {'Network activity': 917.29, 'Payload delivery': 165.15, 'Other': 0.45}
    assert cade(counts, sigmas, BETA, RAW) == pytest.approx(6.5218, abs=1e-4)


def test_event_19_cade():
    # Notion "CADE — fórmulas e exemplos reais", top 10: event 19 with the population σ of §3.1.
    n = {'Payload installation': 792, 'External analysis': 508, 'Network activity': 48,
         'Antivirus detection': 35, 'Payload delivery': 33, 'Other': 9}
    sigma = {'Payload installation': 116.646, 'External analysis': 76.820, 'Network activity': 917.286,
             'Antivirus detection': 1.617, 'Payload delivery': 327.727, 'Other': 165.148}
    categories = list(n) + [f'c{i}' for i in range(10)]
    counts = dict.fromkeys(categories, 0) | n
    sigmas = dict.fromkeys(categories, 1.0) | sigma
    assert cade(counts, sigmas, {c: 1 / 16 for c in categories}, RAW) == pytest.approx(18.7994, abs=1e-4)


def test_sigma_zero_rule_from_configuration():
    assert category_score(0, 0, RAW) == 0
    assert category_score(3, 0, RAW) == 100
    assert category_score(3, 0, SigmaEstimator('population_std', 't', 'zero')) == 0
    assert category_score(3, 0, SigmaEstimator('population_std', 't', 'half')) == 50


def test_cade_minmax_between_events():
    normalized, degenerate, low, high = minmax({'hotels': 6.5218, 'low': 0.0000037, 'high': 33.3707})
    assert normalized['hotels'] == pytest.approx(19.544, abs=1e-3)
    assert not degenerate and (low, high) == (0.0000037, 33.3707)


def test_counts_only_active_to_ids_and_estimators():
    observations = [observation('a', event='e1'), observation('b', 'b.org', event='e1'),
                    observation('c', 'c.org', event='e2', to_ids=False),
                    observation('d', 'd.org', event='e2', category='Other'),
                    observation('e', 'e.org', event='e3', removed=True)]
    events = counts_by_event(observations, CATEGORIES)
    assert len(events) == 2
    assert [counts['Network activity'] for counts in events.values()] in ([2, 0], [0, 2])
    sigmas, inputs = estimate_sigma(events, CATEGORIES, RAW)
    assert sigmas['Network activity'] == pytest.approx(1.0)
    log, _ = estimate_sigma(events, CATEGORIES, SigmaEstimator('log_std', 't', 'indicator'))
    assert log['Network activity'] == pytest.approx(0.5493, abs=1e-4)
    capped, details = estimate_sigma(events, CATEGORIES, SigmaEstimator('p95_winsorized', 't', 'indicator'))
    assert details['Network activity']['cap'] == pytest.approx(1.9)
    assert capped['Network activity'] == pytest.approx(0.95)
