"""Daily CARIOCA recalculation of the whole valid population at one `as_of` (FR-010)."""
import logging
from dataclasses import asdict
from typing import Protocol
from uuid import uuid4

from misp_ioc_scoring.collection.api import CATEGORIES

from ..domain.aggregation import ObservationEvaluation, winners
from ..domain.cade import cade, counts_by_event, estimate_sigma, event_key
from ..domain.carioca_components import age_days, attribute_score, event_score
from ..domain.carioca_inputs import analysis, threat_level
from ..domain.carioca_results import RunSummary, ScoreResult
from ..domain.feed_rank import feed_rank
from ..domain.population import ioc_exclusion, observation_exclusion
from ..domain.priority import minmax, spotis
from ..domain.selection import ranked

log = logging.getLogger(__name__)
EMPTY_POPULATION = 'empty_population'


class CariocaStore(Protocol):
    """Port: persists one CARIOCA run; nothing is visible before `finish`."""
    def start(self, run_id, as_of, configuration): ...
    def statistics(self, run_id, statistics): ...
    def evaluations(self, run_id, evaluations): ...
    def results(self, run_id, results): ...
    def exclusions(self, run_id, exclusions): ...
    def finish(self, run_id, summary): ...


def _batched(store_call, run_id, items, size):
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            store_call(run_id, batch)
            batch = []
    if batch:
        store_call(run_id, batch)


def calculate(as_of, snapshot, configuration, categories=CATEGORIES):
    """Pure calculation; returns (statistics, evaluations, results, exclusions, warnings)."""
    active = [o for o in snapshot.observations if o.removed_at is None]
    events = counts_by_event(active, categories)
    sigmas, sigma_inputs = estimate_sigma(events, categories, configuration.sigma)
    cade_raw = {key: cade(counts, sigmas, configuration.beta, configuration.sigma)
                for key, counts in events.items()}
    cade_norm, cade_degenerate, cade_min, cade_max = minmax(cade_raw)
    organizations = feed_rank(active, configuration.feed_rank)

    by_ioc_reasons = {}
    valid = []
    for observation in active:
        reason = observation_exclusion(observation, configuration, as_of)
        by_ioc_reasons.setdefault(observation.ioc_id, []).append(reason)
        if reason is None:
            valid.append(observation)

    def identity(observation):
        return (observation.source_instance_id, observation.attribute_uuid)

    attribute_raw = {identity(o): attribute_score(configuration.decay_group(o.misp_type),
                                                  o.source_modified_at, as_of) for o in valid}
    event_raw = {}
    for o in valid:
        event_raw.setdefault(event_key(o), event_score(
            threat_level(o.event_threat_level), analysis(o.event_analysis),
            cade_norm[event_key(o)], configuration.alpha))
    source_raw = {identity(o): organizations[o.orgc_uuid].value for o in valid}
    attribute_norm, attribute_degenerate, attribute_min, attribute_max = minmax(attribute_raw)
    event_norm, event_degenerate, event_min, event_max = minmax(event_raw)
    source_norm, source_degenerate, source_min, source_max = minmax(source_raw)
    degenerate = tuple(name for name, flag in (('cade', cade_degenerate), ('event', event_degenerate),
                                                ('attribute', attribute_degenerate),
                                                ('source', source_degenerate)) if flag and valid)

    evaluations = []
    for o in valid:
        key, event = identity(o), event_key(o)
        components = {'source': source_norm[key], 'event': event_norm[event], 'attribute': attribute_norm[key]}
        evaluations.append(ObservationEvaluation(
            ioc_id=o.ioc_id, source_instance_id=o.source_instance_id, attribute_uuid=o.attribute_uuid,
            event_uuid=o.event_uuid, orgc_uuid=o.orgc_uuid, source_created_at=o.source_created_at,
            decay_group=configuration.type_groups[o.misp_type],
            age_days=age_days(o.source_modified_at, as_of), attribute_raw=attribute_raw[key],
            attribute_norm=attribute_norm[key], threat_level=threat_level(o.event_threat_level),
            analysis=analysis(o.event_analysis), cade_raw=cade_raw[event], cade_norm=cade_norm[event],
            event_raw=event_raw[event], event_norm=event_norm[event], source_value=source_raw[key],
            source_norm=source_norm[key],
            priority=spotis(components, configuration.spotis_weights, configuration.spotis_ideal),
            minmax_degenerate=degenerate,
            event_categories=tuple(c for c, n in events[event].items() if n)))

    iocs = {o.ioc_id: o for o in active}
    results = [ScoreResult(ioc_id=e.ioc_id, type=iocs[e.ioc_id].misp_type,
                           normalized_value=iocs[e.ioc_id].normalized_value,
                           input_revision=iocs[e.ioc_id].input_revision, priority_score=e.priority,
                           rank=rank, in_top_n=in_top_n, observations_evaluated=count, winner=e)
               for e, count, rank, in_top_n in ranked(winners(evaluations), configuration.top_n)]
    exclusions = sorted(((ioc_id, reason) for ioc_id, reasons in by_ioc_reasons.items()
                         if (reason := ioc_exclusion(reasons)) is not None), key=lambda item: str(item[0]))

    warnings = []
    if not valid:
        warnings.append(EMPTY_POPULATION)
    warnings.extend('minmax_degenerate:' + name for name in degenerate)
    statistics = {
        'sigma_method': configuration.sigma.method, 'sigma_version': configuration.sigma.version,
        'sigma_zero_rule': configuration.sigma.zero_rule,
        'sigma_by_category': sigmas, 'n_by_category_stats': sigma_inputs,
        'bounds': {'cade': [cade_min, cade_max], 'event': [event_min, event_max],
                   'attribute': [attribute_min, attribute_max], 'source': [source_min, source_max]},
        'organizations': {str(org): asdict(rank) for org, rank in sorted(organizations.items(), key=lambda i: str(i[0]))},
        'minmax_degenerate': list(degenerate),
        'events_in_cade_scope': len(events), 'top_n_cutoff': next(
            (r.priority_score for r in reversed(results) if r.in_top_n), None),
    }
    return statistics, evaluations, results, exclusions, tuple(warnings)


def run_carioca(as_of, snapshot, configuration, store: CariocaStore, *, batch_size=1000,
                categories=CATEGORIES) -> RunSummary:
    """Recalculate everything from the snapshot, never reusing earlier runs."""
    configuration.require_approved()
    run_id = uuid4()
    store.start(run_id, as_of, configuration)
    statistics, evaluations, results, exclusions, warnings = calculate(as_of, snapshot, configuration, categories)
    store.statistics(run_id, statistics)
    _batched(store.evaluations, run_id, evaluations, batch_size)
    _batched(store.results, run_id, results, batch_size)
    _batched(store.exclusions, run_id, exclusions, batch_size)
    summary = RunSummary(run_id=run_id, as_of=as_of, observations_evaluated=len(evaluations),
                         valid_population=len(results), excluded=len(exclusions), warnings=warnings,
                         scored_revisions=tuple((r.ioc_id, r.input_revision) for r in results))
    if EMPTY_POPULATION in warnings:
        log.warning('carioca_empty_population', extra={'event': 'carioca_empty_population',
                                                        'run_id': str(run_id), 'code': EMPTY_POPULATION})
    store.finish(run_id, summary)
    return summary
