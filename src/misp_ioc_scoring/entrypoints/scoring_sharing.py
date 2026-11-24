"""Composition root for scoring and defensive DNS sharing."""
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from uuid import uuid4

from apscheduler.schedulers.blocking import BlockingScheduler

from misp_ioc_scoring.scoring.api import CariocaConfigurationError, ScoreModel, load_carioca_configuration
from misp_ioc_scoring.scoring.application.score_population import run_carioca
from misp_ioc_scoring.scoring.application.simple_blocking import run_blocking
from misp_ioc_scoring.scoring.infrastructure.persistence.carioca import CariocaRunner
from misp_ioc_scoring.scoring.infrastructure.persistence.simple_blocking import BlockingRunner
from misp_ioc_scoring.scoring.infrastructure.scheduling.scheduler import add_scoring_job
from misp_ioc_scoring.sharing.adapters.pihole import PiHole
from misp_ioc_scoring.sharing.infrastructure.persistence.pihole import Store
from misp_ioc_scoring.sharing.infrastructure.scheduling.scheduler import sync
from misp_ioc_scoring.shared.configuration import enabled, load_configuration, resolve_secret
from misp_ioc_scoring.shared.database import engine_from_configuration
from misp_ioc_scoring.shared.errors import ConfigurationError, OperationalError
from misp_ioc_scoring.shared.logging import configure_logging

log = logging.getLogger(__name__)


def safe_job(name, job):
    try:
        job()
    except Exception:
        log.error("%s_job_failed", name)


def run_simple_blocking(engine, max_age_hours):
    """Simple blocking job: lock, read `as_of` once, evaluate and publish."""
    with BlockingRunner(engine, uuid4) as store:
        if store is None:
            return None
        as_of = datetime.now(timezone.utc)
        return run_blocking(as_of, store.snapshot, timedelta(hours=max_age_hours), store)


def run_carioca_scoring(engine, configuration):
    """CARIOCA job: lock, read `as_of` once, recalculate the whole population."""
    with CariocaRunner(engine, uuid4) as store:
        if store is None:
            return None
        as_of = datetime.now(timezone.utc)
        return run_carioca(as_of, store.snapshot, configuration, store)


def approved_carioca_configuration(path):
    try:
        return load_carioca_configuration(path).require_approved()
    except CariocaConfigurationError as error:
        raise ConfigurationError(error.code) from None


def main():
    flags = [enabled(key) for key in ("SCORING_SIMPLE_ENABLED", "SCORING_CARIOCA_ENABLED",
                                    "SHARING_PIHOLE_ENABLED", "SHARING_MISP_ENABLED")]
    if not any(flags):
        return
    config = load_configuration("scoring-sharing")
    carioca = approved_carioca_configuration(config.carioca_config_path) if config.carioca_scoring_enabled else None
    engine = engine_from_configuration(config)
    try:
        scheduler = BlockingScheduler(timezone="UTC")
        if config.simple_scoring_enabled:
            score = partial(safe_job, "scoring", partial(run_simple_blocking, engine, config.score_max_age_hours))
            add_scoring_job(scheduler, score, config.scoring_daily_cron)
        if carioca is not None:
            daily = partial(safe_job, "carioca", partial(run_carioca_scoring, engine, carioca))
            add_scoring_job(scheduler, daily, config.scoring_daily_cron, "carioca-scoring")
        if config.pihole_enabled:
            client = PiHole(config.pihole_url, resolve_secret(config.pihole_password_secret_ref).get_secret_value(),
                            allow_http=enabled("PIHOLE_ALLOW_HTTP"))
            store = Store(engine, config.pihole_url, config.pihole_interval_seconds,
                          config.pihole_password_secret_ref, ScoreModel(config.pihole_score_model),
                          config.pihole_carioca_min_score)
            share = partial(safe_job, "pihole", partial(sync, engine, client, store, config.score_max_age_hours))
            scheduler.add_job(share, "interval", seconds=config.pihole_interval_seconds,
                              id="pihole", max_instances=1, coalesce=True,
                              next_run_time=datetime.now(timezone.utc))
        scheduler.start()
    finally:
        engine.dispose()


if __name__ == "__main__":
    configure_logging()
    try:
        main()
    except OperationalError as error:
        log.error("scoring_sharing_startup_failed", extra={"code": error.code})
        raise SystemExit(1) from None
