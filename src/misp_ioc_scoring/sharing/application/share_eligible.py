"""Share eligible IOCs with MISP peers (FR-015 to FR-017, FR-027).

Eligibility is re-evaluated in every round: valid score of the current run, at least the
peer minimum, in the top-N, not warninglisted (FR-027 mode) and native distribution that
reaches the peer. Publishing is only `requested`; `confirmed` needs the attribute read
back from the peer. Timeouts become `ambiguous` and are reconciled by reading first.
"""
import logging
from dataclasses import replace
from typing import Protocol

from misp_ioc_scoring.collection.api import warninglist_index

from ..domain.sharing import (AttemptState as State, IneligibilityReason, ShareAttempt, decide_distribution,
                              next_attempt, score_eligibility, score_is_stale)

log = logging.getLogger(__name__)
LIVE = (State.REQUESTED, State.CONFIRMED, State.AMBIGUOUS)


class SharingReader(Protocol):
    def current_carioca_run(self): ...
    def carioca_scores(self, run_id) -> list: ...
    def observations(self, ioc_ids) -> dict: ...
    def warninglists(self) -> dict: ...


class SharingPort(Protocol):
    def sharing_group_members(self) -> dict: ...
    def peer_groups(self, peer, members) -> set: ...
    def ensure_event(self, peer, members): ...
    def upsert(self, peer, attempt, score): ...
    def remove(self, peer, attribute_uuid): ...
    def publish(self, peer): ...
    def confirmed(self, peer, attribute_uuid) -> bool: ...


class SharingStore(Protocol):
    policy_hash: str

    def suspend(self, reason, at): ...
    def resume(self): ...
    def attempts(self, peer_id) -> dict: ...
    def save(self, attempt): ...


def _error(error):
    return getattr(error, 'code', None) or type(error).__name__


def share_eligible(as_of, reader: SharingReader, misp: SharingPort, store: SharingStore, policy, *, max_age):
    """One sharing round for every peer; returns {peer_id: {state: count}} or None when suspended."""
    run = reader.current_carioca_run()
    if score_is_stale(run, as_of, max_age):
        reason = 'no_valid_score' if run is None else IneligibilityReason.STALE_SCORE.value
        store.suspend(reason, as_of)
        log.warning('sharing_suspended', extra={'event': 'sharing_suspended', 'code': reason})
        return None
    store.resume()
    scores = {score.ioc_id: score for score in reader.carioca_scores(run.id)}
    entries = [entry for items in reader.warninglists().values() for entry in items]
    index = warninglist_index(entries, 'fr027')
    members = misp.sharing_group_members()
    return {peer.peer_id: _share_peer(as_of, run, scores, index, members, peer, reader, misp, store, policy)
            for peer in policy.peers}


