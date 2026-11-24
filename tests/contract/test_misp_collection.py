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


def test_object_attributes_preserve_identity_category_and_attribute_timestamp():
    payload = event()
    attribute = payload["Attribute"][0]
    payload["Object"] = [{"Attribute": [dict(attribute, uuid=str(uuid4()), id="42",
                                             timestamp="1793491201", category="Other", to_ids=False)]}]
    client = Client([[{"Event": payload}], []])
    observations = list(CollectionSource(client, "test", False, page_size=1).observations(
        datetime.now(timezone.utc)))
    original, nested = observations
    assert original.attribute_id is None
    assert nested.attribute_id == 42
    assert str(nested.attribute_uuid) == payload["Object"][0]["Attribute"][0]["uuid"]
    assert nested.category == "Other"
    assert nested.source_modified_at.timestamp() == 1793491201
    assert not nested.to_ids
    assert "to_ids" not in client.calls[0][1]
    assert list(CollectionSource(client, "test", False).warninglists()) == []


def test_invalid_attribute_does_not_echo_raw_value():
    payload = event()
    payload["Attribute"][0].update(uuid="invalid", value="private-indicator")
    with pytest.raises(OperationalError) as caught:
        list(CollectionSource(Client([[payload]]), "test", True).observations(datetime.now(timezone.utc)))
    assert "private-indicator" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_incomplete_enabled_warninglist_is_not_an_empty_list():
    class IncompleteWarningClient:
        def call(self, operation, **kwargs):
            if operation == "warninglists":
                return [{"Warninglist": {"enabled": True, "id": 1}}]
            return {"errors": ["private-list"]}

    with pytest.raises(OperationalError, match="^misp_warninglists_invalid$"):
        list(CollectionSource(IncompleteWarningClient(), "test", False).warninglists())


def test_inherited_distribution_keeps_event_sharing_group():
    payload = event()
    payload.update(distribution='4', sharing_group_id='7')
    payload['Attribute'][0].update(distribution='5')
    source = CollectionSource(Client([[{'Event': payload}], []]), 'test', True, page_size=1)
    observation = list(source.observations(datetime(2026, 11, 10, tzinfo=timezone.utc)))[0]
    assert observation.event_sharing_group_id == '7'
    assert observation.distribution == '5' and observation.event_distribution == '4'
