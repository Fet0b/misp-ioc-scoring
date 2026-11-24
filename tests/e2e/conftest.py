"""End-to-end fixtures: project Compose plus an isolated MISP, MISP peer and Pi-hole.

Opt-in with E2E_COMPOSE=true; requires Docker with the compose plugin. The MISP sync
server (local → peer) and its push rules are configured in MISP, not by this project.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).parent / 'config'
FILES = ['-f', str(ROOT / 'compose.yaml'), '-f', str(CONFIG / 'compose.e2e.yaml')]


def _compose(*args, env=None, check=True):
    return subprocess.run(['docker', 'compose', *FILES, *args], cwd=ROOT, env=env, check=check,
                          capture_output=True, text=True)


@pytest.fixture(scope='session')
def e2e_environment():
    if os.environ.get('E2E_COMPOSE') != 'true':
        pytest.skip('set E2E_COMPOSE=true to run the end-to-end environment')
    if shutil.which('docker') is None:
        pytest.skip('Docker is not available')
    env = os.environ | {
        'E2E_LOCAL_KEY': os.environ.get('E2E_LOCAL_KEY', 'e2elocal000000000000000000000000000000000'),
        'E2E_PEER_KEY': os.environ.get('E2E_PEER_KEY', 'e2epeer0000000000000000000000000000000000'),
        'COLLECTION_ENDPOINTS_FILE': str(CONFIG / 'endpoints.json'),
        'COLLECTION_CADENCE_FILE': str(CONFIG / 'cadence.json'),
        'MISP_PEERS_DIR': str(CONFIG),
        'MISP_PEERS_SECRET_REF': 'file:/run/misp-peers/peers.json',
    }
    _compose('up', '--build', '-d', env=env)
    try:
        yield env
    finally:
        _compose('down', '-v', env=env, check=False)
