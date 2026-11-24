"""Read-only scoring surface for `sharing`; returns immutable scoring domain types."""
import json
from pathlib import Path

from sqlalchemy import text

from misp_ioc_scoring.collection.api import CATEGORIES
from misp_ioc_scoring.scoring.application.score_explanation import build_explanation
from misp_ioc_scoring.scoring.domain.blocking import BlockingDecision, BlockingReason, ScoreModel
from misp_ioc_scoring.scoring.domain.carioca_configuration import (CariocaConfiguration, CariocaConfigurationError,
                                                                   parse_configuration)
from misp_ioc_scoring.scoring.domain.carioca_results import CariocaRun, CariocaScore, ScoreExclusion, ScoreExplanation
from misp_ioc_scoring.scoring.domain.simple_blocking import BLOCKABLE_TYPES

__all__ = ["BLOCKABLE_TYPES", "BlockingDecision", "BlockingReason", "CariocaConfigurationError", "CariocaRun",
           "CariocaScore", "ScoreExclusion", "ScoreExplanation", "ScoreModel", "blocking_decision",
           "carioca_scores", "current_carioca_run", "effective_blocks", "exclusions", "explain",
           "load_carioca_configuration"]

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


def load_carioca_configuration(path) -> CariocaConfiguration:
    """Read and validate the versioned configuration file; approval is checked by the caller."""
    try:
        content = Path(path).read_text(encoding="utf-8")
    except (OSError, TypeError, ValueError):
        raise CariocaConfigurationError("CARIOCA_CONFIG_PATH") from None
    return parse_configuration(content, CATEGORIES)


_RUN = """
SELECT r.id, r.as_of, r.finished_at, c.version, c.content_hash, c.content, r.warnings
FROM scoring.execucao_scoring r JOIN scoring.configuracao_carioca c ON c.id = r.configuration_id
WHERE r.status = 'completed'
"""


def _run(row) -> CariocaRun:
    return CariocaRun(id=row.id, as_of=row.as_of, finished_at=row.finished_at, configuration_version=row.version,
                      configuration_hash=row.content_hash, top_n=json.loads(row.content)["top_n"],
                      warnings=tuple(row.warnings or ()))


def current_carioca_run(session) -> CariocaRun | None:
    """Last completed run; failed and running runs are never returned."""
    row = session.execute(text(_RUN + " ORDER BY r.finished_at DESC, r.id LIMIT 1")).first()
    return _run(row) if row else None


def carioca_scores(session, run_id, *, min_score=None, top_n_only=False, page_size=1000):
    """Valid scores of a run ordered by rank, read page by page."""
    last = 0
    while True:
        rows = session.execute(text("""
            SELECT ioc_id, ioc_type, normalized_value, priority_score, rank, in_top_n, input_revision, as_of,
                   winning_source_instance_id, winning_attribute_uuid
            FROM scoring.resultado_score
            WHERE scoring_run_id = :run AND rank > :last
              AND (CAST(:min_score AS double precision) IS NULL OR priority_score >= :min_score)
              AND (NOT :top_n_only OR in_top_n)
            ORDER BY rank LIMIT :size
        """), {"run": run_id, "last": last, "min_score": min_score, "top_n_only": top_n_only,
               "size": page_size}).all()
        for row in rows:
            yield CariocaScore(ioc_id=row.ioc_id, type=row.ioc_type, normalized_value=row.normalized_value,
                               priority_score=row.priority_score, rank=row.rank, in_top_n=row.in_top_n,
                               input_revision=row.input_revision, as_of=row.as_of,
                               source_instance_id=row.winning_source_instance_id,
                               attribute_uuid=row.winning_attribute_uuid)
        if len(rows) < page_size:
            return
        last = rows[-1].rank


def exclusions(session, run_id) -> list[ScoreExclusion]:
    return [ScoreExclusion(row.ioc_id, row.reason) for row in session.execute(text(
        "SELECT ioc_id, reason FROM scoring.exclusao_score WHERE scoring_run_id = :run ORDER BY ioc_id"),
        {"run": run_id})]


def explain(session, run_id, ioc_id) -> ScoreExplanation | None:
    """Explanation of an IOC in a run, or of its exclusion; None if the IOC is unknown there."""
    run = session.execute(text(_RUN.replace("WHERE r.status = 'completed'", "WHERE r.id = :run")),
                          {"run": run_id}).first()
    if run is None:
        return None
    run_info = {"configuration_version": run.version, "configuration_hash": run.content_hash,
                "top_n": json.loads(run.content)["top_n"]}
    result = session.execute(text(
        "SELECT * FROM scoring.resultado_score WHERE scoring_run_id = :run AND ioc_id = :ioc"),
        {"run": run_id, "ioc": ioc_id}).mappings().first()
    if result is None:
        reason = session.scalar(text(
            "SELECT reason FROM scoring.exclusao_score WHERE scoring_run_id = :run AND ioc_id = :ioc"),
            {"run": run_id, "ioc": ioc_id})
        if reason is None:
            return None
        from misp_ioc_scoring.scoring.domain.feed_rank import PROXY_LIMITATION
        return ScoreExplanation(ioc_id=ioc_id, as_of=run.as_of, configuration_version=run.version,
                                configuration_hash=run.content_hash, priority_score=None, rank=None,
                                in_top_n=False, top_n=run_info["top_n"], winning_observation=None,
                                observations_evaluated=0, components={}, sigma_by_category={},
                                minmax_degenerate=(), exclusion_reason=reason,
                                source_proxy_limitation=PROXY_LIMITATION)
    statistics = session.execute(text(
        "SELECT sigma_by_category FROM scoring.estatisticas_populacao WHERE scoring_run_id = :run"),
        {"run": run_id}).mappings().first()
    categories = result["event_categories"]
    return build_explanation(run_info, dict(result), dict(statistics) if statistics else None, categories)
