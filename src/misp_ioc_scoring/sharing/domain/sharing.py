"""Sharing with MISP peers (glossary: Política de compartilhamento, Peer MISP)."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

# Same restrictiveness as `collection.domain.snapshots.RESTRICTIVENESS` (0 < 4 < 1 < 2 < 3).
RESTRICTIVENESS = {'0': 0, '4': 1, '1': 2, '2': 3, '3': 4}
REACHING = frozenset({'1', '2', '3', '4'})


class IneligibilityReason(StrEnum):
    BELOW_MINIMUM = 'below_minimum'
    OUTSIDE_TOP_N = 'outside_top_n'
    WARNINGLIST = 'warninglist'
    STALE_SCORE = 'stale_score'
    NO_VALID_SCORE = 'no_valid_score'
    DISTRIBUTION_NOT_ALLOWED = 'distribution_not_allowed'


class AttemptState(StrEnum):
    ELIGIBLE = 'eligible'
    REQUESTED = 'requested'
    CONFIRMED = 'confirmed'
    FAILED = 'failed'
    AMBIGUOUS = 'ambiguous'
    INELIGIBLE = 'ineligible'
    SUSPENDED = 'suspended'


@dataclass(frozen=True)
class PeerPolicy:
    peer_id: str
    base_url: str
    credential_secret_ref: str
    minimum_priority_score: float
    distribution: str  # maximum distribution of the outbound event
    sharing_group_uuid: str | None = None
    allow_http: bool = False

    @property
    def outbound_event_uuid(self) -> UUID:
        return uuid5(NAMESPACE_URL, 'misp-ioc-scoring:outbound-event:' + self.peer_id)

    def outbound_attribute_uuid(self, ioc_id) -> UUID:
        return uuid5(NAMESPACE_URL, f'misp-ioc-scoring:outbound-attribute:{self.peer_id}:{ioc_id}')


@dataclass(frozen=True)
class DistributionDecision:
    permitting_source_instance_id: str
    permitting_attribute_uuid: UUID
    distribution: str
    sharing_group_id: str | None


@dataclass(frozen=True)
class ShareAttempt:
    peer_id: str
    ioc_id: UUID
    state: AttemptState
    scoring_run_id: UUID | None
    policy_hash: str
    outbound_attribute_uuid: UUID
    permitting_source_instance_id: str | None = None
    permitting_attribute_uuid: UUID | None = None
    outbound_distribution: str | None = None
    outbound_sharing_group_uuid: str | None = None
    reason: str | None = None
    attempts: int = 0
    next_attempt_at: datetime | None = None
    last_error: str | None = None

    @property
    def outbound(self):
        return (self.outbound_distribution, self.outbound_sharing_group_uuid)


def score_eligibility(score, minimum, *, warninglisted) -> IneligibilityReason | None:
    """Valid score of the current run, at least the peer minimum, in the top-N and not warninglisted."""
    if score is None:
        return IneligibilityReason.NO_VALID_SCORE
    if not score.in_top_n:
        return IneligibilityReason.OUTSIDE_TOP_N
    if score.priority_score < minimum:
        return IneligibilityReason.BELOW_MINIMUM
    if warninglisted:
        return IneligibilityReason.WARNINGLIST
    return None


def score_is_stale(run, now, max_age) -> bool:
    return run is None or run.finished_at <= now - max_age


def _order(observation):
    return (observation.source_created_at, observation.source_instance_id, str(observation.attribute_uuid))


def decide_distribution(observations, peer_groups) -> DistributionDecision | None:
    """At least one active observation of a published event must reach the peer.

    Among those that reach it, the most restrictive distribution wins (ties: the
    aggregation order); the outbound attribute never gets a wider distribution.
    `peer_groups`: local sharing group ids whose servers include the peer.
    """
    reaching = []
    for observation in observations:
        if observation.removed_at is not None or observation.published is not True:
            continue
        level, group = observation.effective_distribution()
        if level not in REACHING or (level == '4' and group not in peer_groups):
            continue
        reaching.append((RESTRICTIVENESS[level], _order(observation), observation, level, group))
    if not reaching:
        return None
    _, _, observation, level, group = min(reaching, key=lambda item: item[:2])
    return DistributionDecision(observation.source_instance_id, observation.attribute_uuid, level, group)


def next_attempt(attempts, now, backoff_seconds):
    from datetime import timedelta
    return now + timedelta(seconds=backoff_seconds * 2 ** max(attempts - 1, 0))
