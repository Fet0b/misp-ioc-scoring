"""Compose one Pi-hole reconciliation cycle using module public readers."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text

import logging

from misp_ioc_scoring.collection.api import (DOMAIN_TYPES, active_blocking_values, dns_hostname, source_generations,
                                             untrusted_sources, warninglist_entries, warninglist_index)
from misp_ioc_scoring.scoring.api import (BLOCKABLE_TYPES, BlockingReason, ScoreModel, blocking_decision,
                                          carioca_scores, current_carioca_run, effective_blocks)
from misp_ioc_scoring.shared.database import transaction
from ...application.sync_pihole import reconcile
from ...domain.pihole_policy import eligible


log = logging.getLogger(__name__)


def carioca_desired(snapshot, run, cutoff, unavailable, generations):
    """Hosts of current CARIOCA scores at or above `cutoff` (no top-N); domains and hostnames only."""
    entries = warninglist_entries(snapshot)
    indexes = {}
    desired = defaultdict(list)
    for score in carioca_scores(snapshot, run.id, min_score=cutoff):
        source = score.source_instance_id
        if score.type not in DOMAIN_TYPES or not eligible(
                ScoreModel.CARIOCA, block=None, score=score.priority_score, cutoff=cutoff,
                trusted=source not in unavailable):
            continue
        index = indexes.setdefault(source, warninglist_index(entries.get(source, ()), "strict"))
        if index.match(score.type, score.normalized_value, "strict") is not False:
            continue
        host = dns_hostname(score.type, score.normalized_value)
        if host:
            desired[host].append({"source": source, "attribute": str(score.attribute_uuid), "kind": score.type,
                                  "model": "carioca", "as_of": score.as_of.isoformat(),
                                  "priority_score": score.priority_score, "scoring_run_id": str(run.id),
                                  "generation": generations[source]})
    return desired


def sync(engine, client, store, max_age_hours):
    if store.model == ScoreModel.CARIOCA:
        return sync_carioca(engine, client, store, max_age_hours)
    with transaction(engine) as session:
        if not session.scalar(text("SELECT pg_try_advisory_xact_lock(874203)")):
            return
        store.record_policy(session)
        with transaction(engine) as snapshot:
            snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            unavailable = untrusted_sources(
                snapshot, datetime.now(timezone.utc), timedelta(hours=max_age_hours))
            generations = source_generations(snapshot)
            blocks = {(row.source_instance_id, row.attribute_uuid): row
                      for row in effective_blocks(snapshot)}
            desired = defaultdict(list)
            current_hosts = {}
            for source, attribute, kind, category, value in active_blocking_values(snapshot, BLOCKABLE_TYPES):
                host = dns_hostname(kind, value)
                current_hosts[(source, attribute)] = host
                row = blocks.get((source, attribute))
                if not eligible(ScoreModel.DEFAULT, block=row is not None, trusted=source not in unavailable):
                    continue
                if host:
                    desired[host].append({"source": source, "attribute": str(attribute),
                                          "kind": kind, "category": category, "model": "default",
                                          "as_of": row.as_of.isoformat(),
                                          "rule_version": row.rule_version,
                                          "generation": generations[source]})

        def revalidate(operation, host, evidence):
            with transaction(engine) as check:
                if source_generations(check) != generations:
                    return False
                before = datetime.now(timezone.utc)
                if operation == "add":
                    return all(
                        (row := blocking_decision(check, item["source"], attribute_uuid=UUID(item["attribute"])))
                        and row.block and row.as_of.isoformat() == item["as_of"]
                        for item in evidence)
                if {item["source"] for item in evidence} & untrusted_sources(
                    check, before, timedelta(hours=max_age_hours)):
                    return False
                for item in evidence:
                    row = blocking_decision(check, item["source"], attribute_uuid=UUID(item["attribute"]))
                    if (row is None or row.reason in {BlockingReason.STALE, BlockingReason.INDETERMINATE}
                            or (row.block and current_hosts.get((item["source"], UUID(item["attribute"]))) == host)):
                        return False
                return True

        try:
            client.validate()
            reconcile(client, store, desired, unavailable, revalidate)
        finally:
            client.close()


def sync_carioca(engine, client, store, max_age_hours):
    """Pi-hole from CARIOCA scores; a missing or stale current run sends nothing and keeps entries."""
    max_age = timedelta(hours=max_age_hours)
    with transaction(engine) as session:
        if not session.scalar(text("SELECT pg_try_advisory_xact_lock(874203)")):
            return
        store.record_policy(session)
        with transaction(engine) as snapshot:
            snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            now = datetime.now(timezone.utc)
            run = current_carioca_run(snapshot)
            if run is None or run.finished_at <= now - max_age:
                log.warning("pihole_carioca_score_stale", extra={
                    "event": "pihole_carioca_score_stale", "code": "no_run" if run is None else "stale"})
                return
            unavailable = untrusted_sources(snapshot, now, max_age)
            generations = source_generations(snapshot)
            desired = carioca_desired(snapshot, run, store.min_score, unavailable, generations)

        def revalidate(operation, host, evidence):
            with transaction(engine) as check:
                if source_generations(check) != generations:
                    return False
                current = current_carioca_run(check)
                if current is None or current.id != run.id:
                    return False
                if operation == "remove" and {item["source"] for item in evidence} & untrusted_sources(
                        check, datetime.now(timezone.utc), max_age):
                    return False
                return True

        try:
            client.validate()
            reconcile(client, store, desired, unavailable, revalidate)
        finally:
            client.close()
