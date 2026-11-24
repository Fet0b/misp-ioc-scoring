"""Winning observation of an IOC (glossary: Observação vencedora)."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ObservationEvaluation:
    """Components of one valid observation in a run (glossary: Avaliação de observação)."""
    ioc_id: UUID
    source_instance_id: str
    attribute_uuid: UUID
    event_uuid: UUID
    orgc_uuid: UUID
    source_created_at: datetime
    decay_group: str
    age_days: float
    attribute_raw: float
    attribute_norm: float
    threat_level: float
    analysis: float
    cade_raw: float
    cade_norm: float
    event_raw: float
    event_norm: float
    source_value: float
    source_norm: float
    priority: float
    minmax_degenerate: tuple[str, ...] = ()


def order_key(evaluation):
    """Highest priority first; ties: oldest `source_created_at`, then source and UUID."""
    return (-evaluation.priority, evaluation.source_created_at, evaluation.source_instance_id,
            str(evaluation.attribute_uuid))


def winners(evaluations) -> dict:
    """IOC -> (winning evaluation, number of observations evaluated)."""
    result = {}
    for evaluation in evaluations:
        current = result.get(evaluation.ioc_id)
        if current is None:
            result[evaluation.ioc_id] = (evaluation, 1)
        else:
            best = min(current[0], evaluation, key=order_key)
            result[evaluation.ioc_id] = (best, current[1] + 1)
    return result
