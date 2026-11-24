"""Builders for CARIOCA tests: configuration text and collection snapshots."""
import json
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

from misp_ioc_scoring.collection.api import CATEGORIES
from misp_ioc_scoring.collection.domain.snapshots import CollectionSnapshot, ObservationSnapshot, SourceSnapshot
from misp_ioc_scoring.scoring.domain.carioca_configuration import parse_configuration

AS_OF = datetime(2026, 11, 10, 18, 11, tzinfo=timezone.utc)
HASH_TYPES = ['md5', 'sha1', 'sha256', 'sha512', 'ssdeep', 'imphash', 'tlsh', 'filename', 'malware-sample',
              'filename|md5', 'filename|sha1', 'filename|sha256', 'filename|sha512']


def config_dict(**overrides):
    data = {
        'model_id': 'carioca-orgc-proxy-v3', 'cade_id': 'cade-seminormal-v2', 'version': 'test-1',
        'alpha': {'threat_level': 0.4, 'analysis': 0.2, 'cade': 0.4},
        'beta': {category: 1 / 16 for category in CATEGORIES},
        'sigma': {'method': 'population_std', 'version': 'test', 'zero_rule': 'indicator'},
        'decay_groups': {'hash': {'D': 2, 'T': 60}, 'ip': {'D': 1.5, 'T': 7}, 'domain': {'D': 0.7, 'T': 365}},
        'type_groups': {'hash': HASH_TYPES, 'ip': ['ip-src', 'ip-dst', 'ip-src|port', 'ip-dst|port'],
                        'domain': ['domain', 'hostname', 'domain|ip']},
        'scoring_to_ids_only': True, 'aggregation': 'max-observation',
        'normalization_scopes': {'cade': 'events_with_to_ids_observation', 'event': 'events_with_valid_observation',
                                 'attribute': 'valid_observations', 'source': 'valid_observations'},
        'feed_rank': {'method': 'orgc-proxy', 'damping': 0.85, 'iterations': 50, 'dangling': 'uniform',
                      'contribution_weight': 50, 'pagerank_weight': 50},
        'spotis': {'weights': {'source': 1 / 3, 'event': 1 / 3, 'attribute': 1 / 3}, 'ideal': 100},
        'top_n': 2,
        'approval': {'approved': True, 'approved_by': 'tests', 'approved_at': '2026-11-24T00:00:00+00:00',
                     'evidence_ref': 'tests'},
    }
    data.update(overrides)
    return data


def configuration(**overrides):
    return parse_configuration(json.dumps(config_dict(**overrides)), CATEGORIES)


def uid(name):
    return uuid5(NAMESPACE_URL, 'carioca-test:' + name)


def observation(name, value='example.org', kind='domain', *, ioc=None, event='e1', org='org-a', source='s1',
                category='Network activity', to_ids=True, published=True, tl='2', sa='1', age_days=10.0,
                created_days=20.0, removed=False, revision=1, distribution='1', event_distribution='1',
                sharing_group_id=None):
    return ObservationSnapshot(
        source_instance_id=source, event_uuid=uid('event:' + event), attribute_uuid=uid('attr:' + name),
        raw_value=value, misp_type=kind, category=category, to_ids=to_ids,
        orgc_uuid=uid('org:' + org) if org else None,
        source_created_at=AS_OF - timedelta(days=created_days),
        source_modified_at=AS_OF - timedelta(days=age_days), collected_at=AS_OF,
        event_threat_level=tl, event_analysis=sa, distribution=distribution,
        event_distribution=event_distribution, published=published, sharing_group_id=sharing_group_id,
        removed_at=AS_OF if removed else None, ioc_id=uid('ioc:' + (ioc or kind + ':' + value)),
        normalized_value=value, input_revision=revision)


def snapshot(*observations, warninglists=()):
    sources = {o.source_instance_id for o in observations} | {'s1'}
    return CollectionSnapshot({s: SourceSnapshot(s, 1, 'completed', AS_OF) for s in sources},
                              tuple(observations), tuple(warninglists), ())


class MemoryCariocaStore:
    def __init__(self):
        self.started, self.stats, self.evals, self.res, self.excl, self.summary = None, None, [], [], [], None

    def start(self, run_id, as_of, configuration):
        self.started = (run_id, as_of, configuration.content_hash)

    def statistics(self, run_id, statistics):
        self.stats = statistics

    def evaluations(self, run_id, evaluations):
        self.evals.extend(evaluations)

    def results(self, run_id, results):
        self.res.extend(results)

    def exclusions(self, run_id, exclusions):
        self.excl.extend(exclusions)

    def finish(self, run_id, summary):
        self.summary = summary
