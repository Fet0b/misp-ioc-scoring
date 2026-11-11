"""Shared persistence primitives; each module owns a distinct schema."""
from contextlib import contextmanager
from collections.abc import Iterator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import DeclarativeBase, Session
from .configuration import Configuration

SCHEMAS = ('collection', 'scoring', 'sharing')


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        'ix': 'ix_%(table_name)s_%(column_0_name)s',
        'uq': 'uq_%(table_name)s_%(column_0_name)s',
        'ck': 'ck_%(table_name)s_%(constraint_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    })


def module_schema(module: str) -> str:
    if module not in SCHEMAS:
        raise ValueError('Unknown module schema')
    return module


def engine_from_configuration(configuration: Configuration):
    return create_engine(configuration.database_url.get_secret_value(), pool_pre_ping=True,
                         hide_parameters=True, echo=False)


@contextmanager
def transaction(engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        with session.begin():
            yield session
