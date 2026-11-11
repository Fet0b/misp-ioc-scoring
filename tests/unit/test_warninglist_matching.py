from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry


def test_matching():
    entry = WarninglistEntry('source', 'list', 'cidr', '192.0.2.0/24')
    assert entry.matches('ip-src', '192.0.2.12')
    assert not entry.matches('domain', 'example.com')
    entry = WarninglistEntry('source', 'list', 'hostname', 'example.com')
    assert entry.matches('domain', 'a.example.com')
    assert not entry.matches('domain', 'notexample.com')
    assert WarninglistEntry('s', 'l', 'string', 'example.com').matches('domain', 'example.com')
    for kind in ('regex', 'substring'):
        entry = WarninglistEntry('s', 'l', kind, '.*')
        assert not entry.supported
        assert not entry.matches('domain', 'example.com')
