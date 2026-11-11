from pathlib import Path
import os
import pytest
from openpyxl import load_workbook
from tools.export_observability import write_workbook


def test_text_secrets_truncation_and_permissions(tmp_path):
    output = tmp_path / 'private'
    rows = [{'raw_value': v, 'credential_secret_ref': 'private'} for v in ('=1+1', '+x', '-x', '@x')]
    tables = [('collection.example', ['raw_value'], iter(rows), 4)]
    path = write_workbook(output, tables, 3, [('collection.example', 4)])
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(output).st_mode & 0o777 == 0o700
    workbook = load_workbook(path)
    sheet = workbook['collection.example']
    assert sheet['A2'].value == '=1+1'
    assert sheet['A2'].data_type == 's'
    assert sheet['A3'].value == '+x'
    assert sheet['A4'].value == '-x'
    assert 'TRUNCATED' in sheet['A5'].value
    assert 'private' not in str(list(sheet.values))
    assert list(workbook['Métricas'].values)[1] == ('collection.example', '4')


def test_no_partial_file_on_read_error(tmp_path):
    def broken():
        yield {'value': 'one'}
        raise RuntimeError('untrusted payload')
    with pytest.raises(Exception) as error:
        write_workbook(tmp_path, [('collection.example', ['value'], broken(), 2)], 10, [])
    assert 'untrusted payload' not in str(error.value)
    assert not list(tmp_path.glob('*.xlsx'))
    assert not list(tmp_path.glob('*.tmp'))
