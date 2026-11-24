from ipaddress import ip_address
from itertools import product
from urllib.parse import urlsplit

import pytest

from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry, WarninglistIndex


def entry(kind, value):
    return WarninglistEntry('peer', 'test', kind, value)


def reference(entries, kind, value, mode):
    """Previous behaviour: `blocking_warninglist_membership` (strict) and `matches` (fr027)."""
    host = urlsplit(value).hostname if kind == 'url' else value
    host_kind = 'domain'
    try:
        ip_address(host)
        host_kind = 'ip-dst'
    except ValueError:
        pass
    uncertain = False
    for item in entries:
        if not item.supported:
            uncertain = True
        elif item.matches(kind, value) or (kind == 'url' and item.matches(host_kind, host)):
            return True
    return None if uncertain and mode == 'strict' else False


ENTRIES = [
    entry('string', 'https://listed.example/exact'), entry('string', 'exact.example'),
    entry('hostname', 'allowed.example'), entry('hostname', 'com'),
    entry('cidr', '192.0.2.0/24'), entry('cidr', '2001:db8::/32'), entry('cidr', '10.0.0.1/8'),
    entry('regex', '.*'), entry('substring', 'evil'),
]
VALUES = [
    ('domain', 'allowed.example'), ('domain', 'a.b.allowed.example'), ('domain', 'notallowed.example'),
    ('hostname', 'sub.allowed.example'), ('domain', 'exact.example'), ('domain', 'other.org'),
    ('domain', 'shop.com'), ('url', 'https://listed.example/exact'), ('url', 'https://listed.example/other'),
    ('url', 'https://x.allowed.example/p'), ('url', 'https://192.0.2.5/x'), ('url', 'https://[2001:db8::1]/'),
    ('url', 'https://198.51.100.1/'), ('ip-dst', '192.0.2.200'), ('ip-src', '2001:db8::5'),
    ('ip-dst', '10.1.1.1'), ('ip-dst', '203.0.113.1'), ('md5', 'a' * 32),
]


@pytest.mark.parametrize('mode', ['strict', 'fr027'])
def test_equivalent_to_previous_matching_for_every_subset(mode):
    for mask in product((False, True), repeat=len(ENTRIES)):
        chosen = [e for e, keep in zip(ENTRIES, mask) if keep]
        index = WarninglistIndex(chosen)
        for kind, value in VALUES:
            assert index.match(kind, value, mode) is reference(chosen, kind, value, mode), (chosen, kind, value)


def test_strict_mode():
    index = WarninglistIndex([entry('hostname', 'example.org'), entry('string', 'https://sub.example.org/path')])
    assert index.match('url', 'https://sub.example.org/path') is True
    assert index.match('url', 'https://other.example.org/') is True
    assert index.match('domain', 'example.org') is True
    assert index.match('domain', 'notexample.org') is False
    assert WarninglistIndex([entry('cidr', '192.0.2.0/24')]).match('url', 'https://192.0.2.9/') is True
    assert WarninglistIndex([]).match('url', 'https://sub.example.org/path') is False
    assert WarninglistIndex([entry('regex', '.*')]).match('domain', 'example.org') is None


def test_fr027_ignores_unsupported_entries():
    index = WarninglistIndex([entry('regex', '.*'), entry('hostname', 'example.org')])
    assert index.match('domain', 'a.example.org', 'fr027') is True
    assert index.match('domain', 'other.org', 'fr027') is False
    assert index.match('ip-dst', '192.0.2.1', 'fr027') is False


def test_unknown_mode():
    with pytest.raises(ValueError):
        WarninglistIndex([]).match('domain', 'example.org', 'loose')
