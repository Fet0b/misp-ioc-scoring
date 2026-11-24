"""CARIOCA persistence: mappings, the `CariocaStore` port over SQL and `CariocaRunner`."""
from dataclasses import fields
from uuid import uuid4

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, Uuid, bindparam,
                        insert, text)
from sqlalchemy.orm import mapped_column

from misp_ioc_scoring.collection.api import collection_snapshot
from misp_ioc_scoring.shared.database import Base, transaction

CARIOCA_LOCK = 874204
COLLECTION_LOCK = 874201
COMPONENTS = ("age_days", "attribute_raw", "attribute_norm", "threat_level", "analysis", "cade_raw",
              "cade_norm", "event_raw", "event_norm", "source_value", "source_norm")


def _component_columns(namespace):
    for name in COMPONENTS:
        namespace[name] = mapped_column(Float, nullable=False)


class CariocaConfigurationModel(Base):
    __tablename__ = "configuracao_carioca"
    __table_args__ = {"schema": "scoring"}
    id = mapped_column(Uuid, primary_key=True)
    model_id = mapped_column(String(100), nullable=False)
    version = mapped_column(String(100), nullable=False)
    content_hash = mapped_column(String(64), nullable=False, unique=True)
    content = mapped_column(Text, nullable=False)
    approved = mapped_column(Boolean, nullable=False)
    approved_by = mapped_column(String(200))
    approved_at = mapped_column(DateTime(timezone=True))
    evidence_ref = mapped_column(String(500))
    registered_at = mapped_column(DateTime(timezone=True))


class ScoringRunModel(Base):
    __tablename__ = "execucao_scoring"
    __table_args__ = {"schema": "scoring"}
    id = mapped_column(Uuid, primary_key=True)
    configuration_id = mapped_column(ForeignKey("scoring.configuracao_carioca.id"))
    as_of = mapped_column(DateTime(timezone=True), nullable=False)
    started_at = mapped_column(DateTime(timezone=True))
    finished_at = mapped_column(DateTime(timezone=True))
    status = mapped_column(String(20), nullable=False)
    observations_evaluated = mapped_column(Integer, nullable=False, default=0)
    valid_population = mapped_column(Integer, nullable=False, default=0)
    excluded = mapped_column(Integer, nullable=False, default=0)
    warnings = mapped_column(JSON, nullable=False, default=list)
    error = mapped_column(String(100))


class PopulationStatisticsModel(Base):
    __tablename__ = "estatisticas_populacao"
    __table_args__ = {"schema": "scoring"}
    scoring_run_id = mapped_column(ForeignKey("scoring.execucao_scoring.id"), primary_key=True)
    as_of = mapped_column(DateTime(timezone=True), nullable=False)
    sigma_by_category = mapped_column(JSON, nullable=False)
    n_by_category_stats = mapped_column(JSON, nullable=False)
    bounds = mapped_column(JSON, nullable=False)
    organizations = mapped_column(JSON, nullable=False)
    minmax_degenerate = mapped_column(JSON, nullable=False)
    details = mapped_column(JSON, nullable=False)


class ObservationEvaluationModel(Base):
    __tablename__ = "avaliacao_observacao"
    __table_args__ = {"schema": "scoring"}
    scoring_run_id = mapped_column(ForeignKey("scoring.execucao_scoring.id"), primary_key=True)
    source_instance_id = mapped_column(String(100), primary_key=True)
    attribute_uuid = mapped_column(Uuid, primary_key=True)
    ioc_id = mapped_column(Uuid, nullable=False)
    event_uuid = mapped_column(Uuid, nullable=False)
    orgc_uuid = mapped_column(Uuid, nullable=False)
    decay_group = mapped_column(String(20), nullable=False)
    _component_columns(locals())
    priority = mapped_column(Float, nullable=False)
    minmax_degenerate = mapped_column(JSON, nullable=False)


