import pytest
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4
from misp_ioc_scoring.collection.domain.input_revision import inputs_changed
from misp_ioc_scoring.collection.domain.observations import Observation


def observation():
    now = datetime(2026, 11, 10, tzinfo=timezone.utc)
    return Observation('test', uuid4(), uuid4(), 'EXAMPLE.COM', 'domain', 'Network activity',
                       True, uuid4(), now, now, now, '2', '0', '5', '1', True)


def test_irrelevant_changes_do_not_advance_revision():
    before = observation()
    assert not inputs_changed(before, replace(before, tags=('new',), raw_value='example.com'))
    assert inputs_changed(before, replace(before, event_analysis='1'))
    assert inputs_changed(before, replace(before, removed_at=before.collected_at))


def test_published_advances_revision():
    before = observation()
    assert inputs_changed(before, replace(before, published=False))


@pytest.mark.parametrize('changes', [
    {'tags': ('other',)},
    {'collected_at': datetime(2026, 11, 11, tzinfo=timezone.utc)},
    {'distribution': '0'},
    {'raw_value': 'example.com'},
])
def test_collection_only_fields_do_not_advance_revision(changes):
    before = observation()
    assert not inputs_changed(before, replace(before, **changes))
