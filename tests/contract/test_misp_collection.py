from datetime import datetime, timezone
from uuid import uuid4
import pytest
from misp_ioc_scoring.collection.adapters.collection import CollectionSource
from misp_ioc_scoring.shared.errors import OperationalError


def event():
    return {'uuid': str(uuid4()), 'date': '2026-11-01', 'timestamp': '1793491200',
            'threat_level_id': '2', 'analysis': '0', 'distribution': '1', 'published': True,
            'Orgc': {'uuid': str(uuid4())},
            'Attribute': [{'uuid': str(uuid4()), 'type': 'domain', 'value': 'EXAMPLE.COM',
                           'category': 'Network activity', 'to_ids': True, 'timestamp': '1793491200'}]}


class Client:
    version = '2.5.0'
    def __init__(self, pages):
        self.pages = iter(pages)
        self.calls = []

    def call(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        if operation == 'search':
            return next(self.pages)
        return []


@pytest.mark.parametrize('wrap', [lambda e: [{'Event': e}], lambda e: {'response': [{'Event': e}]}])
def test_response_variants_pagination_and_provenance(wrap):
    payload = event()
    client = Client([wrap(payload), []])
    source = CollectionSource(client, 'test', True, page_size=1)
    observations = list(source.observations(datetime(2026, 11, 10, tzinfo=timezone.utc)))
    assert len(observations) == 1
    assert str(observations[0].orgc_uuid) == payload['Orgc']['uuid']
    assert observations[0].raw_value == 'EXAMPLE.COM'
    assert client.calls[1][1]['page'] == 2
    assert client.calls[0][1]['to_ids'] is True


def test_invalid_payload_raises_safe_error():
    client = Client([[{'Event': {'value': 'sensitive'}}]])
    with pytest.raises(OperationalError, match='misp_payload_invalid'):
        list(CollectionSource(client, 'test', True).observations(datetime.now(timezone.utc)))


def test_repeated_page_fails_instead_of_looping():
    payload = event()
    source = CollectionSource(Client([[{'Event': payload}], [{'Event': payload}]]), 'test', True, page_size=1)
    with pytest.raises(OperationalError, match='misp_pagination_repeated'):
        list(source.observations(datetime.now(timezone.utc)))


def test_enabled_warninglists_and_unsupported_entries():
    class WarningClient:
        def call(self, operation, **kwargs):
            if operation == 'warninglists':
                return [{'Warninglist': {'id': '1', 'enabled': '1'}},
                        {'Warninglist': {'id': '2', 'enabled': '0'}}]
            assert kwargs == {'warninglist': '1'}
            return {'Warninglist': {'name': 'patterns', 'type': 'regex',
                                    'WarninglistEntry': [{'value': '.*'}]}}
    entries = list(CollectionSource(WarningClient(), 'test', True).warninglists())
    assert len(entries) == 1
    assert entries[0].supported is False