class ScoreResultModel(Base):
    __tablename__ = "resultado_score"
    __table_args__ = {"schema": "scoring"}
    scoring_run_id = mapped_column(ForeignKey("scoring.execucao_scoring.id"), primary_key=True)
    ioc_id = mapped_column(Uuid, primary_key=True)
    as_of = mapped_column(DateTime(timezone=True), nullable=False)
    ioc_type = mapped_column(String(100), nullable=False)
    normalized_value = mapped_column(Text, nullable=False)
    input_revision = mapped_column(Integer, nullable=False)
    priority_score = mapped_column(Float, nullable=False)
    rank = mapped_column(Integer, nullable=False)
    in_top_n = mapped_column(Boolean, nullable=False)
    winning_source_instance_id = mapped_column(String(100), nullable=False)
    winning_attribute_uuid = mapped_column(Uuid, nullable=False)
    observations_evaluated = mapped_column(Integer, nullable=False)
    decay_group = mapped_column(String(20), nullable=False)
    event_uuid = mapped_column(Uuid, nullable=False)
    orgc_uuid = mapped_column(Uuid, nullable=False)
    _component_columns(locals())
    minmax_degenerate = mapped_column(JSON, nullable=False)
    event_categories = mapped_column(JSON, nullable=False)


class ScoreExclusionModel(Base):
    __tablename__ = "exclusao_score"
    __table_args__ = {"schema": "scoring"}
    scoring_run_id = mapped_column(ForeignKey("scoring.execucao_scoring.id"), primary_key=True)
    ioc_id = mapped_column(Uuid, primary_key=True)
    reason = mapped_column(String(40), nullable=False)


def _evaluation_row(run_id, evaluation):
    row = {name: getattr(evaluation, name) for name in COMPONENTS}
    row.update(scoring_run_id=run_id, source_instance_id=evaluation.source_instance_id,
               attribute_uuid=evaluation.attribute_uuid, ioc_id=evaluation.ioc_id,
               event_uuid=evaluation.event_uuid, orgc_uuid=evaluation.orgc_uuid,
               decay_group=evaluation.decay_group, priority=evaluation.priority,
               minmax_degenerate=list(evaluation.minmax_degenerate))
    return row


class SqlCariocaStore:
    """`CariocaStore` over one REPEATABLE READ transaction holding the CARIOCA lock."""

    def __init__(self, session, snapshot):
        self.session = session
        self.snapshot = snapshot
        self.run_id = None
        self.as_of = None
        self.configuration_id = None

    def _configuration(self, configuration):
        existing = self.session.scalar(text(
            "SELECT id FROM scoring.configuracao_carioca WHERE content_hash=:hash"),
            {"hash": configuration.content_hash})
        if existing:
            return existing
        identifier = uuid4()
        self.session.execute(insert(CariocaConfigurationModel).values(
            id=identifier, model_id=configuration.model_id, version=configuration.version,
            content_hash=configuration.content_hash, content=configuration.content,
            approved=configuration.approved, approved_by=configuration.approved_by,
            approved_at=configuration.approved_at, evidence_ref=configuration.evidence_ref))
        return identifier

    def start(self, run_id, as_of, configuration):
        self.run_id, self.as_of = run_id, as_of
        self.configuration_id = self._configuration(configuration)
        self.session.execute(insert(ScoringRunModel).values(
            id=run_id, configuration_id=self.configuration_id, as_of=as_of, status="running", warnings=[]))

    def statistics(self, run_id, statistics):
        main = ("sigma_by_category", "n_by_category_stats", "bounds", "organizations", "minmax_degenerate")
        self.session.execute(insert(PopulationStatisticsModel).values(
            scoring_run_id=run_id, as_of=self.as_of, **{key: statistics[key] for key in main},
            details={key: value for key, value in statistics.items() if key not in main}))

    def evaluations(self, run_id, evaluations):
        self.session.execute(insert(ObservationEvaluationModel), [_evaluation_row(run_id, e) for e in evaluations])

    def results(self, run_id, results):
        rows = []
        for result in results:
            row = _evaluation_row(run_id, result.winner)
            for key in ("source_instance_id", "attribute_uuid", "priority"):
                row.pop(key)
            row.update(ioc_id=result.ioc_id, as_of=self.as_of, ioc_type=result.type,
                       normalized_value=result.normalized_value, input_revision=result.input_revision,
                       priority_score=result.priority_score, rank=result.rank, in_top_n=result.in_top_n,
                       winning_source_instance_id=result.winner.source_instance_id,
                       winning_attribute_uuid=result.winner.attribute_uuid,
                       observations_evaluated=result.observations_evaluated,
                       event_categories=list(result.winner.event_categories))
            rows.append(row)
        self.session.execute(insert(ScoreResultModel), rows)

    def exclusions(self, run_id, exclusions):
        self.session.execute(insert(ScoreExclusionModel), [
            dict(scoring_run_id=run_id, ioc_id=ioc_id, reason=str(reason)) for ioc_id, reason in exclusions])

    def finish(self, run_id, summary):
        self.session.execute(text("""
            UPDATE scoring.execucao_scoring SET finished_at=clock_timestamp(), status='completed',
            observations_evaluated=:evaluated, valid_population=:valid, excluded=:excluded, warnings=:warnings
            WHERE id=:id
        """).bindparams(bindparam("warnings", type_=JSON)), dict(
            id=run_id, evaluated=summary.observations_evaluated, valid=summary.valid_population,
            excluded=summary.excluded, warnings=list(summary.warnings)))


