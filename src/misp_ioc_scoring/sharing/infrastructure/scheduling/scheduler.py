"""Compose one Pi-hole reconciliation cycle using module public readers."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text

from misp_ioc_scoring.collection.api import active_blocking_values, blocking_generations, unavailable_blocking_sources
from misp_ioc_scoring.scoring.api import blocking_decision, effective_blocks
from misp_ioc_scoring.shared.database import transaction
from ...application.sync_pihole import reconcile
from ...domain.pihole_hostname import hostname
from ...domain.pihole_policy import eligible


def sync(engine, client, store, max_age_hours):
    with transaction(engine) as session:
        if not session.scalar(text("SELECT pg_try_advisory_xact_lock(874203)")):
            return
        store.record_policy(session)
        with transaction(engine) as snapshot:
            snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            unavailable = unavailable_blocking_sources(
                snapshot, datetime.now(timezone.utc), timedelta(hours=max_age_hours))
            generations = blocking_generations(snapshot)
            blocks = {(row["source_instance_id"], row["attribute_uuid"]): row
                      for row in effective_blocks(snapshot)}
            desired = defaultdict(list)
            current_hosts = {}
            for source, attribute, kind, category, value in active_blocking_values(snapshot):
                host = hostname(kind, value)
                current_hosts[(source, attribute)] = host
                row = blocks.get((source, attribute))
                if not eligible("default", block=row is not None, trusted=source not in unavailable):
                    continue
                if host:
                    desired[host].append({"source": source, "attribute": str(attribute),
                                          "kind": kind, "category": category, "model": "default",
                                          "as_of": row["as_of"].isoformat(),
                                          "rule_version": row["rule_version"],
                                          "generation": generations[source]})

        def revalidate(operation, host, evidence):
            with transaction(engine) as check:
                if blocking_generations(check) != generations:
                    return False
                before = datetime.now(timezone.utc)
                if operation == "add":
                    return all(
                        (row := blocking_decision(check, item["source"], attribute_uuid=UUID(item["attribute"])))
                        and row["block"] and row["as_of"].isoformat() == item["as_of"]
                        for item in evidence)
                if {item["source"] for item in evidence} & unavailable_blocking_sources(
                    check, before, timedelta(hours=max_age_hours)):
                    return False
                for item in evidence:
                    row = blocking_decision(check, item["source"], attribute_uuid=UUID(item["attribute"]))
                    if (row is None or row["reason"] in {"stale", "indeterminate"}
                            or (row["block"] and current_hosts.get((item["source"], UUID(item["attribute"]))) == host)):
                        return False
                return True

        try:
            client.validate()
            reconcile(client, store, desired, unavailable, revalidate)
        finally:
            client.close()
