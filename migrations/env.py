"""Migrations require an administrator connection and runtime secret references."""
from alembic import context
from misp_ioc_scoring.shared.configuration import load_configuration
from misp_ioc_scoring.shared.database import Base, engine_from_configuration


def run_migrations_online():
    configuration = load_configuration('migration')
    engine = engine_from_configuration(configuration)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata,
                          include_schemas=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError('Migrations require an online PostgreSQL connection')
run_migrations_online()
