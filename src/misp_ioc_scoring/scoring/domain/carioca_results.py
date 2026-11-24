"""Read types of CARIOCA runs published by `scoring.api` (contracts/scoring-api.md)."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CariocaRun:
    id: UUID
    as_of: datetime
    finished_at: datetime
    configuration_version: str
    configuration_hash: str
    top_n: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class CariocaScore:
    ioc_id: UUID
    type: str
    normalized_value: str
    priority_score: float
    rank: int
    in_top_n: bool
    input_revision: int
    as_of: datetime
    source_instance_id: str
    attribute_uuid: UUID


@dataclass(frozen=True)
class ScoreExclusion:
    ioc_id: UUID
    reason: str


@dataclass(frozen=True)
class ScoreExplanation:
    """Explanation of one IOC score, in the glossary terms."""
    ioc_id: UUID
    as_of: datetime
    configuration_version: str
    configuration_hash: str
    priority_score: float
    rank: int
    in_top_n: bool
    top_n: int
    winning_observation: tuple[str, UUID]
    observations_evaluated: int
    components: dict
    sigma_by_category: dict
    minmax_degenerate: tuple[str, ...]
    exclusion_reason: str | None
    source_proxy_limitation: str


@dataclass(frozen=True)
class ScoreResult:
    """Score of one logical IOC in a run: the components of its winning observation."""
    ioc_id: UUID
    type: str
    normalized_value: str
    input_revision: int
    priority_score: float
    rank: int
    in_top_n: bool
    observations_evaluated: int
    winner: object  # aggregation.ObservationEvaluation


@dataclass(frozen=True)
class RunSummary:
    run_id: UUID
    as_of: datetime
    observations_evaluated: int
    valid_population: int
    excluded: int
    warnings: tuple[str, ...]
    scored_revisions: tuple  # ((ioc_id, input_revision), ...) of IOCs with a valid score
