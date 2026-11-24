def test_services_start(e2e_environment):
    import subprocess
    from tests.e2e.conftest import FILES, ROOT
    result = subprocess.run(['docker', 'compose', *FILES, 'ps', '--services', '--status', 'running'],
                            cwd=ROOT, env=e2e_environment, capture_output=True, text=True, check=True)
    assert {'misp-local', 'misp-peer', 'pihole'} <= set(result.stdout.split())
