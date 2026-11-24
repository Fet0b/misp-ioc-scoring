from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, MetaData, String, Table, Uuid, create_engine, event

from tools.metrics.candidates import candidate_metrics


def test_pending_oldest_age_and_last_error():
    engine = create_engine('sqlite://')
    event.listen(engine, 'connect', lambda connection, _: connection.execute("ATTACH ':memory:' AS scoring"))
    metadata = MetaData()
    table = Table('candidato_rescoring', metadata, Column('ioc_id', Uuid, primary_key=True),
                  Column('pending', Boolean), Column('input_revision', Integer), Column('marked_at', DateTime),
                  Column('last_attempt_at', DateTime), Column('last_error', String), schema='scoring')
    now = datetime(2026, 11, 24, 12, tzinfo=timezone.utc)
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(table.insert(), [
            dict(ioc_id=uuid4(), pending=True, input_revision=1, marked_at=now - timedelta(hours=2),
                 last_attempt_at=now - timedelta(hours=1), last_error='carioca_run_failed'),
            dict(ioc_id=uuid4(), pending=True, input_revision=1, marked_at=now - timedelta(minutes=5),
                 last_attempt_at=None, last_error=None),
            dict(ioc_id=uuid4(), pending=False, input_revision=1, marked_at=now - timedelta(days=3),
                 last_attempt_at=now - timedelta(days=2), last_error=None)])
        metrics = dict(candidate_metrics(connection, {'scoring.candidato_rescoring': table}, now))
    assert metrics['candidates:pending'] == 2
    assert metrics['candidates:oldest_pending_age_seconds'] == 7200
    assert metrics['candidates:last_error'] == 'carioca_run_failed'
    assert candidate_metrics(None, {}) == []
