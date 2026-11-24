"""Synthetic population shaped like the study MISP (SC-011 benchmark).

~270 thousand valid domain IOCs, 27 organizations with two of them holding about 92 %
of the pairs, events of very different sizes and ages spread over a year.
"""
import random
from datetime import timedelta
from uuid import UUID

from misp_ioc_scoring.collection.api import CATEGORIES
from misp_ioc_scoring.collection.domain.snapshots import CollectionSnapshot, ObservationSnapshot, SourceSnapshot

CATEGORY_WEIGHTS = {'Network activity': 70, 'Payload delivery': 12, 'External analysis': 8, 'Other': 4,
                    'Artifacts dropped': 2, 'Payload installation': 1}


def _uuid(generator):
    return UUID(int=generator.getrandbits(128), version=4)


def dataset(as_of, iocs=270_000, organizations=27, events=1_600, seed=20261124):
    generator = random.Random(seed)
    orgs = [_uuid(generator) for _ in range(organizations)]
    org_weights = [46, 46] + [8 / (organizations - 2)] * (organizations - 2)
    event_ids = [_uuid(generator) for _ in range(events)]
    event_meta = {e: (generator.choice('1234'), generator.choice('012'), generator.choices(orgs, org_weights)[0],
                      as_of - timedelta(days=generator.uniform(0, 365))) for e in event_ids}
    # Few huge events (Maltrail-like) and many small ones.
    event_weights = [generator.paretovariate(1.2) for _ in event_ids]
    categories = list(CATEGORY_WEIGHTS) + [c for c in CATEGORIES if c not in CATEGORY_WEIGHTS]
    category_weights = list(CATEGORY_WEIGHTS.values()) + [0.2] * (len(categories) - len(CATEGORY_WEIGHTS))
    observations = []
    chosen_events = generator.choices(event_ids, event_weights, k=iocs)
    chosen_categories = generator.choices(categories, category_weights, k=iocs)
    for index in range(iocs):
        event = chosen_events[index]
        tl, sa, org, created = event_meta[event]
        value = f'host{index}.example{index % 97}.org'
        observations.append(ObservationSnapshot(
            source_instance_id='bench', event_uuid=event, attribute_uuid=_uuid(generator), raw_value=value,
            misp_type='domain', category=chosen_categories[index], to_ids=True, orgc_uuid=org,
            source_created_at=created, source_modified_at=created + timedelta(days=generator.uniform(0, 1)),
            collected_at=as_of, event_threat_level=tl, event_analysis=sa, distribution='1',
            event_distribution='1', published=True, ioc_id=_uuid(generator), normalized_value=value,
            input_revision=1))
    # A second publisher for 5 % of the values builds the FeedRank graph.
    for item in generator.sample(observations, iocs // 20):
        org = generator.choices(orgs, org_weights)[0]
        observations.append(ObservationSnapshot(**{**item.__dict__, 'attribute_uuid': _uuid(generator),
                                                   'orgc_uuid': org, 'event_uuid': generator.choice(event_ids),
                                                   'source_created_at': item.source_created_at + timedelta(days=1)}))
    sources = {'bench': SourceSnapshot('bench', 1, 'completed', as_of)}
    return CollectionSnapshot(sources, tuple(observations), (), ())
