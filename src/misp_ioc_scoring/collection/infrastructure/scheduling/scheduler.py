"""One synchronous process, with one non-overlapping job per endpoint."""
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor


def build_scheduler(jobs):
    scheduler = BlockingScheduler(timezone='UTC', executors={'default': ThreadPoolExecutor(1)},
                                  job_defaults={'max_instances': 1, 'coalesce': True})
    for source_id, interval_seconds, function in jobs:
        scheduler.add_job(function, 'interval', seconds=interval_seconds,
                          id=source_id, max_instances=1, coalesce=True,
                          next_run_time=datetime.now(timezone.utc))
    return scheduler
