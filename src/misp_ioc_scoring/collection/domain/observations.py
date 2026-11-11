from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Observation:
    source_instance_id: str
    event_uuid: UUID
    attribute_uuid: UUID
    raw_value: str = field(repr=False)
    misp_type: str
    category: str
    to_ids: bool
    orgc_uuid: UUID | None
    source_created_at: datetime
    source_modified_at: datetime
    collected_at: datetime
    event_threat_level: str
    event_analysis: str
    distribution: str
    event_distribution: str
    published: bool
    sharing_group_id: str | None = None
    tags: tuple[str, ...] = ()
    removed_at: datetime | None = None
