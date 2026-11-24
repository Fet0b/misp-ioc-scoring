from misp_ioc_scoring.collection.api import warninglist_index
from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry


def entry(kind, value):
    return WarninglistEntry("peer", "test", kind, value)


def membership(entries, kind, value):
    return warninglist_index(entries, "strict").match(kind, value, "strict")


def test_url_warninglist_matches_full_url_and_hostname():
    value = "https://sub.example.org/path"
    assert membership([entry("string", value)], "url", value)
    assert membership([entry("hostname", "example.org")], "url", value)
    assert membership([], "url", value) is False
    assert membership([entry("regex", ".*")], "url", value) is None
