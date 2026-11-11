import pytest
from misp_ioc_scoring.collection.domain.normalization import normalize, IndicatorRejected


@pytest.mark.parametrize('kind,raw,expected', [
    ('domain', 'EXAMPLE.COM', 'example.com'),
    ('hostname', 'a.Example.com', 'a.example.com'),
    ('ip-src', '2001:0db8::1', '2001:db8::1'),
    ('md5', 'A' * 32, 'a' * 32),
    ('filename|sha256', 'Example.EXE|' + 'A' * 64, 'Example.EXE|' + 'a' * 64),
    ('url', 'https://Example.COM/path?A=B', 'https://example.com/path?A=B'),
])
def test_normalization(kind, raw, expected):
    assert normalize(kind, raw) == expected


@pytest.mark.parametrize('kind,raw,reason', [
    ('domain', 'bad domain', 'invalid'), ('domain', ' example.com', 'invalid'),
    ('ip-dst', '999.1.1.1', 'invalid'), ('md5', 'not-a-valid-hash', 'invalid'),
    ('filename|md5', 'file|' + 'x' * 32, 'invalid'),
    ('url', 'javascript:alert(1)', 'invalid'), ('comment', '=secret', 'unsupported'),
])
def test_rejections_do_not_echo_raw_values(kind, raw, reason):
    with pytest.raises(IndicatorRejected) as error:
        normalize(kind, raw)
    assert error.value.reason == reason
    assert raw not in str(error.value)
