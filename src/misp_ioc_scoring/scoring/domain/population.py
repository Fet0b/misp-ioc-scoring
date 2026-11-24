"""Valid population (glossary: População válida) and exclusion reasons (FR-022)."""
from enum import StrEnum

from .carioca_components import attribute_score
from .carioca_inputs import missing_inputs


class ExclusionReason(StrEnum):
    INCOMPLETE_CONFIGURATION = 'incomplete_configuration'
    MISSING_DATA = 'missing_data'
    UNPUBLISHED = 'unpublished'
    NOT_TO_IDS = 'not_to_ids'
    TYPE_WITHOUT_DECAY_GROUP = 'type_without_decay_group'
    EXPIRED = 'expired'


# Highest precedence first: an IOC takes the reason of its most severe observation.
PRECEDENCE = tuple(ExclusionReason)


def observation_exclusion(observation, configuration, as_of) -> ExclusionReason | None:
    """None when the active observation is valid; otherwise its most severe reason."""
    reasons = set()
    group = None
    if observation.misp_type not in configuration.type_groups:
        reasons.add(ExclusionReason.TYPE_WITHOUT_DECAY_GROUP)
    else:
        group = configuration.decay_group(observation.misp_type)
        if group is None:
            reasons.add(ExclusionReason.INCOMPLETE_CONFIGURATION)
    if missing_inputs(observation, configuration.categories):
        reasons.add(ExclusionReason.MISSING_DATA)
    if observation.published is not True:
        reasons.add(ExclusionReason.UNPUBLISHED)
    if observation.to_ids is not True:
        reasons.add(ExclusionReason.NOT_TO_IDS)
    if group is not None and ExclusionReason.MISSING_DATA not in reasons:
        freshness = attribute_score(group, observation.source_modified_at, as_of)
        if freshness is None:
            reasons.add(ExclusionReason.MISSING_DATA)
        elif freshness <= 0:
            reasons.add(ExclusionReason.EXPIRED)
    return next((reason for reason in PRECEDENCE if reason in reasons), None)


def ioc_exclusion(observation_reasons) -> ExclusionReason | None:
    """An IOC with at least one valid observation is not excluded."""
    reasons = list(observation_reasons)
    if not reasons or any(reason is None for reason in reasons):
        return None
    return next(reason for reason in PRECEDENCE if reason in reasons)