def _share_peer(as_of, run, scores, index, members, peer, reader, misp, store, policy):
    groups = misp.peer_groups(peer, members)
    attempts = store.attempts(peer.peer_id)
    counts = {}

    def save(attempt):
        attempts[attempt.ioc_id] = attempt
        store.save(attempt)

    # 1. Reconcile what was requested or left ambiguous before doing anything else.
    for attempt in list(attempts.values()):
        if attempt.state not in (State.REQUESTED, State.AMBIGUOUS):
            continue
        try:
            if misp.confirmed(peer, attempt.outbound_attribute_uuid):
                save(replace(attempt, state=State.CONFIRMED, last_error=None, next_attempt_at=None))
        except Exception as error:
            save(replace(attempt, state=State.AMBIGUOUS, last_error=_error(error)))

    # 2. Re-evaluate eligibility for the current run.
    def warninglisted(score):
        return index.match(score.type, score.normalized_value, 'fr027') is True

    reasons = {ioc: score_eligibility(score, peer.minimum_priority_score, warninglisted=warninglisted(score))
               for ioc, score in scores.items() if score.in_top_n}
    candidates = [ioc for ioc, reason in reasons.items() if reason is None]
    observations = reader.observations(candidates)
    decisions = {}
    for ioc in candidates:
        decision = decide_distribution(observations.get(ioc, ()), groups)
        if decision is None:
            reasons[ioc] = IneligibilityReason.DISTRIBUTION_NOT_ALLOWED
        else:
            decisions[ioc] = decision

    changed = False
    # 3. Remove what stopped being eligible before publishing again.
    for ioc, attempt in list(attempts.items()):
        if ioc in decisions or attempt.state not in LIVE:
            continue
        reason = reasons.get(ioc) or score_eligibility(scores.get(ioc), peer.minimum_priority_score,
                                                       warninglisted=False) or IneligibilityReason.OUTSIDE_TOP_N
        try:
            misp.remove(peer, attempt.outbound_attribute_uuid)
            changed = True
            save(replace(attempt, state=State.INELIGIBLE, reason=str(reason), scoring_run_id=run.id,
                         last_error=None, next_attempt_at=None))
        except Exception as error:
            save(replace(attempt, state=State.AMBIGUOUS, last_error=_error(error)))

    # 4. Record ineligible top-N IOCs that were never shared, with their reason.
    for ioc, reason in reasons.items():
        if reason is not None and ioc not in attempts:
            save(ShareAttempt(peer.peer_id, ioc, State.INELIGIBLE, run.id, store.policy_hash,
                              peer.outbound_attribute_uuid(ioc), reason=str(reason)))

    # 5. Create or update the outbound attributes of eligible IOCs.
    pending, event_ready = [], False
    for ioc, decision in decisions.items():
        current = attempts.get(ioc)
        group_uuid = members.get(decision.sharing_group_id, (None,))[0] if decision.distribution == '4' else None
        outbound = (decision.distribution, group_uuid)
        if current is not None:
            if current.state == State.CONFIRMED and current.outbound == outbound:
                continue
            if current.state == State.FAILED:
                continue
            if current.state in (State.REQUESTED, State.AMBIGUOUS):
                if current.attempts >= policy.retry_attempts:
                    save(replace(current, state=State.FAILED, last_error=current.last_error or 'unconfirmed'))
                    continue
                if current.next_attempt_at and current.next_attempt_at > as_of and current.outbound == outbound:
                    continue
        attempt = ShareAttempt(
            peer.peer_id, ioc, State.ELIGIBLE, run.id, store.policy_hash, peer.outbound_attribute_uuid(ioc),
            decision.permitting_source_instance_id, decision.permitting_attribute_uuid, decision.distribution,
            group_uuid, None, current.attempts if current else 0, None, None)
        try:
            if not event_ready:
                misp.ensure_event(peer, members)
                event_ready = True
            misp.upsert(peer, attempt, _Outbound(scores[ioc], decision))
            save(attempt)
            pending.append(attempt)
            changed = True
        except Exception as error:
            failed = replace(attempt, state=State.AMBIGUOUS, attempts=attempt.attempts + 1,
                             next_attempt_at=next_attempt(attempt.attempts + 1, as_of, policy.retry_backoff_seconds),
                             last_error=_error(error))
            save(failed)

    # 6. Publish once: a request to the native sync, not a confirmation.
    if changed:
        try:
            misp.publish(peer)
            state, error = State.REQUESTED, None
        except Exception as failure:
            state, error = State.AMBIGUOUS, _error(failure)
        for attempt in pending:
            tries = attempt.attempts + 1
            save(replace(attempt, state=state, attempts=tries, last_error=error,
                         next_attempt_at=next_attempt(tries, as_of, policy.retry_backoff_seconds)))
    for attempt in attempts.values():
        counts[str(attempt.state)] = counts.get(str(attempt.state), 0) + 1
    return counts


class _Outbound:
    """Score plus the local sharing group id used for an outbound attribute."""

    def __init__(self, score, decision):
        self.type = score.type
        self.normalized_value = score.normalized_value
        self.sharing_group_id = decision.sharing_group_id
