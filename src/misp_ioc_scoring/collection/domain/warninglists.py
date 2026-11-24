from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from urllib.parse import urlsplit

SUPPORTED_LIST_TYPES = frozenset({'string', 'cidr', 'hostname'})
_DOMAIN_KINDS = frozenset({'domain', 'hostname'})
_IP_KINDS = frozenset({'ip-src', 'ip-dst'})
MODES = ('strict', 'fr027')


@dataclass(frozen=True)
class WarninglistEntry:
    source_instance_id: str
    list_name: str
    list_type: str
    normalized_value: str

    @property
    def supported(self) -> bool:
        return self.list_type in SUPPORTED_LIST_TYPES

    def matches(self, kind: str, value: str) -> bool:
        if not self.supported:
            return False
        if self.list_type == 'string':
            return value == self.normalized_value
        if self.list_type == 'hostname':
            return kind in _DOMAIN_KINDS and (
                value == self.normalized_value or value.endswith('.' + self.normalized_value))
        if kind not in _IP_KINDS:
            return False
        try:
            return ip_address(value) in ip_network(self.normalized_value)
        except ValueError:
            return False


class WarninglistIndex:
    """Warninglist membership for the entries of one source, built once per snapshot.

    Supported list types: exact string, hostname (the host itself or any subdomain) and
    CIDR for IP values. A URL also matches through its host. Regex and substring lists
    are never evaluated:
    - mode ``strict`` (simple blocking, 002): an unsupported entry makes a non-match
      undetermined (``None``);
    - mode ``fr027`` (MISP peers, FR-027): unsupported entries are ignored.
    """

    def __init__(self, entries):
        self._exact = set()
        self._hostnames = set()
        self._networks = []
        self.unsupported = 0
        for entry in entries:
            if not entry.supported:
                self.unsupported += 1
            elif entry.list_type == 'string':
                self._exact.add(entry.normalized_value)
            elif entry.list_type == 'hostname':
                self._hostnames.add(entry.normalized_value)
            else:
                try:
                    self._networks.append(ip_network(entry.normalized_value))
                except ValueError:
                    pass

    def _matches(self, kind, value) -> bool:
        if value in self._exact:
            return True
        if kind in _DOMAIN_KINDS:
            labels = value.split('.')
            return any('.'.join(labels[i:]) in self._hostnames for i in range(len(labels)))
        if kind in _IP_KINDS and self._networks:
            try:
                address = ip_address(value)
            except ValueError:
                return False
            return any(address in network for network in self._networks)
        return False

    def match(self, kind: str, value: str, mode: str = 'strict') -> bool | None:
        if mode not in MODES:
            raise ValueError('Unknown warninglist mode')
        if self._matches(kind, value):
            return True
        if kind == 'url':
            host = urlsplit(value).hostname
            try:
                ip_address(host)
                host_kind = 'ip-dst'
            except ValueError:
                host_kind = 'domain'
            if self._matches(host_kind, host):
                return True
        if mode == 'strict' and self.unsupported:
            return None
        return False
