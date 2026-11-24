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
    monkeypatch.setattr(scoring_sharing, "run_simple_blocking", lambda *args: events.append("score"))
    monkeypatch.setattr(scoring_sharing, "sync_pihole", lambda *args: events.append("share"))
    collector.main()
    scoring_sharing.main()
    assert events == expected + (["dispose"] if simple else [])


def _carioca_env(monkeypatch, path):
    for key, value in {"SCORING_SIMPLE_ENABLED": "false", "SCORING_CARIOCA_ENABLED": "true",
                       "SHARING_MISP_ENABLED": "false", "SHARING_PIHOLE_ENABLED": "false",
                       "DATABASE_URL": "postgresql+psycopg://scoring@db/test",
                       "SCORING_DAILY_CRON": "0 3 * * *", "CARIOCA_CONFIG_PATH": str(path)}.items():
        monkeypatch.setenv(key, value)


def test_carioca_requires_approved_configuration(monkeypatch, tmp_path):
    import json
    from pathlib import Path
    from misp_ioc_scoring.shared.errors import ConfigurationError

    versioned = Path(__file__).resolve().parents[2] / "config" / "carioca-orgc-proxy-v3.yaml"
    _carioca_env(monkeypatch, versioned)
    with pytest.raises(ConfigurationError, match="CARIOCA_CONFIGURATION_NOT_APPROVED"):
        scoring_sharing.main()

    from tests.support.carioca import config_dict
    approved = tmp_path / "carioca.yaml"
    approved.write_text(json.dumps(config_dict()))
    _carioca_env(monkeypatch, approved)
    events = []

    class Engine:
        def dispose(self):
            events.append("dispose")

    class Scheduler:
        def __init__(self, timezone):
            self.jobs = []

        def add_job(self, job, *args, **kwargs):
            self.jobs.append(kwargs["id"])
            job()

        def start(self):
            pass

    monkeypatch.setattr(scoring_sharing, "BlockingScheduler", Scheduler)
    monkeypatch.setattr(scoring_sharing, "engine_from_configuration", lambda config: Engine())
    monkeypatch.setattr(scoring_sharing, "run_carioca_scoring", lambda *args: events.append("carioca"))
    scoring_sharing.main()
    assert events == ["carioca", "dispose"]


def test_misp_sharing_job_requires_carioca_and_registers_policy(monkeypatch, tmp_path):
    import json
    from tests.support.carioca import config_dict

    approved = tmp_path / "carioca.yaml"
    approved.write_text(json.dumps(config_dict()))
    _carioca_env(monkeypatch, approved)
    for key, value in {"SHARING_MISP_ENABLED": "true", "MISP_PEERS_SECRET_REF": "env:TEST_PEERS",
                       "SHARING_INTERVAL_SECONDS": "300", "SHARING_RETRY_ATTEMPTS": "3",
                       "SHARING_RETRY_BACKOFF_SECONDS": "5", "MISP_REQUEST_TIMEOUT_SECONDS": "30"}.items():
        monkeypatch.setenv(key, value)
    events = []

    class Engine:
        def dispose(self):
            events.append("dispose")

    class Scheduler:
        def __init__(self, timezone):
            pass

        def add_job(self, job, *args, **kwargs):
            events.append(kwargs["id"])

        def start(self):
            pass

    class Store:
        def __init__(self, engine, policy):
            pass

        def record_policy(self, at):
            events.append("policy")

    monkeypatch.setattr(scoring_sharing, "BlockingScheduler", Scheduler)
    monkeypatch.setattr(scoring_sharing, "engine_from_configuration", lambda config: Engine())
    monkeypatch.setattr(scoring_sharing, "load_sharing_policy", lambda config: object())
    monkeypatch.setattr(scoring_sharing, "SqlSharingStore", Store)
    monkeypatch.setattr(scoring_sharing, "misp_synchronization", lambda config, policy: object())
    scoring_sharing.main()
    assert events == ["carioca-scoring", "policy", "misp-sharing", "dispose"]
