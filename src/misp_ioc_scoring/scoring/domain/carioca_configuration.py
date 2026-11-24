"""Versioned CARIOCA configuration (glossary: Configuração CARIOCA).

The file is YAML written in its JSON subset (every JSON document is valid YAML 1.2).
That keeps the project free of a YAML dependency (Constitution V) while staying
readable; anything outside that subset is rejected with an explicit error. Nothing has
an implicit default: a missing parameter stops the calculation (FR-012).
"""
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from .decay import DecayGroup

SIGMA_METHODS = frozenset({'population_std', 'p95_winsorized', 'log_std'})
# σ = 0: `indicator` gives 0/100, `half` gives 0/50 (previous prototype), `zero` always 0.
ZERO_RULES = frozenset({'indicator', 'half', 'zero'})
DECAY_GROUP_NAMES = ('hash', 'ip', 'domain')
NORMALIZATION_SCOPES = MappingProxyType({
    'cade': 'events_with_to_ids_observation',
    'event': 'events_with_valid_observation',
    'attribute': 'valid_observations',
    'source': 'valid_observations',
})
COMPONENTS = ('source', 'event', 'attribute')
# A MinMax whose maximum equals its minimum is always 50 (FR-024); not configurable.
DEGENERATE_MINMAX_VALUE = 50.0
_TOLERANCE = 1e-9


