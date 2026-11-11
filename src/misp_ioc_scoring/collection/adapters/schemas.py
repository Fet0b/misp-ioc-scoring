"""MISP payload validation; unknown enum values are preserved for explicit handling."""
from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from misp_ioc_scoring.collection.domain.observations import Observation


class Payload(BaseModel):
    model_config = ConfigDict(extra='ignore', hide_input_in_errors=True)


class AttributePayload(Payload):
    uuid: UUID
    type: str
    value: str = Field(repr=False)
    category: str
    to_ids: bool
    timestamp: datetime
    distribution: str = '5'
    sharing_group_id: str | None = None
    deleted: bool = False
    Tag: list[dict] = Field(default_factory=list)

    @field_validator('distribution', 'sharing_group_id', mode='before')
    @classmethod
    def string_enum(cls, value):
        return str(value) if value is not None else None

    @field_validator('timestamp', mode='before')
    @classmethod
    def timestamp_utc(cls, value):
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            return datetime.fromtimestamp(int(value), timezone.utc)
        return value


class EventPayload(Payload):
    uuid: UUID
    date: datetime
    timestamp: datetime
    threat_level_id: str
    analysis: str
    distribution: str
    published: bool
    Orgc: dict = Field(default_factory=dict)
    Attribute: list[AttributePayload] = Field(default_factory=list)
    Object: list[dict] = Field(default_factory=list)

    @field_validator('threat_level_id', 'analysis', 'distribution', mode='before')
    @classmethod
    def string_enum(cls, value):
        return str(value)

    @field_validator('date', 'timestamp', mode='before')
    @classmethod
    def timestamp_utc(cls, value):
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
            return datetime.fromtimestamp(int(value), timezone.utc)
        if isinstance(value, str) and len(value) == 10:
            return value + 'T00:00:00+00:00'
        return value

    def observations(self, source: str, collected_at: datetime):
        attributes = list(self.Attribute)
        for obj in self.Object:
            attributes.extend(AttributePayload.model_validate(a) for a in obj.get('Attribute', []))
        orgc = UUID(self.Orgc['uuid']) if self.Orgc.get('uuid') else None
        for attribute in attributes:
            yield Observation(
                source_instance_id=source, event_uuid=self.uuid, attribute_uuid=attribute.uuid,
                raw_value=attribute.value, misp_type=attribute.type, category=attribute.category,
                to_ids=attribute.to_ids, orgc_uuid=orgc, source_created_at=self.date,
                source_modified_at=attribute.timestamp, collected_at=collected_at,
                event_threat_level=self.threat_level_id, event_analysis=self.analysis,
                distribution=attribute.distribution, event_distribution=self.distribution,
                published=self.published, sharing_group_id=attribute.sharing_group_id,
                tags=tuple(tag['name'] for tag in attribute.Tag if 'name' in tag),
                removed_at=collected_at if attribute.deleted else None,
            )
