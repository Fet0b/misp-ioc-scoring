"""Collect `Observation`s into PostgreSQL through the real repository (integration tests)."""
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository


def uid(name):
    return uuid5(NAMESPACE_URL, 'integration:' + name)


def observation(name, value, kind='domain', *, as_of, event='e1', org='A', category='Network activity',
                to_ids=True, published=True, tl='2', sa='1', age_days=10, created_days=20, source='test',
                distribution='1', event_distribution='1', sharing_group_id=None, event_sharing_group_id=None):
    extra = {} if event_sharing_group_id is None else {'event_sharing_group_id': event_sharing_group_id}
    return Observation(
        source_instance_id=source, event_uuid=uid('event:' + event), attribute_uuid=uid('attr:' + name),
        raw_value=value, misp_type=kind, category=category, to_ids=to_ids,
        orgc_uuid=uid('org:' + org) if org else None,
        source_created_at=as_of - timedelta(days=created_days), source_modified_at=as_of - timedelta(days=age_days),
        collected_at=as_of, event_threat_level=tl, event_analysis=sa, distribution=distribution,
        event_distribution=event_distribution, published=published, sharing_group_id=sharing_group_id, **extra)


def collect(engine, observations, collected_at=None, source='test'):
    collected_at = collected_at or datetime.now(timezone.utc)
    items = [o for o in observations if o.source_instance_id == source]
    ObservationsRepository(engine, source).apply(items, {o.attribute_uuid for o in items}, [], collected_at)
    return collected_at
