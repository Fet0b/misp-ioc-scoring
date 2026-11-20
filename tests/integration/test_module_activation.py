import pytest

from misp_ioc_scoring.entrypoints import collector, scoring_sharing


@pytest.mark.parametrize("simple,pihole,expected", [
    (False, False, []), (True, False, ["score"]), (True, True, ["score", "share"]),
])
def test_workers_start_only_enabled_jobs(monkeypatch, simple, pihole, expected):
    variables = {
        "COLLECTION_ENABLED": "false",
        "SCORING_SIMPLE_ENABLED": str(simple).lower(),
        "SCORING_CARIOCA_ENABLED": "false",
        "SHARING_MISP_ENABLED": "false",
        "SHARING_PIHOLE_ENABLED": str(pihole).lower(),
    }
    if simple:
        variables.update(DATABASE_URL="postgresql+psycopg://scoring@db/test", SCORING_DAILY_CRON="0 3 * * *")
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    if pihole:
        variables.update(PIHOLE_URL="https://pihole.example", PIHOLE_PASSWORD_SECRET_REF="env:TEST_PIN",
                         PIHOLE_INTERVAL_SECONDS="60", TEST_PIN="fake-password")
    else:
        monkeypatch.delenv("PIHOLE_PASSWORD_SECRET_REF", raising=False)
    for key, value in variables.items():
        monkeypatch.setenv(key, value)
    events = []

    class Engine:
        def dispose(self):
            events.append("dispose")

    class Scheduler:
        def __init__(self, timezone):
            self.jobs = []

        def add_job(self, job, *args, **kwargs):
            self.jobs.append(job)

        def start(self):
            for job in self.jobs:
                job()

    monkeypatch.setattr(scoring_sharing, "BlockingScheduler", Scheduler)
    monkeypatch.setattr(scoring_sharing, "engine_from_configuration", lambda config: Engine())
    monkeypatch.setattr(scoring_sharing, "run", lambda *args: events.append("score"))
    monkeypatch.setattr(scoring_sharing, "sync", lambda *args: events.append("share"))
    collector.main()
    scoring_sharing.main()
    assert events == expected + (["dispose"] if simple else [])
