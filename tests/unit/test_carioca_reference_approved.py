"""Level 2 of SC-015: reference cases recalculated with the approved σ estimator.

Values come from `docs/sigma-estimator-evaluation.md` (T033), in
`tests/unit/fixtures/carioca_reference_approved.json`:
{"cases": [{"name": ..., "n_by_category": {...}, "sigma_by_category": {...},
            "cade": ..., "cade_min": ..., "cade_max": ..., "cade_norm": ...,
            "threat_level": ..., "analysis": ..., "event": ...,
            "source_norm": ..., "event_norm": ..., "attribute_norm": ..., "priority": ...}]}
"""
import json
from pathlib import Path

import pytest

from misp_ioc_scoring.scoring.api import load_carioca_configuration
from misp_ioc_scoring.scoring.domain.cade import cade
from misp_ioc_scoring.scoring.domain.carioca_components import event_score
from misp_ioc_scoring.scoring.domain.priority import spotis

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'config' / 'carioca-orgc-proxy-v3.yaml'
VALUES = Path(__file__).parent / 'fixtures' / 'carioca_reference_approved.json'


def test_reference_cases_with_approved_estimator():
    configuration = load_carioca_configuration(CONFIG)
    if not configuration.approved:
        pytest.skip('Configuração CARIOCA ainda não aprovada (docs/sigma-estimator-evaluation.md)')
    assert VALUES.exists(), 'Configuração aprovada exige os valores de referência recalculados (T033)'
    for case in json.loads(VALUES.read_text())['cases']:
        counts = dict.fromkeys(configuration.categories, 0) | case['n_by_category']
        sigmas = dict.fromkeys(configuration.categories, 1.0) | case['sigma_by_category']
        raw = cade(counts, sigmas, configuration.beta, configuration.sigma)
        assert raw == pytest.approx(case['cade'], abs=1e-4), case['name']
        norm = (raw - case['cade_min']) / (case['cade_max'] - case['cade_min']) * 100
        assert norm == pytest.approx(case['cade_norm'], abs=1e-3), case['name']
        event = event_score(case['threat_level'], case['analysis'], norm, configuration.alpha)
        assert event == pytest.approx(case['event'], abs=1e-3), case['name']
        priority = spotis({'source': case['source_norm'], 'event': case['event_norm'],
                           'attribute': case['attribute_norm']}, configuration.spotis_weights)
        assert priority == pytest.approx(case['priority'], abs=1e-3), case['name']
