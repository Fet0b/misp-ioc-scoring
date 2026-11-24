"""Explicit mapping of MISP inputs; unknown or missing values are never invented."""
THREAT_LEVEL = {'1': 100.0, '2': 66.0, '3': 33.0, '4': 0.0}
ANALYSIS = {'0': 0.0, '1': 50.0, '2': 100.0}


def threat_level(value) -> float | None:
    return THREAT_LEVEL.get(str(value)) if value is not None else None


def analysis(value) -> float | None:
    return ANALYSIS.get(str(value)) if value is not None else None


def missing_inputs(observation, categories) -> bool:
    """TL, SA, timestamp, category or organization missing or unknown (`missing_data`)."""
    return (threat_level(observation.event_threat_level) is None
            or analysis(observation.event_analysis) is None
            or observation.source_modified_at is None
            or observation.source_modified_at.utcoffset() is None
            or observation.category not in categories
            or observation.orgc_uuid is None)
