from uuid import uuid4

from sqlalchemy import JSON, bindparam, text
from sqlalchemy.dialects.postgresql import insert

from misp_ioc_scoring.sharing.domain.pihole_entries import ManagedEntry

from .models import PiHolePolicyModel

from misp_ioc_scoring.shared.database import transaction


class Store:
    def __init__(self, engine, destination, interval_seconds, password_secret_ref, model="default", min_score=None):
        self.engine = engine
        self.model = model
        self.min_score = min_score
        self.destination = destination
        self.interval_seconds = interval_seconds
        self.password_secret_ref = password_secret_ref

    def record_policy(self, session):
        query = insert(PiHolePolicyModel).values(
            destination=self.destination, model=str(self.model), min_score=self.min_score,
            interval_seconds=self.interval_seconds, password_secret_ref=self.password_secret_ref,
        )
        session.execute(query.on_conflict_do_update(
            index_elements=["destination"],
            set_={key: query.excluded[key] for key in
                  ("model", "min_score", "interval_seconds", "password_secret_ref")},
        ))

    def entries(self):
        with transaction(self.engine) as session:
            rows = session.execute(text(
                "SELECT * FROM sharing.pihole_entry WHERE destination=:destination"
            ), {"destination": self.destination}).mappings()
            return {row["hostname"]: ManagedEntry(row["hostname"], row["marker"], row["remote_id"], row["status"],
                                                  row["evidence"]) for row in rows}

    def save(self, host, marker, remote_id, status, evidence):
        query = text("""
            INSERT INTO sharing.pihole_entry VALUES (:destination,:host,:marker,:remote_id,:status,:evidence)
            ON CONFLICT (destination,hostname) DO UPDATE SET marker=excluded.marker,
            remote_id=excluded.remote_id,status=excluded.status,evidence=excluded.evidence
        """).bindparams(bindparam("evidence", type_=JSON))
        with transaction(self.engine) as session:
            session.execute(query, dict(destination=self.destination, host=host, marker=marker,
                                        remote_id=remote_id, status=status, evidence=evidence))

    def attempt(self, host, operation, status):
        with transaction(self.engine) as session:
            session.execute(text("""
                INSERT INTO sharing.pihole_attempt (id,destination,hostname,operation,status)
                VALUES (:id,:destination,:host,:operation,:status)
            """), dict(id=uuid4(), destination=self.destination, host=host,
                      operation=operation, status=status))
