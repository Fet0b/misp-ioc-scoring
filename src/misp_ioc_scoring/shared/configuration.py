"""Immutable startup configuration; file: and env: references resolve secrets."""
import math
import os
from pathlib import Path
from typing import Literal, Mapping

from apscheduler.triggers.cron import CronTrigger
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy.engine import make_url

from .errors import ConfigurationError
from .logging import register_secret


class Configuration(BaseModel):
    model_config = ConfigDict(frozen=True)
    service: Literal['collector', 'scoring-sharing', 'tools', 'migration']
    database_url: SecretStr
    misp_to_ids_only: bool = True
    score_max_age_hours: float = 48
    export_max_rows_per_sheet: int = 1000000
    export_output_dir: str | None = None
    misp_endpoints_secret_ref: str | None = Field(default=None, repr=False)
    collection_cadence_secret_ref: str | None = Field(default=None, repr=False)
    collection_overlap_minutes: float | None = None
    collection_retry_attempts: int | None = None
    collection_retry_backoff_seconds: float | None = None
    reconcile_max_removal_ratio: float | None = None
    misp_request_timeout_seconds: float | None = None
    scoring_daily_cron: str | None = None
    sharing_interval_seconds: float | None = None
    sharing_retry_attempts: int | None = None
    sharing_retry_backoff_seconds: float | None = None
    carioca_config_path: str | None = None
    carioca_top_n: int | None = None
    misp_peers_secret_ref: str | None = Field(default=None, repr=False)
    peer_minimum_scores_secret_ref: str | None = Field(default=None, repr=False)
    peer_credentials_secret_ref: str | None = Field(default=None, repr=False)


def resolve_secret(reference: str, environ: Mapping[str, str] | None = None) -> SecretStr:
    environ = os.environ if environ is None else environ
    try:
        kind, location = reference.split(':', 1)
        if kind == 'file' and Path(location).is_absolute():
            value = Path(location).read_text().rstrip('\r\n')
        elif kind == 'env':
            value = environ[location]
        else:
            raise ValueError
        if not value:
            raise ValueError
    except (OSError, KeyError, ValueError):
        raise ConfigurationError('SECRET_REF') from None
    register_secret(value)
    return SecretStr(value)


def load_configuration(service: str, environ: Mapping[str, str] | None = None) -> Configuration:
    env = dict(os.environ if environ is None else environ)
    if service not in {'collector', 'scoring-sharing', 'tools', 'migration'}:
        raise ConfigurationError('SERVICE')
    values: dict = {'service': service}

    def required(key: str) -> str:
        value = env.get(key, '')
        if not value.strip():
            raise ConfigurationError(key)
        return value

    database_url = required('DATABASE_URL')
    try:
        url = make_url(database_url)
        if url.drivername != 'postgresql+psycopg' or not url.host or not url.database:
            raise ValueError
    except Exception:
        raise ConfigurationError('DATABASE_URL') from None
    if url.password:
        register_secret(url.password)
    values['database_url'] = SecretStr(database_url)

    def number(key: str, *, integer=False, minimum=0, maximum=None, default=None, inclusive=False):
        raw = env.get(key, default)
        if raw is None or raw == '':
            raise ConfigurationError(key)
        try:
            value = int(raw) if integer else float(raw)
            if not math.isfinite(value) or value < minimum or (not inclusive and value == minimum):
                raise ValueError
            if maximum is not None and value > maximum:
                raise ValueError
        except (ValueError, TypeError):
            raise ConfigurationError(key) from None
        values[key.lower()] = value

    number('SCORE_MAX_AGE_HOURS', default='48')
    number('EXPORT_MAX_ROWS_PER_SHEET', integer=True, maximum=1048575, default='1000000')
    if service == 'collector':
        for key in ('MISP_ENDPOINTS_SECRET_REF', 'COLLECTION_CADENCE_SECRET_REF'):
            reference = required(key)
            if not reference.startswith(('file:/', 'env:')):
                raise ConfigurationError(key)
            values[key.lower()] = reference
        raw = env.get('MISP_TO_IDS_ONLY', 'true')
        if raw not in {'true', 'false'}:
            raise ConfigurationError('MISP_TO_IDS_ONLY')
        values['misp_to_ids_only'] = raw == 'true'
        number('COLLECTION_OVERLAP_MINUTES', inclusive=True)
        number('COLLECTION_RETRY_ATTEMPTS', integer=True)
        number('COLLECTION_RETRY_BACKOFF_SECONDS')
        number('RECONCILE_MAX_REMOVAL_RATIO', maximum=1, inclusive=True)
    if service in {'collector', 'scoring-sharing'}:
        number('MISP_REQUEST_TIMEOUT_SECONDS')
    if service == 'scoring-sharing':
        cron = required('SCORING_DAILY_CRON')
        try:
            CronTrigger.from_crontab(cron, timezone='UTC')
        except ValueError:
            raise ConfigurationError('SCORING_DAILY_CRON') from None
        values['scoring_daily_cron'] = cron
        for key in ('SHARING_INTERVAL_SECONDS', 'SHARING_RETRY_BACKOFF_SECONDS'):
            number(key)
        number('SHARING_RETRY_ATTEMPTS', integer=True)
        number('CARIOCA_TOP_N', integer=True)
        values['carioca_config_path'] = required('CARIOCA_CONFIG_PATH')
        for key in ('MISP_PEERS_SECRET_REF', 'PEER_MINIMUM_SCORES_SECRET_REF', 'PEER_CREDENTIALS_SECRET_REF'):
            reference = required(key)
            if not reference.startswith(('file:/', 'env:')):
                raise ConfigurationError(key)
            values[key.lower()] = reference
    if service == 'tools':
        values['export_output_dir'] = required('EXPORT_OUTPUT_DIR')
    try:
        return Configuration(**values)
    except ValidationError:
        raise ConfigurationError('SERVICE') from None
