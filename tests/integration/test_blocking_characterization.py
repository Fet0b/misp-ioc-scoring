"""Characterization of simple blocking and the Pi-hole desired set (refactoring safety net).

The golden file freezes the observable behaviour before the DDD adjustment (D1–D9).
Timestamps are relative to a frozen `as_of`, because the effective-decision view
compares against the database clock. Regenerate only on purpose with `--update-golden`.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from sqlalchemy import create_engine, text

from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry
from misp_ioc_scoring.collection.infrastructure.persistence.models import EndpointModel
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.shared.database import transaction
from misp_ioc_scoring.sharing.infrastructure.persistence.pihole import Store

GOLDEN = Path(__file__).parent / 'fixtures' / 'blocking_characterization.json'
MAX_AGE_HOURS = 48


def uuid(name):
    return uuid5(NAMESPACE_URL, 'characterization:' + name)


class RecordingPiHole:
    def __init__(self):
        self.rows = {}
        self.adds = []

    def validate(self):
        pass

    def close(self):
        pass

    def lookup(self, host):
        return self.rows.get(host)

    def add(self, host, marker):
        self.adds.append(host)
        self.rows[host] = {'id': len(self.adds), 'comment': marker, 'groups': [0], 'enabled': True}

    def remove(self, host):
        del self.rows[host]


def frozen(as_of):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return as_of if tz else as_of.replace(tzinfo=None)
    return Frozen


def observation(source, name, value, kind='domain', *, age_days=10, to_ids=True, analysis='2',
                collected_at, as_of):
    timestamp = as_of - timedelta(days=age_days)
    return Observation(
        source_instance_id=source, event_uuid=uuid('event:' + source), attribute_uuid=uuid(name),
        raw_value=value, misp_type=kind, category='Network activity', to_ids=to_ids,
        orgc_uuid=uuid('org'), source_created_at=timestamp, source_modified_at=timestamp,
        collected_at=collected_at, event_threat_level='2', event_analysis=analysis,
        distribution='1', event_distribution='1', published=True)


def build_fixture(engine, as_of):
    collected = as_of - timedelta(hours=1)
    with transaction(engine) as session:
        session.get(EndpointModel, 'test').removal_ratio = 1
        session.add(EndpointModel(id='failed', base_url='https://failed.example',
                                  credential_secret_ref='env:KEY', interval_seconds=60,
                                  to_ids_only=True, removal_ratio=1))
    common = dict(collected_at=collected, as_of=as_of)
    trusted = [
        observation('test', 'eligible-domain', 'good.example', **common),
        observation('test', 'eligible-url', 'https://www.urlgood.example/path?q=1', 'url', **common),
        observation('test', 'removed', 'gone.example', **common),
        observation('test', 'type', 'host.example', 'hostname', **common),
        observation('test', 'to-ids', 'noids.example', to_ids=False, **common),
        observation('test', 'analysis', 'initial.example', analysis='1', **common),
        observation('test', 'warning-hostname', 'sub.allowed.example', **common),
        observation('test', 'warning-string', 'https://listed.example/exact', 'url', **common),
        observation('test', 'warning-cidr', 'https://192.0.2.5/x', 'url', **common),
        observation('test', 'expired', 'old.example', age_days=400, **common),
        observation('test', 'future', 'future.example', age_days=-1, **common),
        observation('test', 'rejected', 'bad domain', **common),
    ]
    warnings = [
        WarninglistEntry('test', 'allowed', 'hostname', 'allowed.example'),
        WarninglistEntry('test', 'urls', 'string', 'https://listed.example/exact'),
        WarninglistEntry('test', 'nets', 'cidr', '192.0.2.0/24'),
    ]
    repository = ObservationsRepository(engine, 'test')
    repository.apply(trusted, {o.attribute_uuid for o in trusted}, warnings, collected - timedelta(minutes=5))
    kept = [o for o in trusted if o.attribute_uuid != uuid('removed')]
    repository.apply(kept, {o.attribute_uuid for o in kept}, warnings, collected)

    failed = [
        observation('failed', 'failed-domain', 'failed.example', **common),
        observation('failed', 'failed-url', 'https://failed-url.example/', 'url', **common),
    ]
    other = ObservationsRepository(engine, 'failed')
    other.apply(failed, {o.attribute_uuid for o in failed},
                [WarninglistEntry('failed', 'patterns', 'regex', '.*')], collected)
    other.failed(collected + timedelta(minutes=1), 'test_failure')


def run_simple_blocking(engine, as_of, monkeypatch):
    from misp_ioc_scoring.entrypoints import scoring_sharing

    monkeypatch.setattr(scoring_sharing, 'datetime', frozen(as_of))
    scoring_sharing.run_simple_blocking(engine, MAX_AGE_HOURS)


def run_pihole(engine, store, as_of, monkeypatch):
    from misp_ioc_scoring.sharing.infrastructure.scheduling import scheduler

    monkeypatch.setattr(scheduler, 'datetime', frozen(as_of))
    remote = RecordingPiHole()
    scheduler.sync(engine, remote, store, MAX_AGE_HOURS)
    return remote


@pytest.fixture
def worker(engine):
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE scoring.execucao_bloqueio CASCADE'))
        connection.execute(text('TRUNCATE sharing.pihole_entry, sharing.pihole_attempt, sharing.pihole_policy'))
    worker = create_engine(engine.url.set(username='scoring_sharing'))
    try:
        yield worker
    finally:
        worker.dispose()
        with engine.begin() as connection:
            connection.execute(text('TRUNCATE scoring.execucao_bloqueio CASCADE'))
            connection.execute(text('TRUNCATE sharing.pihole_entry, sharing.pihole_attempt, sharing.pihole_policy'))


def test_blocking_and_pihole_characterization(engine, worker, monkeypatch, request):
    as_of = datetime.now(timezone.utc).replace(microsecond=0)
    build_fixture(engine, as_of)
    names = {uuid(name): name for name in (
        'eligible-domain', 'eligible-url', 'removed', 'type', 'to-ids', 'analysis',
        'warning-hostname', 'warning-string', 'warning-cidr', 'expired', 'future', 'rejected',
        'failed-domain', 'failed-url')}

    run_simple_blocking(worker, as_of, monkeypatch)
    store = Store(worker, 'https://pihole.example', 60, 'env:PIHOLE_TEST_PASSWORD')
    remote = run_pihole(worker, store, as_of, monkeypatch)

    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT source_instance_id, attribute_uuid, block, reason, expires_at, as_of
            FROM scoring.decisao_bloqueio
        """)).all()
    decisions = sorted([
        {'source_instance_id': source, 'attribute': names[attribute], 'block': block, 'reason': reason,
         'expires_after_seconds': (expires_at - as_of).total_seconds(),
         'as_of_matches': stored_as_of == as_of}
        for source, attribute, block, reason, expires_at, stored_as_of in rows
    ], key=lambda row: (row['source_instance_id'], row['attribute']))
    actual = {'decisions': decisions, 'pihole_hosts': sorted(remote.adds),
              'pihole_entries': {host: [{k: v for k, v in item.items() if k in ('kind', 'model', 'generation')}
                                        for item in entry['evidence']]
                                 for host, entry in sorted(store.entries().items())}}

    if request.config.getoption('--update-golden') or not GOLDEN.exists():
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(json.dumps(actual, indent=2, sort_keys=True) + '\n')
    assert actual == json.loads(GOLDEN.read_text())
