"""Pi-hole use case: plan the desired exact hostnames and reconcile them safely.

Only entries proven to be ours (marker, remote ID, default group, enabled) are ever
changed or removed; manual entries and entries of unavailable sources are preserved.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID, uuid4

from misp_ioc_scoring.collection.api import DOMAIN_TYPES, dns_hostname, warninglist_index
from misp_ioc_scoring.scoring.api import BLOCKABLE_TYPES, BlockingReason, ScoreModel

from ..domain.pihole_entries import ManagedEntry
from ..domain.pihole_policy import eligible

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PiHolePolicy:
    model: ScoreModel
    min_score: float | None
    max_age: timedelta


class SourcesPort(Protocol):
    def untrusted(self, now, max_age) -> set: ...
    def generations(self) -> dict: ...
    def active_values(self, types) -> list: ...
    def warninglists(self) -> dict: ...


class DecisionsPort(Protocol):
    def effective_blocks(self) -> list: ...
    def decision(self, source, attribute_uuid): ...
    def current_carioca_run(self): ...
    def carioca_scores(self, run_id, min_score): ...


class PiHolePort(Protocol):
    def validate(self): ...
    def lookup(self, host): ...
    def add(self, host, marker): ...
    def remove(self, host): ...
    def close(self): ...


class PiHoleStore(Protocol):
    def entries(self) -> dict: ...
    def save(self, host, marker, remote_id, status, evidence): ...
    def attempt(self, host, operation, status): ...


def _marker():
    return "misp-ioc-scoring:" + uuid4().hex


def reconcile(client, store, desired, unavailable, revalidate=lambda operation, host, evidence: True):
    entries = store.entries()
    for host in sorted(set(entries) | set(desired)):
        entry = entries.get(host)
        new = desired.get(host, [])
        old = entry.evidence if entry else []
        retained = [item for item in old if item["source"] in unavailable]
        evidence = new + retained
        if not new and (not entry or retained or entry.status == "removed"):
            continue

        operation = "add" if new else "remove"
        try:
            if not revalidate(operation, host, new or old):
                continue
            remote = client.lookup(host)
            marker = entry.marker if entry else _marker()
            remote_id = entry.remote_id if entry else None
            if remote is not None and (not entry or not ManagedEntry(host, marker, remote_id).is_owned_by(remote)):
                if entry:
                    store.save(host, marker, remote_id, "unverified", evidence or old)
                log.warning("pihole_entry_ownership_unverified")
                continue
            if new and remote is None:
                if entry and entry.status == "unverified":
                    continue
                if entry and entry.status != "pending":
                    marker = _marker()
                store.save(host, marker, None, "pending", evidence)
                store.attempt(host, operation, "pending")
                if not revalidate(operation, host, new):
                    continue
                client.add(host, marker)
                remote = client.lookup(host)
                if not ManagedEntry(host, marker).is_owned_by(remote):
                    raise ValueError("unconfirmed_add")
            if new:
                store.save(host, marker, remote.id, "confirmed", evidence)
            else:
                if remote:
                    store.attempt(host, operation, "pending")
                    if not revalidate(operation, host, old):
                        continue
                    if not ManagedEntry(host, marker, remote.id).is_owned_by(client.lookup(host)):
                        store.save(host, marker, remote_id, "unverified", old)
                        log.warning("pihole_entry_ownership_unverified")
                        continue
                    client.remove(host)
                    if client.lookup(host) is not None:
                        raise ValueError("unconfirmed_remove")
                store.save(host, marker, remote_id, "removed", [])
            store.attempt(host, operation, "confirmed")
        except Exception:
            store.attempt(host, operation, "ambiguous")
            log.warning("pihole_sync_attempt_unconfirmed")


def default_desired(decisions, sources, unavailable, generations):
    """Hosts of effective simple-blocking decisions of trusted sources."""
    blocks = {(row.source_instance_id, row.attribute_uuid): row for row in decisions.effective_blocks()}
    desired = defaultdict(list)
    current_hosts = {}
    for source, attribute, kind, category, value in sources.active_values(BLOCKABLE_TYPES):
        host = dns_hostname(kind, value)
        current_hosts[(source, attribute)] = host
        row = blocks.get((source, attribute))
        if not eligible(ScoreModel.DEFAULT, block=row is not None, trusted=source not in unavailable):
            continue
        if host:
            desired[host].append({"source": source, "attribute": str(attribute), "kind": kind,
                                  "category": category, "model": "default", "as_of": row.as_of.isoformat(),
                                  "rule_version": row.rule_version, "generation": generations[source]})
    return desired, current_hosts


def carioca_desired(decisions, sources, run, cutoff, unavailable, generations):
    """Hosts of current CARIOCA scores at or above `cutoff` (no top-N); domains and hostnames only."""
    entries = sources.warninglists()
    indexes = {}
    desired = defaultdict(list)
    for score in decisions.carioca_scores(run.id, cutoff):
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


def plan_and_reconcile(as_of, decisions: DecisionsPort, sources: SourcesPort, pihole: PiHolePort,
                       store: PiHoleStore, policy: PiHolePolicy, *, fresh, clock=None):
    """One Pi-hole cycle. `fresh()` opens a new read context `(decisions, sources)` for revalidation."""
    clock = clock or (lambda: as_of)
    unavailable = sources.untrusted(as_of, policy.max_age)
    generations = sources.generations()
    if policy.model == ScoreModel.CARIOCA:
        run = decisions.current_carioca_run()
        if run is None or run.finished_at <= as_of - policy.max_age:
            log.warning("pihole_carioca_score_stale", extra={
                "event": "pihole_carioca_score_stale", "code": "no_run" if run is None else "stale"})
            return
        desired = carioca_desired(decisions, sources, run, policy.min_score, unavailable, generations)

        def revalidate(operation, host, evidence):
            with fresh() as (check_decisions, check_sources):
                if check_sources.generations() != generations:
                    return False
                current = check_decisions.current_carioca_run()
                if current is None or current.id != run.id:
                    return False
                if operation == "remove" and {item["source"] for item in evidence} & check_sources.untrusted(
                        clock(), policy.max_age):
                    return False
                return True
    else:
        desired, current_hosts = default_desired(decisions, sources, unavailable, generations)

        def revalidate(operation, host, evidence):
            with fresh() as (check_decisions, check_sources):
                if check_sources.generations() != generations:
                    return False
                before = clock()
                if operation == "add":
                    return all(
                        (row := check_decisions.decision(item["source"], UUID(item["attribute"])))
                        and row.block and row.as_of.isoformat() == item["as_of"]
                        for item in evidence)
                if {item["source"] for item in evidence} & check_sources.untrusted(before, policy.max_age):
                    return False
                for item in evidence:
                    row = check_decisions.decision(item["source"], UUID(item["attribute"]))
                    if (row is None or row.reason in {BlockingReason.STALE, BlockingReason.INDETERMINATE}
                            or (row.block and current_hosts.get((item["source"], UUID(item["attribute"]))) == host)):
                        return False
                return True

    try:
        pihole.validate()
        reconcile(pihole, store, desired, unavailable, revalidate)
    finally:
        pihole.close()
