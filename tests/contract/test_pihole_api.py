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
        "domain": "block.example", "comment": "misp-ioc-scoring:opaque"
    }
