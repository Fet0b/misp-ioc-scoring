"""Eligibility of one source observation at a fixed instant."""
from .blocking import BlockingReason as Reason
from .decay import DOMAIN

# URL shares the domain decay group in simple blocking (feature 002).
BLOCKABLE_TYPES = frozenset({"domain", "url"})


def freshness(timestamp, as_of):
    if timestamp is None or timestamp.utcoffset() is None or as_of.utcoffset() is None:
        return None
    return DOMAIN.freshness((as_of - timestamp).total_seconds() / 86400)


def decision(*, kind, to_ids, analysis, removed, warning, timestamp, as_of):
    if removed:
        return Reason.REMOVED
    if kind not in BLOCKABLE_TYPES:
        return Reason.TYPE
    if to_ids is not True:
        return Reason.TO_IDS
    if str(analysis) != "2":
        return Reason.ANALYSIS
    age_score = freshness(timestamp, as_of)
    if warning is None or age_score is None:
        return Reason.INDETERMINATE
    if warning:
        return Reason.WARNINGLIST
    return Reason.ELIGIBLE if age_score > 0 else Reason.EXPIRED
