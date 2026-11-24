"""SQL `CandidateStore` for re-scoring candidates."""
from sqlalchemy import Boolean, DateTime, Integer, String, Uuid, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import mapped_column

from misp_ioc_scoring.collection.api import current_input_revisions
from misp_ioc_scoring.shared.database import Base, transaction

_CHUNK = 5000


class RescoringCandidateModel(Base):
    __tablename__ = "candidato_rescoring"
    __table_args__ = {"schema": "scoring"}
    ioc_id = mapped_column(Uuid, primary_key=True)
    pending = mapped_column(Boolean, nullable=False)
    input_revision = mapped_column(Integer, nullable=False)
    scored_revision = mapped_column(Integer)
    reason = mapped_column(String(60), nullable=False)
    marked_at = mapped_column(DateTime(timezone=True), nullable=False)
    last_attempt_at = mapped_column(DateTime(timezone=True))
    last_error = mapped_column(String(100))


def _chunks(items):
    items = list(items)
    for start in range(0, len(items), _CHUNK):
        yield items[start:start + _CHUNK]


class SqlCandidateStore:
    """Writes in the run transaction; current revisions are read from a fresh transaction."""

    def __init__(self, session, engine):
        self.session = session
        self.engine = engine

    def scored_revisions(self):
        return dict(self.session.execute(select(RescoringCandidateModel.ioc_id,
                                                RescoringCandidateModel.scored_revision)).all())

    def mark(self, candidates, reason, marked_at):
        rows = [dict(ioc_id=ioc, pending=True, input_revision=revision, reason=str(reason), marked_at=marked_at)
                for ioc, revision in candidates.items()]
        for chunk in _chunks(rows):
            query = insert(RescoringCandidateModel).values(chunk)
            self.session.execute(query.on_conflict_do_update(
                index_elements=["ioc_id"], set_={key: query.excluded[key]
                                                 for key in ("pending", "input_revision", "reason", "marked_at")}))

    def current_revisions(self, ioc_ids):
        with transaction(self.engine) as fresh:
            return current_input_revisions(fresh, ioc_ids)

    def complete(self, done, attempted_at):
        by_revision = {}
        for ioc, revision in done.items():
            by_revision.setdefault(revision, []).append(ioc)
        for revision, iocs in by_revision.items():
            for chunk in _chunks(iocs):
                self.session.execute(update(RescoringCandidateModel).where(
                    RescoringCandidateModel.ioc_id.in_(chunk)).values(
                    pending=False, scored_revision=revision, last_attempt_at=attempted_at, last_error=None))

    def keep_pending(self, ioc_ids, attempted_at, error):
        for chunk in _chunks(ioc_ids):
            self.session.execute(update(RescoringCandidateModel).where(
                RescoringCandidateModel.ioc_id.in_(chunk)).values(
                last_attempt_at=attempted_at, last_error=str(error)[:100]))


def record_failure(session, code):
    """A failed run keeps every pending candidate and records a safe error code."""
    session.execute(text("""
        UPDATE scoring.candidato_rescoring SET last_attempt_at = clock_timestamp(), last_error = :code
        WHERE pending
    """), {"code": str(code)[:100]})
