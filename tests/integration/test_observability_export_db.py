from openpyxl import load_workbook
from misp_ioc_scoring.shared.configuration import load_configuration
from tools.export_observability import export


def test_export_uses_observer_and_excludes_secret_columns(engine, tmp_path):
    url = engine.url.set(username='observer', password='test-only-password').render_as_string(hide_password=False)
    configuration = load_configuration('tools', {'DATABASE_URL': url, 'EXPORT_OUTPUT_DIR': str(tmp_path)})
    workbook = load_workbook(export(configuration))
    assert len(workbook.sheetnames) == 6
    endpoints = workbook['collection.endpoint_coleta']
    assert 'credential_secret_ref' not in [c.value for c in endpoints[1]]
    assert workbook['Métricas'].max_row > 5