_FAILED = text("""
INSERT INTO scoring.execucao_scoring (id, configuration_id, as_of, finished_at, status, warnings, error)
VALUES (:id, NULL, COALESCE(:as_of, clock_timestamp()), clock_timestamp(), 'failed', '[]', :error)
ON CONFLICT DO NOTHING
""").bindparams(bindparam("as_of", type_=DateTime(timezone=True)))


class CariocaRunner:
    """Context manager: CARIOCA lock, REPEATABLE READ transaction and the collection snapshot.

    Yields a `SqlCariocaStore`, or None when another worker holds the CARIOCA lock. The
    collection lock is held only while the snapshot is read. A failure rolls everything
    back and records a `failed` run, so the current run is never replaced.
    """

    def __init__(self, engine, new_run_id=uuid4):
        self.engine = engine.execution_options(isolation_level="REPEATABLE READ")
        self.plain_engine = engine
        self.new_run_id = new_run_id
        self._context = None
        self._store = None

    def __enter__(self):
        self._context = transaction(self.engine)
        session = self._context.__enter__()
        try:
            if not session.scalar(text(f"SELECT pg_try_advisory_xact_lock({CARIOCA_LOCK})")):
                self._close(None)
                return None
            session.execute(text(f"SELECT pg_advisory_lock({COLLECTION_LOCK})"))
            try:
                snapshot = collection_snapshot(session)
            finally:
                session.execute(text(f"SELECT pg_advisory_unlock({COLLECTION_LOCK})"))
            self._store = SqlCariocaStore(session, snapshot)
            return self._store
        except BaseException as error:
            self._fail(error)
            raise

    def _close(self, error):
        context, self._context = self._context, None
        if context is not None:
            if error is None:
                context.__exit__(None, None, None)
            else:
                context.__exit__(type(error), error, error.__traceback__)

    def __exit__(self, exc_type, exc, tb):
        if self._context is None:
            return False
        if exc_type is None:
            self._close(None)
        else:
            self._fail(exc)
        return False

    def _fail(self, error):
        self._close(error)
        store = self._store
        code = getattr(error, "code", None) or "carioca_run_failed"
        with transaction(self.plain_engine) as session:
            session.execute(_FAILED, {"id": store.run_id if store and store.run_id else self.new_run_id(),
                                      "as_of": store.as_of if store else None, "error": str(code)[:100]})
