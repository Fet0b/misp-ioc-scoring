"""Explicit IOC normalization; malformed values are rejected without echoing content."""
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

_HASH_LENGTHS = {'md5': 32, 'sha1': 40, 'sha256': 64, 'sha512': 128}


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
    supported = {'domain', 'hostname', 'ip-src', 'ip-dst', 'url', *_HASH_LENGTHS,
                 *('filename|' + h for h in _HASH_LENGTHS)}
    if kind not in supported:
        raise IndicatorRejected('unsupported')
    try:
        if not isinstance(value, str) or not value or value != value.strip() or any(ord(c) < 32 for c in value):
            raise ValueError
        if kind in {'domain', 'hostname'}:
            return _domain(value)
        if kind in {'ip-src', 'ip-dst'}:
            if '%' in value:
                raise ValueError
            return str(ipaddress.ip_address(value))
        if kind in _HASH_LENGTHS:
            if not re.fullmatch('[0-9a-fA-F]{' + str(_HASH_LENGTHS[kind]) + '}', value):
                raise ValueError
            return value.lower()
        if kind.startswith('filename|'):
            filename, hash_value = value.rsplit('|', 1)
            if not filename:
                raise ValueError
            return filename + '|' + normalize(kind.split('|')[1], hash_value)
        parsed = urlsplit(value)
        if parsed.scheme not in {'http', 'https', 'ftp'} or not parsed.hostname or parsed.username or parsed.password:
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
