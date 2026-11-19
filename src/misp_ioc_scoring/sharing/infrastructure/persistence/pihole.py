from uuid import uuid4

from sqlalchemy import JSON, bindparam, text

from misp_ioc_scoring.shared.database import transaction


class Store:
    def __init__(self, engine, destination):
        self.engine = engine
        self.destination = destination

    def entries(self):
        with transaction(self.engine) as session:
            rows = session.execute(text(
                "SELECT * FROM sharing.pihole_entry WHERE destination=:destination"
            ), {"destination": self.destination}).mappings()
            return {row["hostname"]: dict(row) for row in rows}

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
