"""Re-scoring candidates (glossary: Candidato a re-scoring): traceability only.

A candidate never selects what is scored: the daily run always recalculates the whole
population (FR-010). Deriving candidates never changes `input_revision`.
"""
CHANGED = 'input_revision_changed'
CONCURRENT_CHANGE = 'input_changed_during_scoring'


def derive_candidates(snapshot_revisions: dict, scored_revisions: dict) -> dict:
    """IOC -> revision read in the snapshot, when it differs from the last scored revision."""
    return {ioc: revision for ioc, revision in snapshot_revisions.items()
            if scored_revisions.get(ioc) != revision}


def split_completed(used_revisions: dict, current_revisions: dict) -> tuple[dict, set]:
    """(completed IOC -> revision, IOCs whose input changed while the run was calculating)."""
    done, concurrent = {}, set()
    for ioc, revision in used_revisions.items():
        if current_revisions.get(ioc) == revision:
            done[ioc] = revision
        else:
            concurrent.add(ioc)
    return done, concurrent
