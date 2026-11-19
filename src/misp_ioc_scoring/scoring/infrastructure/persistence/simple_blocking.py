from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import JSON, bindparam, text

from misp_ioc_scoring.collection.api import blocking_snapshot, blocking_warninglist_membership
from misp_ioc_scoring.shared.database import transaction
from ...application.simple_blocking import evaluate

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


def run(engine, max_age_hours):
    run_id = uuid4()
    as_of = datetime.now(timezone.utc)
    params = {"id": run_id, "as_of": as_of}
    try:
        with transaction(engine) as session:
            if not session.scalar(text("SELECT pg_try_advisory_xact_lock(874202)")):
                return
            session.execute(text("SELECT pg_advisory_xact_lock(874201)"))
            as_of = params["as_of"] = datetime.now(timezone.utc)
            snapshot = blocking_snapshot(session)
            session.execute(text("""
                INSERT INTO scoring.execucao_bloqueio VALUES (:id, :as_of, NULL, 'default-v1', 'running')
            """), params)
            batch = []
            for row in evaluate(snapshot, as_of, timedelta(hours=max_age_hours), blocking_warninglist_membership):
                batch.append(dict(row, run_id=run_id))
                if len(batch) == 1000:
                    session.execute(_UPSERT, batch)
                    batch.clear()
            if batch:
                session.execute(_UPSERT, batch)
            session.execute(text("""
                UPDATE scoring.execucao_bloqueio SET finished_at=clock_timestamp(), status='completed' WHERE id=:id
            """), params)
    except Exception:
        with transaction(engine) as session:
            session.execute(text("""
                INSERT INTO scoring.execucao_bloqueio
                VALUES (:id, :as_of, clock_timestamp(), 'default-v1', 'failed')
                ON CONFLICT DO NOTHING
            """), params)
        raise
