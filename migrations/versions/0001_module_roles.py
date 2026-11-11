"""Create restricted runtime roles; passwords come only from secret references."""
import os
from alembic import op
from psycopg import sql
from misp_ioc_scoring.shared.configuration import resolve_secret
from misp_ioc_scoring.shared.errors import ConfigurationError

revision = '0001'
down_revision = '0000'
branch_labels = None
depends_on = None

ROLES = {
    'collector': 'COLLECTOR_DB_PASSWORD_SECRET_REF',
    'scoring_sharing': 'SCORING_DB_PASSWORD_SECRET_REF',
    'observer': 'OBSERVER_DB_PASSWORD_SECRET_REF',
}


def upgrade():
    # Use the driver's safe SQL composition; passwords never pass through SQLAlchemy logs.
    connection = op.get_bind().connection.driver_connection
    with connection.cursor() as cursor:
        for role, setting in ROLES.items():
            reference = os.environ.get(setting)
            if not reference:
                raise ConfigurationError(setting)
            password = resolve_secret(reference).get_secret_value()
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT').format(
                sql.Identifier(role), sql.Literal(password)))
        cursor.execute('ALTER ROLE observer SET default_transaction_read_only = on')
        for schema in ('collection', 'scoring', 'sharing'):
            cursor.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(schema)))
            writer = 'collector' if schema == 'collection' else 'scoring_sharing'
            readers = ['observer'] + (['scoring_sharing'] if schema == 'collection' else [])
            for role in [writer, *readers]:
                cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(
                    sql.Identifier(schema), sql.Identifier(role)))
                table_privileges = sql.SQL('SELECT, INSERT, UPDATE, DELETE') if role == writer else sql.SQL('SELECT')
                cursor.execute(sql.SQL('GRANT {} ON ALL TABLES IN SCHEMA {} TO {}').format(
                    table_privileges, sql.Identifier(schema), sql.Identifier(role)))
                cursor.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT {} ON TABLES TO {}').format(
                    sql.Identifier(schema), table_privileges, sql.Identifier(role)))
            cursor.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}').format(
                sql.Identifier(schema), sql.Identifier(writer)))
            cursor.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT USAGE, SELECT ON SEQUENCES TO {}').format(
                sql.Identifier(schema), sql.Identifier(writer)))


def downgrade():
    connection = op.get_bind().connection.driver_connection
    with connection.cursor() as cursor:
        for role in reversed(ROLES):
            cursor.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
