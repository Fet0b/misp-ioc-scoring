from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class IndicatorRejection:
    source_instance_id: str
    event_uuid: UUID
    attribute_uuid: UUID
    misp_type: str
    raw_value: str = field(repr=False)
    reason: Literal['invalid', 'unsupported']
    rejected_at: datetime
    detail: str = 'indicator_rejected'
