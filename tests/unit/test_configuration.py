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
        'CARIOCA_CONFIG_PATH': '/config/carioca.yaml',
        'MISP_REQUEST_TIMEOUT_SECONDS': '60',
        'MISP_PEERS_SECRET_REF': 'file:/run/secrets/peers',
    }


def test_scoring_flags_and_conditional_settings():
    env = {"DATABASE_URL": scoring_env()["DATABASE_URL"]}
    assert not load_configuration("scoring-sharing", env).simple_scoring_enabled
    with pytest.raises(ConfigurationError, match="SHARING_MISP_REQUIRES_SCORING_CARIOCA_ENABLED"):
        load_configuration("scoring-sharing", env | {"SHARING_MISP_ENABLED": "true"})
    with pytest.raises(ConfigurationError, match="SCORING_DAILY_CRON"):
        load_configuration("scoring-sharing", env | {"SCORING_SIMPLE_ENABLED": "true"})
    pihole = env | {"SHARING_PIHOLE_ENABLED": "true", "PIHOLE_SCORE_MODEL": "carioca"}
    for value in ("", "nan", "101"):
        with pytest.raises(ConfigurationError, match="PIHOLE_CARIOCA_MIN_SCORE"):
            load_configuration("scoring-sharing", pihole | {"PIHOLE_CARIOCA_MIN_SCORE": value})
    for value in ("0", "100"):
        with pytest.raises(ConfigurationError, match="PIHOLE_REQUIRES_SCORING_CARIOCA_ENABLED"):
            load_configuration("scoring-sharing", pihole | {"PIHOLE_CARIOCA_MIN_SCORE": value})
    active = env | {"SCORING_SIMPLE_ENABLED": "true", "SCORING_DAILY_CRON": "0 3 * * *",
                    "SHARING_PIHOLE_ENABLED": "true", "PIHOLE_URL": "https://dns.example",
                    "PIHOLE_INTERVAL_SECONDS": "60", "PIHOLE_PASSWORD_SECRET_REF": "env:PIHOLE_PASSWORD"}
    assert load_configuration("scoring-sharing", active).pihole_enabled


def test_export_physical_row_limit_is_accepted():
    assert load_configuration('tools', {
        'DATABASE_URL': 'postgresql+psycopg://observer@database/db',
        'EXPORT_OUTPUT_DIR': '/output', 'EXPORT_MAX_ROWS_PER_SHEET': '1048575',
    }).export_max_rows_per_sheet == 1048575


def test_carioca_flag_requires_readable_configuration_and_cron(tmp_path):
    env = {"DATABASE_URL": scoring_env()["DATABASE_URL"], "SCORING_CARIOCA_ENABLED": "true"}
    with pytest.raises(ConfigurationError, match="CARIOCA_CONFIG_PATH"):
        load_configuration("scoring-sharing", env)
    with pytest.raises(ConfigurationError, match="CARIOCA_CONFIG_PATH"):
        load_configuration("scoring-sharing", env | {"CARIOCA_CONFIG_PATH": str(tmp_path / "missing.yaml")})
    path = tmp_path / "carioca.yaml"
    path.write_text("{}")
    with pytest.raises(ConfigurationError, match="SCORING_DAILY_CRON"):
        load_configuration("scoring-sharing", env | {"CARIOCA_CONFIG_PATH": str(path)})
    config = load_configuration("scoring-sharing", env | {"CARIOCA_CONFIG_PATH": str(path),
                                                          "SCORING_DAILY_CRON": "0 3 * * *"})
    assert config.carioca_scoring_enabled and config.carioca_config_path == str(path)


def test_misp_sharing_requires_carioca_peers_and_retry_settings(tmp_path):
    path = tmp_path / "carioca.yaml"
    path.write_text("{}")
    env = {"DATABASE_URL": scoring_env()["DATABASE_URL"], "SCORING_CARIOCA_ENABLED": "true",
           "CARIOCA_CONFIG_PATH": str(path), "SCORING_DAILY_CRON": "0 3 * * *", "SHARING_MISP_ENABLED": "true"}
    with pytest.raises(ConfigurationError, match="MISP_PEERS_SECRET_REF"):
        load_configuration("scoring-sharing", env)
    with pytest.raises(ConfigurationError, match="MISP_PEERS_SECRET_REF"):
        load_configuration("scoring-sharing", env | {"MISP_PEERS_SECRET_REF": "/plain/path"})
    env["MISP_PEERS_SECRET_REF"] = "file:/run/secrets/peers"
    with pytest.raises(ConfigurationError, match="SHARING_INTERVAL_SECONDS"):
        load_configuration("scoring-sharing", env)
    complete = env | {"SHARING_INTERVAL_SECONDS": "300", "SHARING_RETRY_ATTEMPTS": "3",
                      "SHARING_RETRY_BACKOFF_SECONDS": "5", "MISP_REQUEST_TIMEOUT_SECONDS": "30"}
    config = load_configuration("scoring-sharing", complete)
    assert config.misp_sharing_enabled and config.sharing_retry_attempts == 3
    with pytest.raises(ConfigurationError, match="SHARING_RETRY_ATTEMPTS"):
        load_configuration("scoring-sharing", complete | {"SHARING_RETRY_ATTEMPTS": "0"})
