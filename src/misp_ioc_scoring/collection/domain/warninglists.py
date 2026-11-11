from dataclasses import dataclass
from ipaddress import ip_address, ip_network


@dataclass(frozen=True)
class WarninglistEntry:
    source_instance_id: str
    list_name: str
    list_type: str
    normalized_value: str

    @property
    def supported(self) -> bool:
        return self.list_type in {'string', 'cidr', 'hostname'}

    def matches(self, kind: str, value: str) -> bool:
        if not self.supported:
            return False
        if self.list_type == 'string':
            return value == self.normalized_value
        if self.list_type == 'hostname':
            return kind in {'domain', 'hostname'} and (
                value == self.normalized_value or value.endswith('.' + self.normalized_value))
        if kind not in {'ip-src', 'ip-dst'}:
            return False
        try:
            return ip_address(value) in ip_network(self.normalized_value)
        except ValueError:
            return False
