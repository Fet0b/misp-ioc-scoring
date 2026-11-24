"""Event and Attribute components, always against `as_of`, never the clock."""


def age_days(timestamp, as_of) -> float:
    return (as_of - timestamp).total_seconds() / 86400


def attribute_score(group, timestamp, as_of) -> float | None:
    """`A` by the decay group; None for a future timestamp."""
    return group.freshness(age_days(timestamp, as_of))


def event_score(threat_level, analysis, cade_norm, alpha) -> float:
    """`E = 0.4·TL + 0.2·SA + 0.4·CADE'` with the configured `alpha`."""
    return alpha['threat_level'] * threat_level + alpha['analysis'] * analysis + alpha['cade'] * cade_norm
