from dataclasses import dataclass

DOMAIN_TYPES = frozenset({'domain', 'hostname'})
IP_TYPES = frozenset({'ip-src', 'ip-dst'})
HASH_TYPES = frozenset({'md5', 'sha1', 'sha256', 'sha512'})
URL_TYPES = frozenset({'url'})


@dataclass(frozen=True)
class IOC:
    type: str
    normalized_value: str

    def __post_init__(self):
        from .normalization import normalize  # normalization imports the type constants above
        if normalize(self.type, self.normalized_value) != self.normalized_value:
            raise ValueError('IOC requires a normalized value')
