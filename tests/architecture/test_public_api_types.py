"""Public APIs return immutable domain types, never ORM models, Row or RowMapping."""
import dataclasses
import inspect
from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Row, RowMapping

from misp_ioc_scoring.collection import api as collection_api
from misp_ioc_scoring.scoring import api as scoring_api
from misp_ioc_scoring.shared.database import Base, transaction

FORBIDDEN = (Base, Row, RowMapping)
VERSIONED_CONFIG = Path(__file__).resolve().parents[2] / 'config' / 'carioca-orgc-proxy-v3.yaml'


def walk(value, path='result', seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen or isinstance(value, (str, bytes, int, float, bool, type(None), datetime)):
        return
    seen.add(id(value))
    assert not isinstance(value, FORBIDDEN), f'{path} is {type(value).__name__}'
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for field in dataclasses.fields(value):
            walk(getattr(value, field.name), f'{path}.{field.name}', seen)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            walk(key, f'{path}[key]', seen)
            walk(item, f'{path}[{key!r}]', seen)
    elif isinstance(value, Iterable):
        for index, item in enumerate(value):
            walk(item, f'{path}[{index}]', seen)


def public_functions(module):
    return {name for name, item in vars(module).items()
            if inspect.isfunction(item) and item.__module__ == module.__name__ and not name.startswith('_')}


def calls(session, engine):
    from misp_ioc_scoring.collection.api import collection_snapshot

    snapshot = collection_snapshot(session)
    observation = snapshot.observations[0]
    now = datetime.now(timezone.utc)
    reader = collection_api.CollectionReader(engine)
    return {
        collection_api: {
            'collection_snapshot': lambda: snapshot,
            'untrusted_sources': lambda: collection_api.untrusted_sources(session, now, timedelta(hours=48)),
            'source_generations': lambda: collection_api.source_generations(session),
            'current_input_revisions': lambda: collection_api.current_input_revisions(session, [observation.ioc_id]),
            'warninglist_entries': lambda: collection_api.warninglist_entries(session),
            'warninglist_index': lambda: collection_api.warninglist_index(snapshot.warninglists, 'strict'),
            'active_blocking_values': lambda: collection_api.active_blocking_values(session, ('domain',)),
            'dns_hostname': lambda: collection_api.dns_hostname('domain', 'example.org'),
            'CollectionReader': lambda: (reader.current_input_revision(observation.ioc_id),
                                         reader.unsupported_warninglist_entries(), reader.rejections(),
                                         reader.rejection_counts()),
        },
        scoring_api: {
            'blocking_decision': lambda: scoring_api.blocking_decision(
                session, observation.source_instance_id, attribute_uuid=observation.attribute_uuid),
            'effective_blocks': lambda: scoring_api.effective_blocks(session),
            'load_carioca_configuration': lambda: scoring_api.load_carioca_configuration(VERSIONED_CONFIG),
            'current_carioca_run': lambda: scoring_api.current_carioca_run(session),
            'carioca_scores': lambda: list(scoring_api.carioca_scores(
                session, scoring_api.current_carioca_run(session).id)),
            'exclusions': lambda: scoring_api.exclusions(session, scoring_api.current_carioca_run(session).id),
            'explain': lambda: scoring_api.explain(session, scoring_api.current_carioca_run(session).id,
                                                   observation.ioc_id),
        },
    }


@pytest.fixture
def populated(engine):
    from misp_ioc_scoring.collection.domain.observations import Observation
    from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry
    from misp_ioc_scoring.collection.infrastructure.persistence.repositories.observations import ObservationsRepository
    from misp_ioc_scoring.entrypoints.scoring_sharing import run_simple_blocking
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    observations = [Observation(
        source_instance_id='test', event_uuid=uuid4(), attribute_uuid=uuid4(), raw_value=value,
        misp_type='domain', category='Network activity', to_ids=True, orgc_uuid=uuid4(),
        source_created_at=now, source_modified_at=now, collected_at=now, event_threat_level='2',
        event_analysis='2', distribution='1', event_distribution='1', published=True, tags=('t',))
        for value in ('api.example', 'bad value')]
    ObservationsRepository(engine, 'test').apply(
        observations, {o.attribute_uuid for o in observations},
        [WarninglistEntry('test', 'l', 'regex', '.*')], now)
    run_simple_blocking(engine, 48)
    from misp_ioc_scoring.entrypoints.scoring_sharing import run_carioca_scoring
    from tests.support.carioca import configuration
    run_carioca_scoring(engine, configuration())
    yield engine
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE scoring.execucao_bloqueio CASCADE'))
        connection.execute(text('TRUNCATE scoring.execucao_scoring, scoring.configuracao_carioca CASCADE'))


def test_public_functions_return_domain_types(populated):
    with transaction(populated) as session:
        recipes = calls(session, populated)
        for module, recipe in recipes.items():
            names = public_functions(module) | {name for name, item in vars(module).items()
                                                 if inspect.isclass(item) and item.__module__ == module.__name__
                                                 and name.endswith('Reader')}
            assert names <= set(recipe), f'add a call for {sorted(names - set(recipe))} in {module.__name__}'
            for name, call in recipe.items():
                walk(call(), f'{module.__name__}.{name}')