class CariocaConfigurationError(ValueError):
    """Invalid or incomplete configuration; `code` is safe to log."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SigmaEstimator:
    method: str
    version: str
    zero_rule: str


@dataclass(frozen=True)
class FeedRankParameters:
    method: str
    damping: float
    iterations: int
    dangling: str
    contribution_weight: float
    pagerank_weight: float


@dataclass(frozen=True)
class CariocaConfiguration:
    model_id: str
    cade_id: str
    version: str
    categories: tuple[str, ...]  # the 16 MISP event categories, from collection.api
    alpha: MappingProxyType  # threat_level, analysis, cade
    beta: MappingProxyType  # category -> weight
    sigma: SigmaEstimator
    decay_groups: MappingProxyType  # name -> DecayGroup
    type_groups: MappingProxyType  # MISP type -> group name
    scoring_to_ids_only: bool
    aggregation: str
    normalization_scopes: MappingProxyType
    feed_rank: FeedRankParameters
    spotis_weights: MappingProxyType  # component -> weight
    spotis_ideal: float
    top_n: int
    approved: bool
    approved_by: str | None
    approved_at: datetime | None
    evidence_ref: str | None
    content: str
    content_hash: str

    def decay_group(self, misp_type) -> DecayGroup | None:
        name = self.type_groups.get(misp_type)
        return self.decay_groups.get(name) if name else None

    def require_approved(self):
        if not self.approved:
            raise CariocaConfigurationError('CARIOCA_CONFIGURATION_NOT_APPROVED')
        return self


def _number(value, code, *, minimum=None, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CariocaConfigurationError(code)
    if integer and not isinstance(value, int):
        raise CariocaConfigurationError(code)
    if minimum is not None and value < minimum:
        raise CariocaConfigurationError(code)
    return value


def _weights(raw, keys, code):
    if not isinstance(raw, dict) or set(raw) != set(keys):
        raise CariocaConfigurationError(code)
    weights = {key: _number(raw[key], code, minimum=0) for key in keys}
    if abs(sum(weights.values()) - 1) > _TOLERANCE:
        raise CariocaConfigurationError(code)
    return MappingProxyType(weights)


def _text(raw, key, code):
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CariocaConfigurationError(code)
    return value


def parse_configuration(text: str, categories) -> CariocaConfiguration:
    """Parse and validate; `categories` are the MISP event categories (`collection.api.CATEGORIES`)."""
    categories = tuple(categories)
    lines = text.splitlines() if isinstance(text, str) else []
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith('#')):
        lines.pop(0)  # YAML comments are accepted only in the header
    try:
        raw = json.loads('\n'.join(lines))
    except (TypeError, ValueError):
        raise CariocaConfigurationError('CARIOCA_CONFIGURATION_FORMAT') from None
    if not isinstance(raw, dict):
        raise CariocaConfigurationError('CARIOCA_CONFIGURATION_FORMAT')
    model_id = _text(raw, 'model_id', 'CARIOCA_MODEL_ID')
    if model_id != 'carioca-orgc-proxy-v3':
        raise CariocaConfigurationError('CARIOCA_MODEL_ID')
    cade_id = _text(raw, 'cade_id', 'CARIOCA_CADE_ID')
    if cade_id != 'cade-seminormal-v2':
        raise CariocaConfigurationError('CARIOCA_CADE_ID')
    version = _text(raw, 'version', 'CARIOCA_VERSION')
    alpha = _weights(raw.get('alpha'), ('threat_level', 'analysis', 'cade'), 'CARIOCA_ALPHA')
    beta = _weights(raw.get('beta'), categories, 'CARIOCA_BETA')

    sigma_raw = raw.get('sigma')
    if not isinstance(sigma_raw, dict):
        raise CariocaConfigurationError('CARIOCA_SIGMA')
    sigma = SigmaEstimator(_text(sigma_raw, 'method', 'CARIOCA_SIGMA_METHOD'),
                           _text(sigma_raw, 'version', 'CARIOCA_SIGMA_VERSION'),
                           _text(sigma_raw, 'zero_rule', 'CARIOCA_SIGMA_ZERO_RULE'))
    if sigma.method not in SIGMA_METHODS:
        raise CariocaConfigurationError('CARIOCA_SIGMA_METHOD')
    if sigma.zero_rule not in ZERO_RULES:
        raise CariocaConfigurationError('CARIOCA_SIGMA_ZERO_RULE')

    decay_raw = raw.get('decay_groups')
    if not isinstance(decay_raw, dict) or set(decay_raw) != set(DECAY_GROUP_NAMES):
        raise CariocaConfigurationError('CARIOCA_DECAY_GROUPS')
    decay_groups = {}
    for name in DECAY_GROUP_NAMES:
        item = decay_raw[name]
        if not isinstance(item, dict) or set(item) != {'D', 'T'}:
            raise CariocaConfigurationError('CARIOCA_DECAY_GROUPS')
        D = _number(item['D'], 'CARIOCA_DECAY_GROUPS', minimum=0)
        T = _number(item['T'], 'CARIOCA_DECAY_GROUPS', minimum=0)
        if D == 0 or T == 0:
            raise CariocaConfigurationError('CARIOCA_DECAY_GROUPS')
        decay_groups[name] = DecayGroup(name, D, T)

    groups_raw = raw.get('type_groups')
    if not isinstance(groups_raw, dict) or set(groups_raw) != set(DECAY_GROUP_NAMES):
        raise CariocaConfigurationError('CARIOCA_TYPE_GROUPS')
    type_groups = {}
    for name in DECAY_GROUP_NAMES:
        types = groups_raw[name]
        if not isinstance(types, list) or not types:
            raise CariocaConfigurationError('CARIOCA_TYPE_GROUPS')
        for misp_type in types:
            # URL has no CARIOCA decay group (decision of 2026-11-24).
            if not isinstance(misp_type, str) or misp_type == 'url' or misp_type in type_groups:
                raise CariocaConfigurationError('CARIOCA_TYPE_GROUPS')
            type_groups[misp_type] = name

    if raw.get('scoring_to_ids_only') is not True:
        raise CariocaConfigurationError('CARIOCA_SCORING_TO_IDS_ONLY')
    if raw.get('aggregation') != 'max-observation':
        raise CariocaConfigurationError('CARIOCA_AGGREGATION')
    if raw.get('normalization_scopes') != dict(NORMALIZATION_SCOPES):
        raise CariocaConfigurationError('CARIOCA_NORMALIZATION_SCOPES')

    feed_raw = raw.get('feed_rank')
    if not isinstance(feed_raw, dict):
        raise CariocaConfigurationError('CARIOCA_FEED_RANK')
    feed_rank = FeedRankParameters(
        method=_text(feed_raw, 'method', 'CARIOCA_FEED_RANK'),
        damping=_number(feed_raw.get('damping'), 'CARIOCA_FEED_RANK', minimum=0),
        iterations=_number(feed_raw.get('iterations'), 'CARIOCA_FEED_RANK', minimum=1, integer=True),
        dangling=_text(feed_raw, 'dangling', 'CARIOCA_FEED_RANK'),
        contribution_weight=_number(feed_raw.get('contribution_weight'), 'CARIOCA_FEED_RANK', minimum=0),
        pagerank_weight=_number(feed_raw.get('pagerank_weight'), 'CARIOCA_FEED_RANK', minimum=0))
    if (feed_rank.method != 'orgc-proxy' or feed_rank.damping >= 1 or feed_rank.dangling != 'uniform'
            or feed_rank.contribution_weight + feed_rank.pagerank_weight == 0):
        raise CariocaConfigurationError('CARIOCA_FEED_RANK')

    spotis_raw = raw.get('spotis')
    if not isinstance(spotis_raw, dict):
        raise CariocaConfigurationError('CARIOCA_SPOTIS')
    spotis_weights = _weights(spotis_raw.get('weights'), COMPONENTS, 'CARIOCA_SPOTIS')
    if _number(spotis_raw.get('ideal'), 'CARIOCA_SPOTIS') != 100:
        raise CariocaConfigurationError('CARIOCA_SPOTIS')

    if 'top_n' not in raw:
        raise CariocaConfigurationError('CARIOCA_TOP_N')
    top_n = _number(raw['top_n'], 'CARIOCA_TOP_N', minimum=1, integer=True)

    approval = raw.get('approval')
    if not isinstance(approval, dict) or not isinstance(approval.get('approved'), bool):
        raise CariocaConfigurationError('CARIOCA_APPROVAL')
    approved = approval['approved']
    approved_at = approval.get('approved_at')
    try:
        approved_at = datetime.fromisoformat(approved_at) if approved_at else None
    except (TypeError, ValueError):
        raise CariocaConfigurationError('CARIOCA_APPROVAL') from None
    if approved and (not approval.get('approved_by') or approved_at is None or not approval.get('evidence_ref')):
        raise CariocaConfigurationError('CARIOCA_APPROVAL')

    content = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return CariocaConfiguration(
        model_id=model_id, cade_id=cade_id, version=version, categories=categories, alpha=alpha, beta=beta, sigma=sigma,
        decay_groups=MappingProxyType(decay_groups), type_groups=MappingProxyType(type_groups),
        scoring_to_ids_only=True, aggregation='max-observation',
        normalization_scopes=NORMALIZATION_SCOPES, feed_rank=feed_rank,
        spotis_weights=spotis_weights, spotis_ideal=100.0, top_n=top_n, approved=approved,
        approved_by=approval.get('approved_by'), approved_at=approved_at,
        evidence_ref=approval.get('evidence_ref'), content=content,
        content_hash=hashlib.sha256(content.encode()).hexdigest())
