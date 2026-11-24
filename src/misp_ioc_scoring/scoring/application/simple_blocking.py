"""Build an explainable decision per observation and known rejection."""
from collections import defaultdict
from datetime import timedelta

from misp_ioc_scoring.collection.api import warninglist_index

from ..domain.blocking import BlockingDecision, BlockingEvidence, BlockingReason
from ..domain.simple_blocking import decision


def evaluate(snapshot, as_of, max_age):
    """Yield one decision per known observation and rejection of a `CollectionSnapshot`."""
    by_source = defaultdict(list)
    for item in snapshot.warninglists:
        by_source[item.source_instance_id].append(item)
    indexes = {source: warninglist_index(entries, "strict") for source, entries in by_source.items()}
    empty = warninglist_index((), "strict")
    rejected = {(item.source_instance_id, item.attribute_uuid): item for item in snapshot.rejections}

    for observation in snapshot.observations:
        key = (observation.source_instance_id, observation.attribute_uuid)
        rejection = rejected.pop(key, None)
        source = snapshot.sources[key[0]]
        timestamp = observation.source_modified_at
        expires_at = as_of + max_age
        warning = None
        valid_until = source.valid_until(max_age)
        if valid_until is not None:
            expires_at = min(expires_at, valid_until)
            if source.trusted(as_of, max_age):
                warning = indexes.get(key[0], empty).match(
                    observation.misp_type, observation.normalized_value, "strict")
        reason = BlockingReason.REJECTED if rejection else decision(
            kind=observation.misp_type, to_ids=observation.to_ids,
            analysis=observation.event_analysis, removed=observation.removed_at is not None,
            warning=warning, timestamp=timestamp, as_of=as_of)
        yield BlockingDecision(
            source_instance_id=key[0], attribute_uuid=key[1],
            attribute_id=rejection.attribute_id if rejection else observation.attribute_id,
            block=reason == BlockingReason.ELIGIBLE, reason=reason, as_of=as_of,
            expires_at=min(expires_at, timestamp + timedelta(days=365)) if timestamp else expires_at,
            generation=source.generation,
            evidence=BlockingEvidence(kind=observation.misp_type, max_age_hours=max_age.total_seconds() / 3600,
                                      timestamp=timestamp, warning=warning, to_ids=observation.to_ids,
                                      analysis=observation.event_analysis))
    for key, item in rejected.items():
        yield BlockingDecision(
            source_instance_id=key[0], attribute_uuid=key[1], attribute_id=item.attribute_id,
            block=False, reason=BlockingReason.REJECTED, as_of=as_of, expires_at=as_of,
            generation=snapshot.sources[key[0]].generation,
            evidence=BlockingEvidence(kind=item.misp_type, max_age_hours=max_age.total_seconds() / 3600,
                                      rejected=True))
