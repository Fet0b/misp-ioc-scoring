"""Pi-hole entries (glossary: Entrada gerenciada) and the ownership rule."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RemoteEntry:
    """Exact deny entry as read from Pi-hole, translated by the adapter."""
    id: object
    comment: object
    groups: tuple | None
    enabled: object

    @classmethod
    def from_payload(cls, row):
        groups = row.get('groups')
        return cls(id=row.get('id'), comment=row.get('comment'),
                   groups=tuple(groups) if isinstance(groups, list) else None, enabled=row.get('enabled'))


@dataclass(frozen=True)
class ManagedEntry:
    hostname: str
    marker: str
    remote_id: int | None = None
    status: str | None = None
    evidence: list = field(default_factory=list)

    def is_owned_by(self, remote: RemoteEntry | None) -> bool:
        """The project owns the remote entry only if it carries our marker, our ID and default state."""
        return (remote is not None and remote.comment == self.marker
                and type(remote.id) is int
                and (self.remote_id is None or remote.id == self.remote_id)
                and remote.groups == (0,) and remote.enabled is True)
