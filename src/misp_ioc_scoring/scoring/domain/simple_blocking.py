"""Eligibility of one source observation at a fixed instant."""

def freshness(timestamp, as_of):
    if timestamp is None or timestamp.utcoffset() is None or as_of.utcoffset() is None:
        return None
    days = (as_of - timestamp).total_seconds() / 86400
    if days < 0:
        return None
    return 100 * (1 - (days / 365) ** (1 / 0.7)) if days < 365 else 0


def decision(*, kind, to_ids, analysis, removed, warning, timestamp, as_of):
    if removed:
        return "removed"
    if kind not in {"domain", "url"}:
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
