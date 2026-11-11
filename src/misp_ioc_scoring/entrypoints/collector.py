"""Collector composition root; configuration is read once at startup."""
import json
import logging
from datetime import datetime, timezone
from functools import partial
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from misp_ioc_scoring.shared.configuration import load_configuration, resolve_secret
from misp_ioc_scoring.shared.database import engine_from_configuration, transaction
from misp_ioc_scoring.shared.errors import ConfigurationError, OperationalError
from misp_ioc_scoring.shared.logging import configure_logging
from misp_ioc_scoring.shared.misp.client import MispClient
from misp_ioc_scoring.collection.adapters.collection import CollectionSource
from misp_ioc_scoring.collection.application.collect import collect
from misp_ioc_scoring.collection.infrastructure.persistence.models import EndpointModel
from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
from misp_ioc_scoring.collection.infrastructure.scheduling.scheduler import build_scheduler


class Endpoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', hide_input_in_errors=True)
    id: str = Field(min_length=1, max_length=100)
    base_url: str
    credential_secret_ref: str = Field(repr=False)
    to_ids_only: bool | None = None
    allow_http: bool = False


def _run(source, repository, configuration):
    try:
        collect(source, repository, datetime.now(timezone.utc),
                overlap_minutes=configuration.collection_overlap_minutes,
                attempts=configuration.collection_retry_attempts,
                backoff_seconds=configuration.collection_retry_backoff_seconds)
    except OperationalError:
        # Status has already been persisted by the use case; do not expose payloads.
        pass


def main():
    configure_logging()
    configuration = load_configuration('collector')
    try:
        endpoints = [Endpoint.model_validate(e) for e in json.loads(
            resolve_secret(configuration.misp_endpoints_secret_ref).get_secret_value())]
        cadence = json.loads(resolve_secret(configuration.collection_cadence_secret_ref).get_secret_value())
        if not endpoints or len({e.id for e in endpoints}) != len(endpoints):
            raise ValueError
        import math
        for endpoint in endpoints:
            interval = float(cadence[endpoint.id])
            if not math.isfinite(interval) or interval <= 0:
                raise ValueError
    except (ValueError, TypeError, KeyError, ValidationError):
        raise ConfigurationError('COLLECTION_ENDPOINTS_OR_CADENCE') from None
    engine = engine_from_configuration(configuration)
    jobs = []
    for endpoint in endpoints:
        client = MispClient(endpoint.base_url, endpoint.credential_secret_ref,
                            configuration.misp_request_timeout_seconds, allow_http=endpoint.allow_http)
        to_ids = endpoint.to_ids_only if endpoint.to_ids_only is not None else configuration.misp_to_ids_only
        with transaction(engine) as session:
            stored = session.get(EndpointModel, endpoint.id)
            if stored is None:
                stored = EndpointModel(id=endpoint.id)
                session.add(stored)
            stored.base_url = endpoint.base_url
            stored.credential_secret_ref = endpoint.credential_secret_ref
            stored.interval_seconds = float(cadence[endpoint.id])
            stored.to_ids_only = to_ids
            stored.removal_ratio = configuration.reconcile_max_removal_ratio
            stored.version = client.version
        source = CollectionSource(client, endpoint.id, to_ids)
        repository = ObservationsRepository(engine, endpoint.id)
        jobs.append((endpoint.id, float(cadence[endpoint.id]), partial(_run, source, repository, configuration)))
    try:
        build_scheduler(jobs).start()
    finally:
        engine.dispose()


if __name__ == '__main__':
    try:
        main()
    except OperationalError as error:
        logging.getLogger(__name__).error('collector_startup_failed', extra={
            'event': 'collector_startup_failed', 'code': error.code})
        raise SystemExit(1) from None
