"""Explanation of an IOC score in the glossary terms (Constitution I)."""
from ..domain.carioca_results import ScoreExplanation
from ..domain.feed_rank import PROXY_LIMITATION

COMPONENT_NAMES = {
    'source_value': 'Source (valor da organização no FeedRank)', 'source_norm': "Source' (MinMax)",
    'threat_level': 'Threat level (TL)', 'analysis': 'Status de análise (SA)',
    'cade_raw': 'CADE bruto', 'cade_norm': "CADE' (MinMax entre eventos)",
    'event_raw': 'Event', 'event_norm': "Event' (MinMax)",
    'age_days': 'Idade t em dias contra o as_of', 'attribute_raw': 'Attribute (frescor)',
    'attribute_norm': "Attribute' (MinMax)",
}


def build_explanation(run, result, statistics, event_categories) -> ScoreExplanation:
    """`event_categories`: categories of the winning event, to show their σ."""
    sigma = statistics['sigma_by_category'] if statistics else {}
    return ScoreExplanation(
        ioc_id=result['ioc_id'], as_of=result['as_of'],
        configuration_version=run['configuration_version'], configuration_hash=run['configuration_hash'],
        priority_score=result['priority_score'], rank=result['rank'], in_top_n=result['in_top_n'],
        top_n=run['top_n'],
        winning_observation=(result['winning_source_instance_id'], result['winning_attribute_uuid']),
        observations_evaluated=result['observations_evaluated'],
        components={label: result[key] for key, label in COMPONENT_NAMES.items()} | {
            'Grupo de decaimento': result['decay_group']},
        sigma_by_category={category: sigma.get(category) for category in event_categories},
        minmax_degenerate=tuple(result['minmax_degenerate']),
        exclusion_reason=None, source_proxy_limitation=PROXY_LIMITATION)
