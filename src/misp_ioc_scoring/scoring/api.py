"""Read-only scoring surface for `sharing`; returns immutable scoring domain types."""
from sqlalchemy import text

from misp_ioc_scoring.scoring.domain.blocking import BlockingDecision, BlockingReason, ScoreModel
from misp_ioc_scoring.scoring.domain.simple_blocking import BLOCKABLE_TYPES

__all__ = ["BLOCKABLE_TYPES", "BlockingDecision", "BlockingReason", "ScoreModel",
           "blocking_decision", "effective_blocks"]

_COLUMNS = "source_instance_id, attribute_uuid, attribute_id, block, reason, as_of, expires_at, rule_version"


def _decision(row) -> BlockingDecision:
    return BlockingDecision(
        source_instance_id=row.source_instance_id, attribute_uuid=row.attribute_uuid,
        attribute_id=row.attribute_id, block=row.block, reason=BlockingReason(row.reason),
        as_of=row.as_of, expires_at=row.expires_at, rule_version=row.rule_version)


def blocking_decision(session, source_instance_id, *, attribute_uuid=None, attribute_id=None):
    """Return a read-only effective decision, or None when no attribute is known."""
    if (attribute_uuid is None) == (attribute_id is None):
        raise ValueError("Provide exactly one attribute identifier")
    column = "attribute_uuid" if attribute_uuid is not None else "attribute_id"
    identifier = attribute_uuid if attribute_uuid is not None else attribute_id
    rows = session.execute(text(
        f"SELECT {_COLUMNS} FROM scoring.decisao_bloqueio_efetiva "
        f"WHERE source_instance_id=:source AND {column}=:identifier"
    ), {"source": source_instance_id, "identifier": identifier}).fetchmany(2)
    if len(rows) > 1:
        raise ValueError("Ambiguous local attribute ID")
    return _decision(rows[0]) if rows else None


def effective_blocks(session) -> list[BlockingDecision]:
    """Effective decisions that block now."""
    return [_decision(row) for row in session.execute(text(
        f"SELECT {_COLUMNS} FROM scoring.decisao_bloqueio_efetiva WHERE block"))]
