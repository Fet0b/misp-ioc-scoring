from dataclasses import replace
from datetime import timedelta

import pytest

from misp_ioc_scoring.collection.domain.indicators import IOC
from misp_ioc_scoring.collection.domain.observations import Observation
from misp_ioc_scoring.collection.domain.reconciliation import reconcile_snapshot
from misp_ioc_scoring.shared.errors import OperationalError
from tests.support.carioca import AS_OF, observation as stored_observation, uid


def received(name, value='example.org', **changes):
    item = stored_observation(name, value)
    fields = {k: getattr(item, k) for k in Observation.__dataclass_fields__}
    return replace(Observation(**fields), **changes)


def stored(name, value='example.org', **changes):
    return replace(stored_observation(name, value), **changes)


def plan(existing, incoming, ratio=1.0, iocs=None):
    return reconcile_snapshot({o.attribute_uuid: o for o in existing}, incoming, AS_OF, ratio,
                              iocs=iocs if iocs is not None else {('domain', 'example.org'): uid('ioc:domain:example.org')},
                              new_id=lambda: uid('new'))


def test_older_update_is_ignored():
    old = stored('a')
    changes = plan([old], [received('a', source_modified_at=old.source_modified_at - timedelta(days=1),
                                    event_analysis='2')])
    assert not (changes.updates or changes.inserts or changes.revised_iocs)


def test_invalid_value_becomes_rejection_and_removes_active_observation():
    active = stored('a')
    changes = plan([active], [received('a', raw_value='bad value')])
    assert [r.reason for r in changes.rejections] == ['invalid']
    assert changes.removals == {active.attribute_uuid} and changes.revised_iocs == {active.ioc_id}
    assert [r.reason for r in plan([], [received('b', misp_type='comment', raw_value='x')]).rejections] == ['unsupported']


def test_valid_value_creates_ioc_by_identity_and_resolves_rejection():
    changes = plan([], [received('a', raw_value='NEW.example.org', misp_type='domain')], iocs={})
    assert changes.new_iocs[0].ioc == IOC('domain', 'new.example.org')
    assert changes.inserts[0][1] == uid('new') and changes.revised_iocs == {uid('new')}
    assert changes.resolved_rejections == {uid('attr:a')}
    same = plan([], [received('b', raw_value='EXAMPLE.ORG')])
    assert not same.new_iocs and same.inserts[0][1] == uid('ioc:domain:example.org')


def test_missing_observation_is_removed():
    gone = stored('gone')
    changes = plan([gone, stored('kept')], [received('kept')])
    assert changes.removals == {gone.attribute_uuid}
    assert changes.revised_iocs == {gone.ioc_id}


def test_relevant_and_irrelevant_changes():
    current = stored('a')
    assert plan([current], [received('a', tags=('new',))]).revised_iocs == set()
    assert plan([current], [received('a', event_analysis='2')]).revised_iocs == {current.ioc_id}
    assert plan([current], [received('a', published=False)]).revised_iocs == {current.ioc_id}


def test_ioc_change_marks_old_and_new():
    current = stored('a')
    changes = plan([current], [received('a', raw_value='other.example.org')], iocs={})
    assert changes.revised_iocs == {current.ioc_id, uid('new')}
    assert changes.updates[0][1] == uid('new')


def test_mass_removal_refuses_reconciliation():
    existing = [stored(f'o{n}', f'h{n}.example.org') for n in range(10)]
    plan(existing, [received(f'o{n}', f'h{n}.example.org') for n in range(8)], ratio=0.2)
    with pytest.raises(OperationalError, match='collection_removal_limit_exceeded'):
        plan(existing, [received(f'o{n}', f'h{n}.example.org') for n in range(7)], ratio=0.2)
