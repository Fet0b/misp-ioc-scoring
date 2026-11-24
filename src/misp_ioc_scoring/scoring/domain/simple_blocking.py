"""Eligibility of one source observation at a fixed instant."""
from .decay import DOMAIN

# URL shares the domain decay group in simple blocking (feature 002).
BLOCKABLE_TYPES = frozenset({"domain", "url"})


def freshness(timestamp, as_of):
    if timestamp is None or timestamp.utcoffset() is None or as_of.utcoffset() is None:
        return None
    return DOMAIN.freshness((as_of - timestamp).total_seconds() / 86400)


def decision(*, kind, to_ids, analysis, removed, warning, timestamp, as_of):
    if removed:
        return "removed"
    if kind not in BLOCKABLE_TYPES:
        return "type"
    if to_ids is not True:
        return "to_ids"
    if str(analysis) != "2":
        return "analysis"
    age_score = freshness(timestamp, as_of)
    if warning is None or age_score is None:
        return "indeterminate"
    if warning:
        return "warninglist"
    return "eligible" if age_score > 0 else "expired"
