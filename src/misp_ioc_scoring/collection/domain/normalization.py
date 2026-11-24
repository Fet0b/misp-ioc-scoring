"""Explicit IOC normalization; malformed values are rejected without echoing content."""
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from .indicators import DOMAIN_TYPES, HASH_TYPES, IP_TYPES, URL_TYPES

_HASH_LENGTHS = {'md5': 32, 'sha1': 40, 'sha256': 64, 'sha512': 128}
assert set(_HASH_LENGTHS) == HASH_TYPES
_URL_SCHEMES = frozenset({'http', 'https', 'ftp'})


class IndicatorRejected(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__('indicator_' + reason)


def _domain(value: str) -> str:
    result = value.encode('idna').decode('ascii').lower()
    candidate = result[:-1] if result.endswith('.') else result
    if len(candidate) > 253 or not candidate:
        raise ValueError
    for label in candidate.split('.'):
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label):
            raise ValueError
    return candidate


def normalize(kind: str, value: str) -> str:
    supported = {*DOMAIN_TYPES, *IP_TYPES, *URL_TYPES, *HASH_TYPES,
                 *('filename|' + h for h in HASH_TYPES)}
    if kind not in supported:
        raise IndicatorRejected('unsupported')
    try:
        if not isinstance(value, str) or not value or value != value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError
        if kind in DOMAIN_TYPES:
            return _domain(value)
        if kind in IP_TYPES:
            if '%' in value:
                raise ValueError
            return str(ipaddress.ip_address(value))
        if kind in HASH_TYPES:
            if not re.fullmatch('[0-9a-fA-F]{' + str(_HASH_LENGTHS[kind]) + '}', value):
                raise ValueError
            return value.lower()
        if kind.startswith('filename|'):
            filename, hash_value = value.rsplit('|', 1)
            if not filename:
                raise ValueError
            return filename + '|' + normalize(kind.split('|')[1], hash_value)
        parsed = urlsplit(value)
        if parsed.scheme not in _URL_SCHEMES or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError
        host = parsed.hostname
        if ':' in host:
            host = '[' + str(ipaddress.IPv6Address(host)) + ']'
        else:
            host = _domain(host)
        if parsed.port is not None:
            host += ':' + str(parsed.port)
        return urlunsplit((parsed.scheme.lower(), host, parsed.path, parsed.query, parsed.fragment))
    except (ValueError, UnicodeError, TypeError):
        raise IndicatorRejected('invalid') from None


def dns_hostname(kind: str, value: str) -> str | None:
    """Exact DNS hostname of a domain or URL indicator, or None.

    `domain`/`hostname` validate the value itself; `url` takes the host of an http,
    https or ftp URL without userinfo. IP literals, numeric TLDs and single-label
    hosts give None. A URL host covers the whole host, not only the original path.
    """
    try:
        if kind in DOMAIN_TYPES:
            host = value
        elif kind in URL_TYPES:
            parsed = urlsplit(value)
            if (parsed.scheme not in _URL_SCHEMES or parsed.username is not None
                    or parsed.password is not None or not parsed.hostname):
                return None
            host = parsed.hostname
        else:
            return None
        host = _domain(host)
    except (ValueError, UnicodeError, TypeError, AttributeError):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    labels = host.split('.')
    if len(labels) < 2 or labels[-1].isdigit():
        return None
    return host
