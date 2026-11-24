from misp_ioc_scoring.scoring.application.score_candidates import active_revisions, complete_candidates, mark_candidates
from misp_ioc_scoring.scoring.application.score_population import calculate, run_carioca
from misp_ioc_scoring.scoring.domain.rescoring import derive_candidates, split_completed
from tests.support.carioca import AS_OF, MemoryCariocaStore, configuration, observation, snapshot, uid


class MemoryCandidates:
    def __init__(self, scored=None, current=None):
        self.scored = scored or {}
        self.current = current
        self.marked, self.done, self.pending = {}, {}, set()

    def scored_revisions(self):
        return dict(self.scored)

    def mark(self, candidates, reason, marked_at):
        self.marked.update(candidates)

    def current_revisions(self, ioc_ids):
        return {ioc: (self.current or {}).get(ioc, revision) for ioc, revision in ioc_ids.items()}

    def complete(self, done, attempted_at):
        self.done.update(done)

    def keep_pending(self, ioc_ids, attempted_at, error):
        self.pending.update(ioc_ids)


def test_candidate_when_revision_differs_from_last_scored():
    assert derive_candidates({'a': 2, 'b': 1, 'c': 1}, {'a': 1, 'b': 1}) == {'a': 2, 'c': 1}
    assert split_completed({'a': 2, 'b': 1}, {'a': 2, 'b': 3}) == ({'a': 2}, {'b'})


def test_many_observations_give_one_candidate():
    data = snapshot(observation('a', ioc='same', revision=4), observation('b', ioc='same', source='s2', revision=4))
    assert active_revisions(data) == {uid('ioc:same'): 4}
    store = MemoryCandidates()
    assert mark_candidates(data, store, AS_OF) == {uid('ioc:same'): 4}


def test_candidates_do_not_change_what_is_scored_nor_revisions():
    data = snapshot(observation('a', 'a.org', revision=3), observation('b', 'b.org', revision=1, org='B'))
    plain = calculate(AS_OF, data, configuration())
    store = MemoryCandidates(scored={uid('ioc:domain:b.org'): 1})
    summary = run_carioca(AS_OF, data, configuration(), MemoryCariocaStore(), candidates=store)
    assert {r.ioc_id for r in plain[2]} == {ioc for ioc, _ in summary.scored_revisions}
    assert store.marked == {uid('ioc:domain:a.org'): 3}
    assert store.done == {uid('ioc:domain:a.org'): 3, uid('ioc:domain:b.org'): 1}
    assert [o.input_revision for o in data.observations] == [3, 1]


def test_concurrent_revision_keeps_pending():
    data = snapshot(observation('a', 'a.org', revision=3))
    store = MemoryCandidates(current={uid('ioc:domain:a.org'): 4})
    done, concurrent = complete_candidates(data, store, AS_OF)
    assert done == {} and concurrent == {uid('ioc:domain:a.org')} == store.pending
