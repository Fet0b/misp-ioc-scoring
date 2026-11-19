"""Pi-hole v6 client for exact deny entries on one configured endpoint."""
import json
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class PiHole:
    def __init__(self, endpoint, password, timeout=10):
        self.endpoint = endpoint.rstrip("/")
        self.password = password
        self.timeout = timeout
        self.sid = None
        self.opener = build_opener(NoRedirect)

    def _request(self, method, path, data=None):
        headers = {"Content-Type": "application/json"}
        if self.sid and path != "/auth":
            headers["X-FTL-SID"] = self.sid
        payload = json.dumps(data).encode() if data is not None else None
        request = Request(self.endpoint + "/api" + path, payload, headers, method=method)
        with self.opener.open(request, timeout=self.timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    def _login(self):
        session = self._request("POST", "/auth", {"password": self.password})["session"]
        if not session.get("valid") or not session.get("sid"):
            raise ValueError("pihole_auth_failed")
        self.sid = session["sid"]

    def call(self, method, path, data=None):
        if not self.sid:
            self._login()
        try:
            return self._request(method, path, data)
        except HTTPError as error:
            if error.code != 401:
                raise
        self._login()
        return self._request(method, path, data)

    def lookup(self, host):
        try:
            rows = self.call("GET", "/domains/deny/exact/" + quote(host, safe=""))["domains"]
        except HTTPError as error:
            if error.code == 404:
                return None
            raise
        return next((row for row in rows if row["domain"] == host), None)

    def add(self, host, marker):
        self.call("POST", "/domains/deny/exact", {"domain": host, "comment": marker})

    def remove(self, host):
        self.call("DELETE", "/domains/deny/exact/" + quote(host, safe=""))

    def close(self):
        if self.sid:
            try:
                self._request("DELETE", "/auth")
            finally:
                self.sid = None
