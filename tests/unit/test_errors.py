import json
import logging
from misp_ioc_scoring.shared.errors import ConfigurationError, OperationalError
from misp_ioc_scoring.shared.logging import JsonFormatter, register_secret


def test_operational_errors_have_safe_codes():
    assert str(ConfigurationError('DATABASE_URL')) == 'Invalid or missing configuration: DATABASE_URL'
    assert OperationalError('collection_failed').code == 'collection_failed'


def test_log_redacts_secrets_payload_and_exception():
    register_secret('private-key')
    record = logging.LogRecord('test', logging.ERROR, __file__, 1,
                               'failed %s', ('private-key',), None)
    record.token = 'private-key'
    record.raw_value = '=sensitive'
    record.event = 'collection_failed'
    result = json.loads(JsonFormatter().format(record))
    assert result['event'] == 'collection_failed'
    assert 'private-key' not in json.dumps(result)
    assert '=sensitive' not in json.dumps(result)
