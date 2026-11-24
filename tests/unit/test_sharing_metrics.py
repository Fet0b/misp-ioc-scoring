from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Column, DateTime, MetaData, String, Table, Uuid, create_engine, event

from tools.metrics.sharing import sharing_metrics

NOW = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)


def database():
    engine = create_engine('sqlite://')

    def attach(connection, _):
        connection.execute("ATTACH ':memory:' AS sharing")
        connection.execute("ATTACH ':memory:' AS scoring")
    event.listen(engine, 'connect', attach)
    metadata = MetaData()
    attempts = Table('tentativa_compartilhamento', metadata, Column('peer_id', String), Column('ioc_id', Uuid),
                     Column('state', String), schema='sharing')
    policies = Table('politica_compartilhamento', metadata, Column('policy_hash', String),
                     Column('loaded_at', DateTime), schema='sharing')
    runs = Table('execucao_scoring', metadata, Column('id', Uuid), Column('status', String),
                 Column('finished_at', DateTime), schema='scoring')
    return engine, metadata, attempts, policies, runs


def test_states_policy_and_suspension():
    engine, metadata, attempts, policies, runs = database()
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(attempts.insert(), [dict(peer_id='a', ioc_id=uuid4(), state=s)
                                               for s in ('requested', 'requested', 'confirmed', 'failed', 'ambiguous')])
        connection.execute(policies.insert(), [dict(policy_hash='old', loaded_at=NOW - timedelta(days=1)),
                                               dict(policy_hash='new', loaded_at=NOW)])
        connection.execute(runs.insert(), [dict(id=uuid4(), status='completed', finished_at=NOW - timedelta(hours=49)),
                                           dict(id=uuid4(), status='failed', finished_at=NOW)])
        tables = {'sharing.tentativa_compartilhamento': attempts, 'sharing.politica_compartilhamento': policies,
                  'scoring.execucao_scoring': runs}
        metrics = dict(sharing_metrics(connection, tables, 48, NOW))
        assert metrics['sharing:a:requested'] == 2 and metrics['sharing:pending'] == 3
        assert metrics['sharing:failed'] == 1 and metrics['sharing:policy_hash'] == 'new'
        assert metrics['sharing:suspended'] is True
        connection.execute(runs.insert(), [dict(id=uuid4(), status='completed', finished_at=NOW - timedelta(hours=1))])
        assert dict(sharing_metrics(connection, tables, 48, NOW))['sharing:suspended'] is False
