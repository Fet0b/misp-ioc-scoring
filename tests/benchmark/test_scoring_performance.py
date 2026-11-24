"""SC-011: the full CARIOCA recalculation of ~270 thousand IOCs ends within one hour.

Opt-in (slow): set RUN_BENCHMARK=true. With TEST_DATABASE_URL it also measures the
persistence through `SqlCariocaStore`. BENCHMARK_DATABASE_URL (a copy of the study MISP)
is not available in the repository; see research.md, "Benchmark do CARIOCA".
"""
import os
import time
from datetime import datetime, timezone

import pytest

from misp_ioc_scoring.scoring.application.score_population import calculate, run_carioca
from tests.benchmark.dataset import dataset
from tests.support.carioca import configuration

pytestmark = pytest.mark.skipif(os.environ.get('RUN_BENCHMARK') != 'true', reason='set RUN_BENCHMARK=true')
LIMIT_SECONDS = 3600


def test_in_memory_calculation_within_one_hour():
    as_of = datetime(2026, 11, 24, tzinfo=timezone.utc)
    snapshot = dataset(as_of)
    started = time.perf_counter()
    _, evaluations, results, exclusions, _ = calculate(as_of, snapshot, configuration(top_n=20_000))
    elapsed = time.perf_counter() - started
    print(f'\ncalculate: {len(snapshot.observations)} observations, {len(results)} IOCs in {elapsed:.1f}s')
    assert len(results) >= 250_000
    assert elapsed < LIMIT_SECONDS


def test_calculation_and_persistence_within_one_hour(database_engine):
    from sqlalchemy import text
    from misp_ioc_scoring.scoring.infrastructure.persistence.carioca import SqlCariocaStore
    from misp_ioc_scoring.shared.database import transaction

    as_of = datetime(2026, 11, 24, tzinfo=timezone.utc)
    snapshot = dataset(as_of)
    started = time.perf_counter()
    try:
        with transaction(database_engine) as session:
            summary = run_carioca(as_of, snapshot, configuration(top_n=20_000), SqlCariocaStore(session, snapshot))
        elapsed = time.perf_counter() - started
        print(f'\ncalculate + persist: {summary.valid_population} IOCs in {elapsed:.1f}s')
        assert elapsed < LIMIT_SECONDS
    finally:
        with database_engine.begin() as connection:
            connection.execute(text('TRUNCATE scoring.execucao_scoring, scoring.configuracao_carioca CASCADE'))
