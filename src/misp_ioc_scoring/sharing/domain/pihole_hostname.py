import ipaddress
import re
from urllib.parse import urlsplit


def hostname(kind, value):
    if kind not in {"domain", "url"}:
        return None
    try:
        parsed = urlsplit(value) if kind == "url" else None
        if parsed and (parsed.scheme not in {"http", "https", "ftp"} or parsed.username is not None):
            return None
        host = parsed.hostname if parsed else value
        host = host.rstrip(".").encode("idna").decode("ascii").lower()
    except (AttributeError, ValueError, TypeError):
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        labels = host.split(".")
        if len(host) <= 253 and len(labels) > 1 and not labels[-1].isdigit():
            if all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
                return host
    return None
