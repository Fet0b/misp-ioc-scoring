"""Blocking decision of one source observation (glossary: Decisão de bloqueio)."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class BlockingReason(StrEnum):
    """Reason of a decision; the value is what is stored in `scoring.decisao_bloqueio`."""
    ELIGIBLE = 'eligible'
    REMOVED = 'removed'
    TYPE = 'type'
    TO_IDS = 'to_ids'
    ANALYSIS = 'analysis'
    WARNINGLIST = 'warninglist'
    EXPIRED = 'expired'
    INDETERMINATE = 'indeterminate'
    REJECTED = 'rejected'
    STALE = 'stale'


class ScoreModel(StrEnum):
    DEFAULT = 'default'
    CARIOCA = 'carioca'


@dataclass(frozen=True)
class BlockingEvidence:
    kind: str
    max_age_hours: float
    timestamp: datetime | None = None
    warning: bool | None = None
    to_ids: bool | None = None
    analysis: str | None = None
    rejected: bool = False

    def to_json(self) -> dict:
        """Same JSON stored before the domain type existed."""
        if self.rejected:
            return dict(kind=self.kind, max_age_hours=self.max_age_hours)
        return dict(timestamp=self.timestamp.isoformat() if self.timestamp else None,
                    kind=self.kind, warning=self.warning, max_age_hours=self.max_age_hours,
                    to_ids=self.to_ids, analysis=self.analysis)


@dataclass(frozen=True)
class BlockingDecision:
    source_instance_id: str
    attribute_uuid: UUID
    attribute_id: int | None
    block: bool
    reason: BlockingReason
    as_of: datetime
    expires_at: datetime
    generation: int | None = None
    evidence: BlockingEvidence | None = None
    rule_version: str | None = None
