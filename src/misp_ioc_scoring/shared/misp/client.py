"""Authenticated PyMISP boundary with safe operational failures."""
from urllib.parse import urlsplit
from misp_ioc_scoring.shared.configuration import resolve_secret
from misp_ioc_scoring.shared.errors import ConfigurationError, OperationalError


class MispClient:
    def __init__(self, base_url: str, credential_secret_ref: str, timeout: float,
                 *, factory=None, allow_http=False):
        parsed = urlsplit(base_url)
        if (parsed.scheme != 'https' and not (allow_http and parsed.scheme == 'http')) or not parsed.hostname or parsed.username or parsed.password:
            raise ConfigurationError('MISP_BASE_URL')
        if timeout <= 0:
            raise ConfigurationError('MISP_REQUEST_TIMEOUT_SECONDS')
        if factory is None:
            from pymisp import PyMISP
            factory = PyMISP
        secret = resolve_secret(credential_secret_ref)
        try:
            self._client = factory(base_url, secret.get_secret_value(), ssl=True,
                                   timeout=timeout, debug=False)
            version = self._client.misp_instance_version
            if callable(version):
                version = version()
            if not isinstance(version, dict) or not isinstance(version.get('version'), str):
                raise ValueError
            self.version = version['version']
        except Exception:
            raise OperationalError('misp_connection_failed') from None

    def call(self, operation: str, **kwargs):
        if operation not in {'search', 'warninglists', 'get_warninglist', 'get_event',
                             'push', 'get_job', 'get_server'}:
            raise OperationalError('misp_operation_not_allowed')
        try:
            response = getattr(self._client, operation)(**kwargs)
            if isinstance(response, dict) and ('errors' in response or response.get('error')):
                raise ValueError
            return response
        except Exception:
            raise OperationalError('misp_request_failed') from None
