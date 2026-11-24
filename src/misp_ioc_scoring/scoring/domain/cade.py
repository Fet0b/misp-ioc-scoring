"""CADE: category anomaly of an event (model `cade-seminormal-v2`).

`CS_i = (1 - exp(-n_i**2 / (2 * sigma_i**2))) * 100`, `CADE = sum(beta_i * CS_i)`,
then `CADE'` by MinMax between the events of the `cade` scope.
"""
import math
from statistics import pstdev


def event_key(observation):
    return (observation.source_instance_id, observation.event_uuid)


def counts_by_event(observations, categories) -> dict:
    """`n_i` per event over active `to_ids=true` observations (the `cade` scope)."""
    events = {}
    for observation in observations:
        if observation.removed_at is not None or observation.to_ids is not True:
            continue
        counts = events.setdefault(event_key(observation), dict.fromkeys(categories, 0))
        if observation.category in counts:
            counts[observation.category] += 1
    return events


def _transform(n, method):
    return math.log1p(n) if method == 'log_std' else float(n)


def _percentile(values, fraction):
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def estimate_sigma(events: dict, categories, estimator) -> tuple[dict, dict]:
    """σ per category with the configured estimator; returns (sigma, estimator inputs)."""
    sigmas, inputs = {}, {}
    for category in categories:
        values = [_transform(counts[category], estimator.method) for counts in events.values()]
        if not values:
            sigmas[category] = 0.0
            inputs[category] = {'events': 0}
            continue
        detail = {'events': len(values), 'max': max(values), 'mean': sum(values) / len(values)}
        if estimator.method == 'p95_winsorized':
            cap = _percentile(values, 0.95)
            values = [min(value, cap) for value in values]
            detail['cap'] = cap
        sigmas[category] = pstdev(values)
        inputs[category] = detail
    return sigmas, inputs


def category_score(n, sigma, estimator) -> float:
    x = _transform(n, estimator.method)
    if sigma == 0:
        if estimator.zero_rule == 'zero':
            return 0.0
        return 0.0 if x == 0 else (50.0 if estimator.zero_rule == 'half' else 100.0)
    return (1 - math.exp(-(x ** 2) / (2 * sigma ** 2))) * 100


def cade(counts: dict, sigmas: dict, beta: dict, estimator) -> float:
    return sum(beta[category] * category_score(counts[category], sigmas[category], estimator)
               for category in beta)
