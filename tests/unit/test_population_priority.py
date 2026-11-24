import random
from dataclasses import replace

import pytest

from misp_ioc_scoring.scoring.application.score_population import calculate, run_carioca
from misp_ioc_scoring.scoring.domain.population import ExclusionReason as R, ioc_exclusion, observation_exclusion
from misp_ioc_scoring.scoring.domain.priority import minmax, spotis
from tests.support.carioca import AS_OF, MemoryCariocaStore, configuration, observation, snapshot

CONFIG = configuration()


@pytest.mark.parametrize('changes,reason', [
    ({}, None),
    ({'kind': 'url', 'value': 'https://x.org/'}, R.TYPE_WITHOUT_DECAY_GROUP),
    ({'kind': 'btc', 'value': 'x'}, R.TYPE_WITHOUT_DECAY_GROUP),
    ({'age_days': 400}, R.EXPIRED),
    ({'to_ids': False}, R.NOT_TO_IDS),
    ({'published': False}, R.UNPUBLISHED),
    ({'tl': '9'}, R.MISSING_DATA), ({'sa': None}, R.MISSING_DATA),
    ({'category': 'Unknown'}, R.MISSING_DATA), ({'org': None}, R.MISSING_DATA),
    ({'age_days': -1}, R.MISSING_DATA),
])
def test_observation_eligibility(changes, reason):
    assert observation_exclusion(observation('o', **changes), CONFIG, AS_OF) == reason


def test_precedence_and_incomplete_configuration():
    assert observation_exclusion(observation('o', org=None, published=False, to_ids=False), CONFIG, AS_OF) == R.MISSING_DATA
    assert observation_exclusion(observation('o', published=False, to_ids=False), CONFIG, AS_OF) == R.UNPUBLISHED
    broken = replace(CONFIG, decay_groups={})
    assert observation_exclusion(observation('o', org=None), broken, AS_OF) == R.INCOMPLETE_CONFIGURATION
    assert ioc_exclusion([R.EXPIRED, R.NOT_TO_IDS, R.TYPE_WITHOUT_DECAY_GROUP]) == R.NOT_TO_IDS
    assert ioc_exclusion([R.EXPIRED, R.INCOMPLETE_CONFIGURATION, R.MISSING_DATA]) == R.INCOMPLETE_CONFIGURATION
    assert ioc_exclusion([R.MISSING_DATA, None]) is None


def test_ioc_with_one_valid_observation_is_not_excluded():
    data = snapshot(observation('ok', ioc='same'), observation('noorg', ioc='same', org=None, source='s2'))
    _, evaluations, results, exclusions, _ = calculate(AS_OF, data, CONFIG)
    assert len(results) == 1 and exclusions == [] and len(evaluations) == 1


def test_minmax_degenerate_and_empty_population(caplog):
    normalized, degenerate, *_ = minmax({'a': 3.0, 'b': 3.0})
    assert normalized == {'a': 50, 'b': 50} and degenerate
    _, evaluations, results, _, warnings = calculate(AS_OF, snapshot(observation('only')), CONFIG)
    assert set(evaluations[0].minmax_degenerate) == {'cade', 'event', 'attribute', 'source'}
    assert evaluations[0].priority == pytest.approx(50)
    assert 'minmax_degenerate:event' in warnings
    store = MemoryCariocaStore()
    summary = run_carioca(AS_OF, snapshot(observation('old', age_days=400)), CONFIG, store)
    assert summary.valid_population == 0 and summary.warnings == ('empty_population',)
    assert store.res == [] and store.summary == summary
    assert 'carioca_empty_population' in caplog.text


def test_spotis_equals_mean_of_normalized_components():
    weights = CONFIG.spotis_weights
    generator = random.Random(20261124)
    for _ in range(1000):
        s, e, a = (generator.uniform(0, 100) for _ in range(3))
        assert spotis({'source': s, 'event': e, 'attribute': a}, weights) == pytest.approx((s + e + a) / 3)
    assert spotis({'source': 100, 'event': 60.532, 'attribute': 66.984}, weights) == pytest.approx(75.838, abs=1e-3)


def test_normalization_scopes():
    data = snapshot(
        observation('v1', 'a.org', event='e1', org='A', sa='0', age_days=10),
        observation('v2', 'b.org', event='e2', org='B', sa='2', age_days=100),
        # e3 only has an expired observation: it is in the CADE scope, not in the event scope.
        observation('x', 'c.org', event='e3', org='A', category='Payload delivery', age_days=400),
        observation('x2', 'c2.org', event='e3', org='A', category='Other', age_days=400),
    )
    statistics, evaluations, *_ = calculate(AS_OF, data, CONFIG)
    assert statistics['events_in_cade_scope'] == 3
    cade_norm = {e.event_uuid: e.cade_norm for e in evaluations}
    assert set(cade_norm.values()) == {0.0}  # e3 is the CADE maximum, outside the valid population
    by_value = {e.attribute_uuid: e for e in evaluations}
    assert sorted(e.event_norm for e in by_value.values()) == [0, 100]
    assert sorted(e.attribute_norm for e in by_value.values()) == [0, 100]
