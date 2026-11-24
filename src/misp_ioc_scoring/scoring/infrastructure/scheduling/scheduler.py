from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger


def add_scoring_job(scheduler, job, cron, job_id="simple-scoring"):
    """Daily UTC job, started once at boot; overlapping runs are coalesced."""
    scheduler.add_job(job, CronTrigger.from_crontab(cron, timezone="UTC"),
                      id=job_id, max_instances=1, coalesce=True,
                      next_run_time=datetime.now(timezone.utc))
