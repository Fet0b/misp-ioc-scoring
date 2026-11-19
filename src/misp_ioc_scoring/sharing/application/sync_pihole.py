"""Reconcile exact DNS entries while protecting manually managed records."""
import logging
from uuid import uuid4

log = logging.getLogger(__name__)


def reconcile(client, store, desired, unavailable, revalidate=lambda operation, host, evidence: True):
    entries = store.entries()
    for host in sorted(set(entries) | set(desired)):
        entry = entries.get(host)
        new = desired.get(host, [])
        old = entry["evidence"] if entry else []
        retained = [item for item in old if item["source"] in unavailable]
        evidence = new + retained
        if not new and (not entry or retained or entry["status"] == "removed"):
            continue

        operation = "add" if new else "remove"
        try:
            if not revalidate(operation, host, new or old):
                continue
            remote = client.lookup(host)
            marker = entry["marker"] if entry else "misp-ioc-scoring:" + uuid4().hex
            remote_id = entry["remote_id"] if entry else None
            if remote is not None:
                marked = entry and remote.get("comment") == marker
                identity_matches = remote_id is None or remote.get("id") == remote_id
                if not marked or not identity_matches or remote.get("id") is None:
                    if entry:
                        store.save(host, marker, remote_id, "unverified", evidence or old)
                    log.warning("pihole_entry_ownership_unverified")
                    continue
            if new and remote is None:
                if entry and entry["status"] == "unverified":
                    continue
                if entry and entry["status"] != "pending":
                    marker = "misp-ioc-scoring:" + uuid4().hex
                store.save(host, marker, None, "pending", evidence)
                store.attempt(host, operation, "pending")
                if not revalidate(operation, host, new):
                    continue
                client.add(host, marker)
                remote = client.lookup(host)
                if not remote or remote.get("comment") != marker or remote.get("id") is None:
                    raise ValueError("unconfirmed_add")
            if new:
                store.save(host, marker, remote["id"], "confirmed", evidence)
            else:
                if remote:
                    store.attempt(host, operation, "pending")
                    if not revalidate(operation, host, old):
                        continue
                    client.remove(host)
                    if client.lookup(host) is not None:
                        raise ValueError("unconfirmed_remove")
                store.save(host, marker, remote_id, "removed", [])
            store.attempt(host, operation, "confirmed")
        except Exception:
            store.attempt(host, operation, "ambiguous")
            log.warning("pihole_sync_attempt_unconfirmed")
