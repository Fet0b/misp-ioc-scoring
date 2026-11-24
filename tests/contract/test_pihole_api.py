import io
import json
from urllib.error import HTTPError

from misp_ioc_scoring.sharing.adapters.pihole import PiHole


def test_refresh_session_and_send_exact_domain_with_owner_comment():
    requests = []

    class Transport:
        def open(self, request, timeout):
            requests.append(request)
            if len(requests) == 2:
                raise HTTPError(request.full_url, 401, "expired", None, None)
            if request.full_url.endswith("/api/auth"):
                return io.BytesIO(json.dumps({"session": {"valid": True, "sid": str(len(requests))}}).encode())
            return io.BytesIO(b'{"domains":[]}')

    client = PiHole("https://pihole.example", "application-password")
    client.opener = Transport()
    client.add("block.example", "misp-ioc-scoring:opaque")
    assert [request.get_method() for request in requests] == ["POST"] * 4
    assert requests[-1].full_url == "https://pihole.example/api/domains/deny/exact"
    assert requests[-1].get_header("X-ftl-sid") == "3"
    assert json.loads(requests[-1].data) == {
        "domain": "block.example", "comment": "misp-ioc-scoring:opaque", "groups": [0], "enabled": True
    }


def test_validates_ftl_version_and_exact_deny_contract():
    from collections import deque

    responses = deque([
        {"session": {"valid": True, "sid": "test-sid"}},
        {"version": {"ftl": {"local": {"version": "v6.1"}}}},
        {"domains": []},
        {"domains": [{"domain": "block.example", "comment": "owner", "id": 42, "groups": [2]}]},
    ])

    class Transport:
        def open(self, request, timeout):
            return io.BytesIO(json.dumps(responses.popleft()).encode())

    client = PiHole("https://pihole.example", "application-password")
    client.opener = Transport()
    client.validate()
    assert client.lookup("block.example").groups == (2,)
    assert not responses


def test_http_requires_opt_in_and_rejects_incompatible_version():
    import pytest

    with pytest.raises(ValueError, match="pihole_invalid_transport"):
        PiHole("http://pihole.example", "application-password")
    client = PiHole("http://pihole.example", "application-password", allow_http=True)
    client.call = lambda *args: {"version": {"ftl": {"local": {"version": "v5.1"}}}}
    with pytest.raises(ValueError, match="pihole_incompatible_api"):
        client.validate()


def test_timeout_has_safe_error_and_is_not_retried_by_transport():
    import pytest
    from misp_ioc_scoring.sharing.adapters.pihole import PiHoleRequestError

    class Transport:
        calls = 0

        def open(self, request, timeout):
            self.calls += 1
            raise TimeoutError("private-host:private-session")

    client = PiHole("https://pihole.example", "application-password")
    client.sid = "private-session"
    client.opener = Transport()
    with pytest.raises(PiHoleRequestError, match="^pihole_request_failed$") as caught:
        client.add("private-host.example", "marker")
    assert caught.value.__suppress_context__
    assert client.opener.calls == 1
