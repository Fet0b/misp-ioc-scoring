"""Lock and REPEATABLE READ snapshot for one MISP sharing round."""
from sqlalchemy import text

from misp_ioc_scoring.collection.api import observations_of, warninglist_entries
from misp_ioc_scoring.scoring.api import carioca_scores, current_carioca_run
from misp_ioc_scoring.shared.database import transaction

SHARING_LOCK = 874205


class SqlSharingReader:
    """`SharingReader` over `scoring.api` and `collection.api` inside one transaction."""

    def __init__(self, session):
        self.session = session

    def current_carioca_run(self):
        return current_carioca_run(self.session)

    def carioca_scores(self, run_id):
        return list(carioca_scores(self.session, run_id))

    def observations(self, ioc_ids):
        return observations_of(self.session, ioc_ids)

    def warninglists(self):
        return warninglist_entries(self.session)


class MispSharingRunner:
    """Yields a `SqlSharingReader`, or None when another worker holds the sharing lock."""

    def __init__(self, engine):
        self.engine = engine
        self._lock = self._snapshot = None

    def __enter__(self):
        self._lock = transaction(self.engine)
        session = self._lock.__enter__()
        try:
            if not session.scalar(text(f"SELECT pg_try_advisory_xact_lock({SHARING_LOCK})")):
                self.__exit__(None, None, None)
                return None
            self._snapshot = transaction(self.engine)
            snapshot = self._snapshot.__enter__()
            snapshot.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            return SqlSharingReader(snapshot)
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise

    def __exit__(self, exc_type, exc, tb):
        for name in ("_snapshot", "_lock"):
            context = getattr(self, name)
            setattr(self, name, None)
            if context is not None:
                context.__exit__(exc_type, exc, tb)
        return False
