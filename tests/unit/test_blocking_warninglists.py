from types import SimpleNamespace

from misp_ioc_scoring.collection.api import blocking_warninglist_membership


def entry(kind, value, supported=True):
    return SimpleNamespace(source_instance_id="peer", list_name="test", list_type=kind,
                           normalized_value=value, supported=supported)


def test_url_warninglist_matches_full_url_and_hostname():
    value = "https://sub.example.org/path"
    assert blocking_warninglist_membership([entry("string", value)], "url", value)
    assert blocking_warninglist_membership([entry("hostname", "example.org")], "url", value)
    assert blocking_warninglist_membership([], "url", value) is False
    assert blocking_warninglist_membership([entry("regex", ".*", False)], "url", value) is None
