"""Build an explainable decision per observation and known rejection."""
from collections import defaultdict
from datetime import timedelta

from ..domain.simple_blocking import decision


def evaluate(snapshot, as_of, max_age, membership):
    endpoints, observations, warnings, rejections = snapshot
    by_source = defaultdict(list)
    for item in warnings:
        by_source[item.source_instance_id].append(item)
    rejected = {(item.source_instance_id, item.attribute_uuid): item for item in rejections}

    for observation, value in observations:
        key = (observation.source_instance_id, observation.attribute_uuid)
        rejection = rejected.pop(key, None)
        source = endpoints[key[0]]
        timestamp = observation.source_modified_at
        expires_at = as_of + max_age
        warning = None
        if source.generation and source.status == "completed" and source.last_success_at:
            expires_at = min(expires_at, source.last_success_at + max_age)
            if as_of < expires_at:
                warning = membership(by_source[key[0]], observation.misp_type, value)
        reason = "rejected" if rejection else decision(
            kind=observation.misp_type, to_ids=observation.to_ids,
            analysis=observation.event_analysis, removed=observation.removed_at is not None,
            warning=warning, timestamp=timestamp, as_of=as_of)
        yield dict(source_instance_id=key[0], attribute_uuid=key[1],
                   attribute_id=rejection.attribute_id if rejection else observation.attribute_id,
                   generation=source.generation, block=reason == "eligible", reason=reason, as_of=as_of,
                   expires_at=min(expires_at, timestamp + timedelta(days=365)) if timestamp else expires_at,
                   evidence=dict(timestamp=timestamp.isoformat() if timestamp else None,
                                 kind=observation.misp_type, warning=warning,
                                 max_age_hours=max_age.total_seconds() / 3600,
                                 to_ids=observation.to_ids, analysis=observation.event_analysis))
    for key, item in rejected.items():
        yield dict(source_instance_id=key[0], attribute_uuid=key[1], attribute_id=item.attribute_id,
                   generation=endpoints[key[0]].generation, block=False, reason="rejected",
                   as_of=as_of, expires_at=as_of, evidence=dict(kind=item.misp_type,
                                                  max_age_hours=max_age.total_seconds() / 3600))
