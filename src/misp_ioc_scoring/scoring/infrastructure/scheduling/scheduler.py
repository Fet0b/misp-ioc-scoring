from datetime import datetime, timezone

from apscheduler.triggers.cron import CronTrigger


def add_scoring_job(scheduler, job, cron):
    scheduler.add_job(job, CronTrigger.from_crontab(cron, timezone="UTC"),
                      id="simple-scoring", max_instances=1, coalesce=True,
                      next_run_time=datetime.now(timezone.utc))
