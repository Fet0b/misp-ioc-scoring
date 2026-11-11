import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError


def test_roles_enforce_module_ownership(database_engine):
    with database_engine.begin() as connection:
        connection.execute(text('CREATE TABLE scoring.role_probe (id integer)'))
        connection.execute(text('CREATE TABLE sharing.role_probe (id integer)'))
    try:
        for role, allowed in [('collector', {'collection'}), ('scoring_sharing', {'scoring', 'sharing'}), ('observer', set())]:
            url = database_engine.url.set(username=role, password='test-only-password')
            engine = create_engine(url)
            try:
                for schema, table in [('collection', 'ioc'), ('scoring', 'role_probe'), ('sharing', 'role_probe')]:
                    with engine.begin() as connection:
                        if role != 'collector' or schema == 'collection':
                            connection.execute(text(f'SELECT * FROM {schema}.{table} LIMIT 1'))
                    if schema not in allowed:
                        with pytest.raises(DBAPIError):
                            with engine.begin() as connection:
                                connection.execute(text(f'DELETE FROM {schema}.{table}'))
                    else:
                        with engine.begin() as connection:
                            connection.execute(text(f'DELETE FROM {schema}.{table} WHERE false'))
            finally:
                engine.dispose()
    finally:
        with database_engine.begin() as connection:
            connection.execute(text('DROP TABLE scoring.role_probe'))
            connection.execute(text('DROP TABLE sharing.role_probe'))
