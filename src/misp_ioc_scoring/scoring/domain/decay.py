"""Decay groups of the Attribute component: `(1 - (t/T) ** (1/D)) * 100`."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DecayGroup:
    name: str
    D: float
    T: float

    def freshness(self, t_days: float) -> float | None:
        """Freshness 0–100 after `t_days`; negative time is undetermined (None)."""
        if t_days < 0:
            return None
        if t_days >= self.T:
            return 0
        return 100 * (1 - (t_days / self.T) ** (1 / self.D))


DOMAIN = DecayGroup('domain', 0.7, 365)
IP = DecayGroup('ip', 1.5, 7)
HASH = DecayGroup('hash', 2, 60)
GROUPS = {group.name: group for group in (DOMAIN, IP, HASH)}
