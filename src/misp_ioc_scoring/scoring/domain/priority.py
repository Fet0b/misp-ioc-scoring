"""MinMax normalization and SPOTIS combination of the Priority score."""
from .carioca_configuration import DEGENERATE_MINMAX_VALUE


def minmax(values: dict) -> tuple[dict, bool, float | None, float | None]:
    """Normalize to 0–100; maximum = minimum gives 50 and reports `degenerate`.

    Returns (normalized, degenerate, minimum, maximum).
    """
    if not values:
        return {}, False, None, None
    low, high = min(values.values()), max(values.values())
    if high == low:
        return dict.fromkeys(values, DEGENERATE_MINMAX_VALUE), True, low, high
    span = high - low
    return {key: (value - low) / span * 100 for key, value in values.items()}, False, low, high


def spotis(scores: dict, weights: dict, ideal: float = 100.0, bounds=(0.0, 100.0)) -> float:
    """SPOTIS against the ideal point; with ideal 100, bounds 0–100 it is the weighted mean."""
    low, high = bounds
    distance = sum(weights[key] * abs(scores[key] - ideal) / (high - low) for key in weights)
    return (1 - distance) * 100
