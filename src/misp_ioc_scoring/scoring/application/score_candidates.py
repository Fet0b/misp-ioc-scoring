"""Mark and complete re-scoring candidates around a CARIOCA run."""
from typing import Protocol

from ..domain.rescoring import CHANGED, CONCURRENT_CHANGE, derive_candidates, split_completed


class CandidateStore(Protocol):
    def scored_revisions(self) -> dict: ...
    def mark(self, candidates: dict, reason, marked_at): ...
    def current_revisions(self, ioc_ids) -> dict: ...
    def complete(self, done: dict, attempted_at): ...
    def keep_pending(self, ioc_ids, attempted_at, error): ...


def active_revisions(snapshot) -> dict:
    """One revision per logical IOC with an active observation (many observations, one candidate)."""
    return {o.ioc_id: o.input_revision for o in snapshot.observations if o.removed_at is None}


def mark_candidates(snapshot, store: CandidateStore, as_of) -> dict:
    candidates = derive_candidates(active_revisions(snapshot), store.scored_revisions())
    store.mark(candidates, CHANGED, as_of)
    return candidates


def complete_candidates(snapshot, store: CandidateStore, as_of):
    """Clear a candidate only if the revision used is still the current one."""
    used = active_revisions(snapshot)
    done, concurrent = split_completed(used, store.current_revisions(used))
    store.complete(done, as_of)
    store.keep_pending(concurrent, as_of, CONCURRENT_CHANGE)
    return done, concurrent
