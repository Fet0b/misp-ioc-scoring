from dataclasses import dataclass
from .normalization import normalize


@dataclass(frozen=True)
class IOC:
    type: str
    normalized_value: str

    def __post_init__(self):
        if normalize(self.type, self.normalized_value) != self.normalized_value:
            raise ValueError('IOC requires a normalized value')
