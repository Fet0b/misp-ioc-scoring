import json

import pytest

from misp_ioc_scoring.shared.errors import ConfigurationError
from misp_ioc_scoring.sharing.infrastructure.peer_configuration import parse_sharing_policy


def document(**peer):
    base = {'peer_id': 'peer-a', 'base_url': 'https://peer-a.example', 'credential_secret_ref': 'file:/run/peer-a',
            'minimum_priority_score': 70, 'distribution': '3'}
    return json.dumps({'local': {'base_url': 'https://local.example', 'credential_secret_ref': 'env:LOCAL'},
                       'peers': [base | peer]})


def parse(text):
    return parse_sharing_policy(text, interval_seconds=60, retry_attempts=3, retry_backoff_seconds=5)


@pytest.mark.parametrize('changes,code', [
    ({'minimum_priority_score': 101}, 'MISP_PEERS_MINIMUM_PRIORITY_SCORE'),
    ({'minimum_priority_score': -1}, 'MISP_PEERS_MINIMUM_PRIORITY_SCORE'),
    ({'minimum_priority_score': None}, 'MISP_PEERS_MINIMUM_PRIORITY_SCORE'),
    ({'peer_id': ''}, 'MISP_PEERS_PEER_ID'),
    ({'credential_secret_ref': 'plain-secret'}, 'MISP_PEERS_CREDENTIAL_SECRET_REF'),
    ({'base_url': 'http://peer-a.example'}, 'MISP_PEERS_BASE_URL'),
    ({'distribution': '0'}, 'MISP_PEERS_DISTRIBUTION'),
    ({'distribution': '4'}, 'MISP_PEERS_DISTRIBUTION'),
])
def test_invalid_peers_block_sharing(changes, code):
    with pytest.raises(ConfigurationError) as error:
        parse(document(**changes))
    assert error.value.setting == code
    assert 'plain-secret' not in str(error.value)


def test_missing_document_and_secret_references_stay_references():
    for text in ('', '{}', '{"local": {}, "peers": []}'):
        with pytest.raises(ConfigurationError):
            parse(text)
    policy = parse(document())
    assert policy.peers[0].credential_secret_ref == 'file:/run/peer-a'
    assert 'file:/run/peer-a' not in json.dumps(policy.public_view())


def test_policy_hash_changes_with_configuration():
    assert parse(document()).policy_hash == parse(document()).policy_hash
    assert parse(document()).policy_hash != parse(document(minimum_priority_score=71)).policy_hash
    assert parse(document()).policy_hash == parse(document(credential_secret_ref='env:OTHER')).policy_hash
