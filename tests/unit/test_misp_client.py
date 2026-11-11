import pytest
from misp_ioc_scoring.shared.misp.client import MispClient
from misp_ioc_scoring.shared.errors import OperationalError


class FakeClient:
    def __init__(self, url, key, **kwargs):
        assert key == 'private'
        assert kwargs == {'ssl': True, 'timeout': 30, 'debug': False}

    def misp_instance_version(self):
        return {'version': '2.5.0'}

    def search(self, **kwargs):
        return {'errors': ['private']}


def test_client_resolves_secret_and_sanitizes_failures(monkeypatch):
    monkeypatch.setenv('MISP_KEY', 'private')
    client = MispClient('https://misp.example', 'env:MISP_KEY', 30, factory=FakeClient)
    assert client.version == '2.5.0'
    with pytest.raises(OperationalError, match='misp_request_failed') as error:
        client.call('search')
    assert 'private' not in str(error.value)


def test_http_requires_explicit_opt_in(monkeypatch):
    from misp_ioc_scoring.shared.errors import ConfigurationError
    monkeypatch.setenv('MISP_KEY', 'private')
    with pytest.raises(ConfigurationError, match='MISP_BASE_URL'):
        MispClient('http://192.0.2.1', 'env:MISP_KEY', 30, factory=FakeClient)
    assert MispClient('http://192.0.2.1', 'env:MISP_KEY', 30, factory=FakeClient,
                      allow_http=True).version == '2.5.0'


def test_version_property_supported_by_current_pymisp(monkeypatch):
    class PropertyClient(FakeClient):
        @property
        def misp_instance_version(self):
            return {'version': '2.5.51'}
    monkeypatch.setenv('MISP_KEY', 'private')
    assert MispClient('https://misp.example', 'env:MISP_KEY', 30,
                      factory=PropertyClient).version == '2.5.51'
