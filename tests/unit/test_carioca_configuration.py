import json

import pytest

from misp_ioc_scoring.collection.api import CATEGORIES
from misp_ioc_scoring.scoring.application.score_population import calculate, run_carioca
from misp_ioc_scoring.scoring.domain.carioca_configuration import CariocaConfigurationError, parse_configuration
from tests.support.carioca import AS_OF, MemoryCariocaStore, config_dict, configuration, observation, snapshot


def parse(data):
    return parse_configuration(json.dumps(data), CATEGORIES)


def broken(**changes):
    data = config_dict()
    for key, value in changes.items():
        if value is None:
            data.pop(key)
        else:
            data[key] = value
    return data


@pytest.mark.parametrize('data,code', [
    (broken(alpha={'threat_level': -0.1, 'analysis': 0.7, 'cade': 0.4}), 'CARIOCA_ALPHA'),
    (broken(alpha={'threat_level': 0.5, 'analysis': 0.2, 'cade': 0.4}), 'CARIOCA_ALPHA'),
    (broken(top_n=None), 'CARIOCA_TOP_N'),
    (broken(sigma=None), 'CARIOCA_SIGMA'),
    (broken(sigma={'method': 'population_std', 'version': '1'}), 'CARIOCA_SIGMA_ZERO_RULE'),
    (broken(type_groups=None), 'CARIOCA_TYPE_GROUPS'),
    (broken(type_groups={'hash': ['md5'], 'ip': ['ip-src'], 'domain': ['domain', 'url']}), 'CARIOCA_TYPE_GROUPS'),
    (broken(aggregation='mean'), 'CARIOCA_AGGREGATION'),
    (broken(feed_rank=None), 'CARIOCA_FEED_RANK'),
    (broken(scoring_to_ids_only=False), 'CARIOCA_SCORING_TO_IDS_ONLY'),
])
def test_invalid_configuration(data, code):
    with pytest.raises(CariocaConfigurationError) as error:
        parse(data)
    assert error.value.code == code


def test_not_json_subset_is_rejected():
    with pytest.raises(CariocaConfigurationError, match='FORMAT'):
        parse_configuration('model_id: carioca-orgc-proxy-v3', CATEGORIES)


def test_content_hash_is_canonical():
    data = config_dict()
    reordered = dict(reversed(list(data.items())))
    assert parse(data).content_hash == parse(reordered).content_hash
    assert parse(data).content_hash != parse(config_dict(top_n=3)).content_hash


def test_unapproved_configuration_cannot_calculate():
    unapproved = configuration(approval={'approved': False, 'approved_by': None, 'approved_at': None,
                                         'evidence_ref': None})
    with pytest.raises(CariocaConfigurationError, match='NOT_APPROVED'):
        run_carioca(AS_OF, snapshot(observation('o')), unapproved, MemoryCariocaStore())


def test_identical_inputs_give_identical_results():
    data = snapshot(observation('a', 'a.org', org='A', event='e1'), observation('b', 'b.org', org='B', event='e2', sa='2'),
                    observation('c', 'c.org', org='A', event='e2', age_days=200))
    first = calculate(AS_OF, data, configuration())
    second = calculate(AS_OF, data, configuration())
    assert first == second
