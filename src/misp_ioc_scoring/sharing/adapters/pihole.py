"""Pi-hole v6 client for exact deny entries on one configured endpoint."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PiHoleRequestError(Exception):
    def __init__(self, status=None):
        super().__init__("pihole_request_failed")
        self.status = status


class PiHole:
    def __init__(self, endpoint, password, timeout=10, *, allow_http=False):
        if urlsplit(endpoint).scheme not in ({"https", "http"} if allow_http else {"https"}):
            raise ValueError("pihole_invalid_transport")
        self.endpoint = endpoint.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.sid = None
        self.opener = build_opener(NoRedirect)

    def _request(self, method, path, data=None):
        headers = {"Content-Type": "application/json"}
        if self.sid and (method, path) != ("POST", "/auth"):
            headers["X-FTL-SID"] = self.sid
        payload = json.dumps(data).encode() if data is not None else None
        request = Request(self.endpoint + "/api" + path, payload, headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            error.close()
            raise PiHoleRequestError(error.code) from None
        except (URLError, OSError, ValueError):
            raise PiHoleRequestError() from None

    def _login(self):
        response = self._request("POST", "/auth", {"password": self.password})
        session = response.get("session") if isinstance(response, dict) else None
        if not isinstance(session, dict) or session.get("valid") is not True or not isinstance(
            session.get("sid"), str
        ) or not session["sid"]:
            raise ValueError("pihole_auth_failed")
        self.sid = session["sid"]

    def call(self, method, path, data=None):
        if not self.sid:
            self._login()
        try:
            return self._request(method, path, data)
        except PiHoleRequestError as error:
            if error.status != 401:
                raise
        self._login()
        return self._request(method, path, data)

    def validate(self):
        payload = self.call("GET", "/info/version")
        try:
            version = payload["version"]["ftl"]["local"]["version"]
        except (KeyError, TypeError):
            raise ValueError("pihole_incompatible_api") from None
        if not isinstance(version, str) or not version.startswith("v6."):
            raise ValueError("pihole_incompatible_api")
        payload = self.call("GET", "/domains/deny/exact")
        if not isinstance(payload, dict) or not isinstance(payload.get("domains"), list):
            raise ValueError("pihole_incompatible_api")

    def lookup(self, host):
        try:
            rows = self.call("GET", "/domains/deny/exact/" + quote(host, safe=""))["domains"]
        except PiHoleRequestError as error:
            if error.status == 404:
                return None
            raise
        return next((row for row in rows if row["domain"] == host), None)

    def add(self, host, marker):
        self.call("POST", "/domains/deny/exact", {"domain": host, "comment": marker, "groups": [0], "enabled": True})

    def remove(self, host):
        self.call("DELETE", "/domains/deny/exact/" + quote(host, safe=""))

    def close(self):
        if self.sid:
            try:
                self._request("DELETE", "/auth")
            finally:
                self.sid = None
