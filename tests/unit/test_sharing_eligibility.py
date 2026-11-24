from dataclasses import replace

import pytest

from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry
from misp_ioc_scoring.sharing.application.share_eligible import share_eligible
from misp_ioc_scoring.sharing.domain.sharing import (AttemptState as S, IneligibilityReason as R,
                                                     decide_distribution, score_eligibility, score_is_stale)
from tests.support.carioca import AS_OF, observation, uid
from tests.support.sharing import PEER, FakeSync, MemoryStore, Reader, policy, run, score
from datetime import timedelta

MAX_AGE = timedelta(hours=48)


def test_minimum_boundary_top_n_and_warninglist():
    assert score_eligibility(score('a', 50), 50, warninglisted=False) is None
    assert score_eligibility(score('a', 49.99), 50, warninglisted=False) == R.BELOW_MINIMUM
    assert score_eligibility(score('a', 90, in_top_n=False), 50, warninglisted=False) == R.OUTSIDE_TOP_N
    assert score_eligibility(score('a', 90), 50, warninglisted=True) == R.WARNINGLIST
    assert score_eligibility(None, 50, warninglisted=False) == R.NO_VALID_SCORE


def test_score_age():
    assert score_is_stale(None, AS_OF, MAX_AGE)
    assert score_is_stale(run(age_hours=48), AS_OF, MAX_AGE)
    assert not score_is_stale(run(age_hours=47), AS_OF, MAX_AGE)


def obs(name, distribution, event_distribution='3', *, published=True, sg=None, event_sg=None, created=20, source='s1'):
    return replace(observation(name, distribution=distribution, event_distribution=event_distribution,
                               published=published, sharing_group_id=sg, created_days=created, source=source),
                   event_sharing_group_id=event_sg)


@pytest.mark.parametrize('observations,groups,expected', [
    ([obs('a', '0'), obs('b', '3')], set(), ('3', None)),
    ([obs('a', '1'), obs('b', '3')], set(), ('1', None)),
    ([obs('a', '4', sg='7'), obs('b', '3')], {'7'}, ('4', '7')),
    ([obs('a', '4', sg='7')], set(), None),
    ([obs('a', '0')], set(), None),
    ([obs('a', '3', published=False)], set(), None),
    ([obs('a', '5', '4', event_sg='7')], {'7'}, ('4', '7')),
    ([obs('a', '5', '4')], {'7'}, None),
])
def test_distribution_rule(observations, groups, expected):
    decision = decide_distribution(observations, groups)
    assert (decision and (decision.distribution, decision.sharing_group_id)) == (expected or None)


def test_distribution_tie_uses_aggregation_order():
    older, newer = obs('old', '2', created=30), obs('new', '2', created=10)
    assert decide_distribution([newer, older], set()).permitting_attribute_uuid == older.attribute_uuid


def reader(current=None, scores=None, observations=None, lists=None):
    scores = scores if scores is not None else [score('a.example', 80), score('b.example', 40, rank=2)]
    observations = observations if observations is not None else {
        uid('ioc:a.example'): (obs('a', '2'),), uid('ioc:b.example'): (obs('b', '3'),)}
    return Reader(current or run(), scores, observations, lists)


def test_stale_score_suspends_and_resumes_after_new_run(caplog):
    store, sync = MemoryStore(), FakeSync()
    assert share_eligible(AS_OF, reader(run(age_hours=49)), sync, store, policy(), max_age=MAX_AGE) is None
    assert store.suspended == 'stale_score' and sync.calls == [] and 'sharing_suspended' in caplog.text
    assert share_eligible(AS_OF, Reader(None, [], {}), sync, store, policy(), max_age=MAX_AGE) is None
    assert store.suspended == 'no_valid_score'
    share_eligible(AS_OF, reader(), sync, store, policy(), max_age=MAX_AGE)
    assert store.suspended is None and store.state('a.example').state == S.REQUESTED


def test_round_records_reasons_and_outbound_distribution():
    store, sync = MemoryStore(), FakeSync()
    lists = {'s1': (WarninglistEntry('s1', 'l', 'hostname', 'c.example'), WarninglistEntry('s1', 'r', 'regex', '.*'))}
    scores = [score('a.example', 80), score('b.example', 40, rank=2), score('c.example', 90, rank=3),
              score('d.example', 95, rank=4), score('e.example', 99, rank=5, in_top_n=False)]
    observations = {uid('ioc:a.example'): (obs('a', '2'), obs('a0', '0', source='s2')),
                    uid('ioc:d.example'): (obs('d', '0'),)}
    share_eligible(AS_OF, reader(scores=scores, observations=observations, lists=lists), sync, store, policy(),
                   max_age=MAX_AGE)
    assert store.state('a.example').outbound_distribution == '2'
    assert store.state('b.example').reason == 'below_minimum'
    assert store.state('c.example').reason == 'warninglist'
    assert store.state('d.example').reason == 'distribution_not_allowed'
    assert ('peer-a', uid('ioc:e.example')) not in store.rows
    assert sync.calls == ['ensure', ('upsert', 'a.example', '2'), 'publish']
