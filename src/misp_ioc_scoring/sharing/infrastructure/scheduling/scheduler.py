"""Lock, transactions and read ports for one Pi-hole cycle (no business rules here)."""
from contextlib import contextmanager

from sqlalchemy import text

from misp_ioc_scoring.collection.api import (active_blocking_values, source_generations, untrusted_sources,
                                             warninglist_entries)
from misp_ioc_scoring.scoring.api import blocking_decision, carioca_scores, current_carioca_run, effective_blocks
from misp_ioc_scoring.shared.database import transaction

PIHOLE_LOCK = 874203


class SqlSources:
    """`SourcesPort` over `collection.api`, inside one transaction."""

    def __init__(self, session):
        self.session = session

    def untrusted(self, now, max_age):
        return untrusted_sources(self.session, now, max_age)

    def generations(self):
        return source_generations(self.session)

    def active_values(self, types):
        return active_blocking_values(self.session, types)

    def warninglists(self):
        return warninglist_entries(self.session)


class SqlDecisions:
    """`DecisionsPort` over `scoring.api`, inside one transaction."""

    def __init__(self, session):
        self.session = session

    def effective_blocks(self):
        return effective_blocks(self.session)

    def decision(self, source, attribute_uuid):
        return blocking_decision(self.session, source, attribute_uuid=attribute_uuid)

    def current_carioca_run(self):
        return current_carioca_run(self.session)

    def carioca_scores(self, run_id, min_score):
        return list(carioca_scores(self.session, run_id, min_score=min_score))


class PiHoleRunner:
    """Context manager: Pi-hole lock, policy record and a REPEATABLE READ snapshot.

    Yields itself with `decisions` and `sources` ports, or None when another worker
    holds the lock. `fresh()` opens a new transaction for revalidation.
    """

    def __init__(self, engine, store):
        self.engine = engine
        self.store = store
        self._lock = None
        self._snapshot = None
        self.decisions = self.sources = None

    def __enter__(self):
        self._lock = transaction(self.engine)
        session = self._lock.__enter__()
        try:
            if not session.scalar(text(f"SELECT pg_try_advisory_xact_lock({PIHOLE_LOCK})")):
                self._lock.__exit__(None, None, None)
                self._lock = None
                return None
            self.store.record_policy(session)
            self._snapshot = transaction(self.engine)
            snapshot = self._snapshot.__enter__()
            snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            self.decisions, self.sources = SqlDecisions(snapshot), SqlSources(snapshot)
            return self
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise

    @contextmanager
    def fresh(self):
        with transaction(self.engine) as check:
            yield SqlDecisions(check), SqlSources(check)

    def __exit__(self, exc_type, exc, tb):
        for name in ("_snapshot", "_lock"):
            context = getattr(self, name)
            setattr(self, name, None)
            if context is not None:
                context.__exit__(exc_type, exc, tb)
        return False
