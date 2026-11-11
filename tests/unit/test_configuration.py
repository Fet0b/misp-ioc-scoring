import pytest
from misp_ioc_scoring.shared.configuration import load_configuration, resolve_secret
from misp_ioc_scoring.shared.errors import ConfigurationError


def collector_env():
    return {
        'DATABASE_URL': 'postgresql+psycopg://collector@database/db',
        'MISP_ENDPOINTS_SECRET_REF': 'file:/run/secrets/endpoints',
        'COLLECTION_CADENCE_SECRET_REF': 'file:/run/secrets/cadence',
        'COLLECTION_OVERLAP_MINUTES': '5',
        'COLLECTION_RETRY_ATTEMPTS': '3',
        'COLLECTION_RETRY_BACKOFF_SECONDS': '2',
        'RECONCILE_MAX_REMOVAL_RATIO': '0.2',
        'MISP_REQUEST_TIMEOUT_SECONDS': '30',
    }


def test_collector_requires_only_its_own_settings():
    configuration = load_configuration('collector', collector_env())
    assert configuration.misp_to_ids_only is True
    assert configuration.score_max_age_hours == 48
    assert configuration.export_max_rows_per_sheet == 1000000
    assert configuration.collection_retry_attempts == 3


@pytest.mark.parametrize('key,value', [
    ('COLLECTION_RETRY_ATTEMPTS', '0'),
    ('COLLECTION_OVERLAP_MINUTES', '-1'),
    ('RECONCILE_MAX_REMOVAL_RATIO', '1.1'),
    ('MISP_TO_IDS_ONLY', 'yes'),
    ('MISP_REQUEST_TIMEOUT_SECONDS', 'nan'),
    ('DATABASE_URL', 'sqlite:///test.db'),
    ('EXPORT_MAX_ROWS_PER_SHEET', '1048576'),
])
def test_invalid_settings_do_not_echo_values(key, value):
    env = collector_env() | {key: value}
    with pytest.raises(ConfigurationError) as error:
        load_configuration('collector', env)
    assert key in str(error.value)
    assert 'sqlite:///test.db' not in str(error.value)


def test_missing_required_setting():
    env = collector_env()
    del env['COLLECTION_RETRY_ATTEMPTS']
    with pytest.raises(ConfigurationError, match='COLLECTION_RETRY_ATTEMPTS'):
        load_configuration('collector', env)


def test_configuration_is_snapshot_and_hides_database_password():
    env = collector_env() | {'DATABASE_URL': 'postgresql+psycopg://u:private@database/db'}
    configuration = load_configuration('collector', env)
    env['COLLECTION_RETRY_ATTEMPTS'] = '9'
    assert configuration.collection_retry_attempts == 3
    assert 'private' not in repr(configuration)
    with pytest.raises(Exception):
        configuration.collection_retry_attempts = 9


def test_secret_references(tmp_path):
    path = tmp_path / 'key'
    path.write_text('private\n')
    assert resolve_secret(f'file:{path}').get_secret_value() == 'private'
    assert resolve_secret('env:KEY', {'KEY': 'private'}).get_secret_value() == 'private'
    for reference in ['private', 'env:MISSING', 'file:/does/not/exist']:
        with pytest.raises(ConfigurationError) as error:
            resolve_secret(reference, {})
        assert reference not in str(error.value)


def test_tools_do_not_require_worker_settings():
    configuration = load_configuration('tools', {
        'DATABASE_URL': 'postgresql+psycopg://observer@database/db',
        'EXPORT_OUTPUT_DIR': '/output',
    })
    assert configuration.export_max_rows_per_sheet == 1000000


def scoring_env():
    return {
        'DATABASE_URL': 'postgresql+psycopg://scoring_sharing@database/db',
        'SCORING_DAILY_CRON': '0 3 * * *', 'SHARING_INTERVAL_SECONDS': '300',
        'SHARING_RETRY_ATTEMPTS': '3', 'SHARING_RETRY_BACKOFF_SECONDS': '5',
        'CARIOCA_TOP_N': '100', 'CARIOCA_CONFIG_PATH': '/config/carioca.yaml',
        'MISP_REQUEST_TIMEOUT_SECONDS': '60',
        'MISP_PEERS_SECRET_REF': 'file:/run/secrets/peers',
        'PEER_MINIMUM_SCORES_SECRET_REF': 'file:/run/secrets/minimums',
        'PEER_CREDENTIALS_SECRET_REF': 'file:/run/secrets/credentials',
    }


def test_scoring_requires_explicit_top_n_and_valid_schedule():
    assert load_configuration('scoring-sharing', scoring_env()).carioca_top_n == 100
    for key, value in [('CARIOCA_TOP_N', ''), ('SCORING_DAILY_CRON', 'invalid'),
                       ('SHARING_RETRY_ATTEMPTS', '0'), ('PEER_CREDENTIALS_SECRET_REF', 'raw-secret')]:
        with pytest.raises(ConfigurationError, match=key):
            load_configuration('scoring-sharing', scoring_env() | {key: value})


def test_export_physical_row_limit_is_accepted():
    assert load_configuration('tools', {
        'DATABASE_URL': 'postgresql+psycopg://observer@database/db',
        'EXPORT_OUTPUT_DIR': '/output', 'EXPORT_MAX_ROWS_PER_SHEET': '1048575',
    }).export_max_rows_per_sheet == 1048575
