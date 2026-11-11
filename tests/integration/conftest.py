"""PostgreSQL tests require a disposable database with a name ending in _test."""
import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope='session')
def database_engine():
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('Set TEST_DATABASE_URL to a disposable PostgreSQL database')
    if not make_url(url).database.endswith('_test'):
        pytest.fail('TEST_DATABASE_URL database must end in _test')
    engine = create_engine(url, hide_parameters=True)
    with engine.connect() as connection:
        if connection.scalar(text("SELECT to_regclass('public.alembic_version')")):
            pytest.fail('Integration tests require a fresh disposable database')
    previous = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url
    keys = []
    for role in ('COLLECTOR', 'SCORING', 'OBSERVER'):
        key = role + '_DB_PASSWORD_SECRET_REF'
        keys.append((key, os.environ.get(key)))
        os.environ[key] = 'env:MISP_TEST_ROLE_PASSWORD'
    os.environ['MISP_TEST_ROLE_PASSWORD'] = 'test-only-password'
    config = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))
    try:
        command.upgrade(config, 'head')
        yield engine
    finally:
        command.downgrade(config, 'base')
        with engine.begin() as connection:
            connection.execute(text('DROP TABLE IF EXISTS alembic_version'))
        engine.dispose()
        if previous is None:
            os.environ.pop('DATABASE_URL', None)
        else:
            os.environ['DATABASE_URL'] = previous
        for key, value in keys:
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        os.environ.pop('MISP_TEST_ROLE_PASSWORD', None)


@pytest.fixture
def engine(database_engine):
    from misp_ioc_scoring.collection.infrastructure.persistence.models import EndpointModel
    from misp_ioc_scoring.shared.database import transaction
    with database_engine.begin() as connection:
        connection.execute(text('TRUNCATE collection.endpoint_coleta, collection.ioc CASCADE'))
    with transaction(database_engine) as session:
        session.add(EndpointModel(id='test', base_url='https://misp.example',
                                 credential_secret_ref='file:/run/secrets/key',
                                 interval_seconds=60, to_ids_only=True, removal_ratio=.2))
    return database_engine
