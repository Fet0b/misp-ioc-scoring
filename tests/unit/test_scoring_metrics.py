"""Scoring metrics from fixture tables (SQLite with an attached `scoring` schema)."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, MetaData, String, Table, Uuid, create_engine, event

from tools.metrics.scoring import scoring_metrics


def tables(metadata):
    runs = Table('execucao_scoring', metadata, Column('id', Uuid, primary_key=True), Column('as_of', DateTime),
                 Column('started_at', DateTime), Column('finished_at', DateTime), Column('status', String),
                 Column('observations_evaluated', Integer), Column('valid_population', Integer),
                 Column('excluded', Integer), Column('warnings', JSON), schema='scoring')
    exclusions = Table('exclusao_score', metadata, Column('scoring_run_id', Uuid), Column('ioc_id', Uuid),
                       Column('reason', String), schema='scoring')
    results = Table('resultado_score', metadata, Column('scoring_run_id', Uuid), Column('ioc_id', Uuid),
                    Column('priority_score', Float), Column('in_top_n', Boolean), schema='scoring')
    return runs, exclusions, results


def test_metrics_of_last_successful_run():
    engine = create_engine('sqlite://')
    event.listen(engine, 'connect', lambda connection, _: connection.execute("ATTACH ':memory:' AS scoring"))
    metadata = MetaData()
    runs, exclusions, results = tables(metadata)
    now = datetime(2026, 11, 24, 3, tzinfo=timezone.utc)
    old, current, failed = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(runs.insert(), [
            dict(id=old, as_of=now - timedelta(days=1), started_at=now - timedelta(days=1),
                 finished_at=now - timedelta(days=1), status='completed', observations_evaluated=1,
                 valid_population=1, excluded=0, warnings=[]),
            dict(id=current, as_of=now, started_at=now, finished_at=now + timedelta(seconds=90),
                 status='completed', observations_evaluated=5, valid_population=3, excluded=2,
                 warnings=['minmax_degenerate:cade']),
            dict(id=failed, as_of=now, started_at=now, finished_at=now + timedelta(hours=1), status='failed',
                 observations_evaluated=0, valid_population=0, excluded=0, warnings=[])])
        connection.execute(exclusions.insert(), [dict(scoring_run_id=current, ioc_id=uuid4(), reason=r)
                                                 for r in ('expired', 'expired', 'missing_data')])
        connection.execute(results.insert(), [dict(scoring_run_id=current, ioc_id=uuid4(), priority_score=p,
                                                   in_top_n=top) for p, top in ((90, True), (70, True), (10, False))])
        metrics = dict(scoring_metrics(connection, {'scoring.execucao_scoring': runs,
                                                    'scoring.exclusao_score': exclusions,
                                                    'scoring.resultado_score': results}))
    assert metrics['scoring:last_success:run_id'] == current
    assert metrics['scoring:last_success:duration_seconds'] == 90
    assert metrics['scoring:last_success:valid_population'] == 3
    assert metrics['scoring:last_success:exclusions:expired'] == 2
    assert metrics['scoring:last_success:exclusions:missing_data'] == 1
    assert metrics['scoring:last_success:warning:empty_population'] is False
    assert metrics['scoring:last_success:warning:minmax_degenerate'] == 'cade'
    assert metrics['scoring:last_success:top_n_cutoff'] == 70
    assert metrics['scoring:runs:failed'] == 1


def test_no_successful_run():
    engine = create_engine('sqlite://')
    event.listen(engine, 'connect', lambda connection, _: connection.execute("ATTACH ':memory:' AS scoring"))
    metadata = MetaData()
    runs, *_ = tables(metadata)
    with engine.begin() as connection:
        metadata.create_all(connection)
        assert scoring_metrics(connection, {'scoring.execucao_scoring': runs}) == [('scoring:last_success', 'none')]
    assert scoring_metrics(None, {}) == []
