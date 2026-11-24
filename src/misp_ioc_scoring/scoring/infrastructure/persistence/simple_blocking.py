"""Locks, transaction and SQL behind the `BlockingStore` port of simple blocking."""
from contextlib import ExitStack

from sqlalchemy import JSON, DateTime, bindparam, text

from misp_ioc_scoring.collection.api import collection_snapshot
from misp_ioc_scoring.shared.database import transaction

SCORING_LOCK = 874202
COLLECTION_LOCK = 874201
RULE_VERSION = "default-v1"

_UPSERT = text("""
INSERT INTO scoring.decisao_bloqueio
(source_instance_id, attribute_uuid, attribute_id, run_id, generation, block, reason, as_of, expires_at, evidence)
VALUES (:source_instance_id, :attribute_uuid, :attribute_id, :run_id, :generation, :block,
        :reason, :as_of, :expires_at, :evidence)
ON CONFLICT (source_instance_id, attribute_uuid) DO UPDATE SET
attribute_id=excluded.attribute_id, run_id=excluded.run_id, generation=excluded.generation,
block=excluded.block, reason=excluded.reason, as_of=excluded.as_of,
expires_at=excluded.expires_at, evidence=excluded.evidence
""").bindparams(bindparam("evidence", type_=JSON))

_FAILED = text("""
INSERT INTO scoring.execucao_bloqueio
VALUES (:id, COALESCE(:as_of, clock_timestamp()), clock_timestamp(), :rule_version, 'failed')
ON CONFLICT DO NOTHING
""").bindparams(bindparam("as_of", type_=DateTime(timezone=True)))


class SqlBlockingStore:
    """`BlockingStore` over one open transaction holding both advisory locks."""

    def __init__(self, session, snapshot):
        self.session = session
        self.snapshot = snapshot
        self.run_id = None
        self.as_of = None

    def start(self, run_id, as_of):
        self.run_id, self.as_of = run_id, as_of
        self.session.execute(text(
            "INSERT INTO scoring.execucao_bloqueio VALUES (:id, :as_of, NULL, :rule_version, 'running')"
        ), {"id": run_id, "as_of": as_of, "rule_version": RULE_VERSION})

    def upsert(self, decisions):
        self.session.execute(_UPSERT, [dict(
            source_instance_id=d.source_instance_id, attribute_uuid=d.attribute_uuid,
            attribute_id=d.attribute_id, run_id=self.run_id, generation=d.generation,
            block=d.block, reason=d.reason.value, as_of=d.as_of, expires_at=d.expires_at,
            evidence=d.evidence.to_json()) for d in decisions])

    def finish(self, run_id):
        self.session.execute(text("""
            UPDATE scoring.execucao_bloqueio SET finished_at=clock_timestamp(), status='completed' WHERE id=:id
        """), {"id": run_id})


class BlockingRunner:
    """Context manager: locks, one transaction and the collection snapshot.

    Yields a `SqlBlockingStore`, or None when another worker holds the scoring lock.
    A failure rolls back the run and records it as `failed` without replacing the
    current decisions.
    """

    def __init__(self, engine, new_run_id):
        self.engine = engine
        self.new_run_id = new_run_id
        self._stack = None
        self._store = None

    def __enter__(self):
        self._stack = ExitStack()
        try:
            session = self._stack.enter_context(transaction(self.engine))
            if not session.scalar(text(f"SELECT pg_try_advisory_xact_lock({SCORING_LOCK})")):
                self._stack.close()
                self._stack = None
                return None
            session.execute(text(f"SELECT pg_advisory_xact_lock({COLLECTION_LOCK})"))
            self._store = SqlBlockingStore(session, collection_snapshot(session))
            return self._store
        except BaseException as error:
            self._fail(error)
            raise

    def __exit__(self, exc_type, exc, tb):
        if self._stack is None:
            return False
        if exc_type is None:
            self._stack.close()
        else:
            self._fail(exc)
        return False

    def _fail(self, error):
        stack, self._stack = self._stack, None
        if stack is not None:
            stack.__exit__(type(error), error, error.__traceback__)
        store = self._store
        with transaction(self.engine) as session:
            session.execute(_FAILED, {"id": store.run_id if store and store.run_id else self.new_run_id(),
                                      "as_of": store.as_of if store else None,
                                      "rule_version": RULE_VERSION})
