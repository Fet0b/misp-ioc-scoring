"""Collection-owned persistence; secret references are explicitly annotated."""
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from misp_ioc_scoring.shared.database import Base


class IOCModel(Base):
    __tablename__ = 'ioc'
    __table_args__ = (UniqueConstraint('type', 'normalized_value'), {'schema': 'collection'})
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(String(100))
    normalized_value: Mapped[str] = mapped_column(Text)
    input_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EndpointModel(Base):
    __tablename__ = 'endpoint_coleta'
    __table_args__ = {'schema': 'collection'}
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    base_url: Mapped[str] = mapped_column(Text)
    credential_secret_ref: Mapped[str] = mapped_column(Text, comment='secret')
    interval_seconds: Mapped[float] = mapped_column(Float)
    to_ids_only: Mapped[bool] = mapped_column(Boolean, default=True)
    removal_ratio: Mapped[float] = mapped_column(Float)
    version: Mapped[str | None] = mapped_column(String(100))
    last_successful_checkpoint: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default='scheduled')
    error: Mapped[str | None] = mapped_column(String(100))
    warnings: Mapped[list] = mapped_column(JSON, default=list)


class ObservationModel(Base):
    __tablename__ = 'observacao_origem'
    __table_args__ = (UniqueConstraint('source_instance_id', 'attribute_uuid'), {'schema': 'collection'})
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    ioc_id: Mapped[UUID] = mapped_column(ForeignKey('collection.ioc.id'), index=True)
    source_instance_id: Mapped[str] = mapped_column(ForeignKey('collection.endpoint_coleta.id'))
    event_uuid: Mapped[UUID] = mapped_column(Uuid)
    attribute_uuid: Mapped[UUID] = mapped_column(Uuid)
    raw_value: Mapped[str] = mapped_column(Text)
    misp_type: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(100))
    to_ids: Mapped[bool] = mapped_column(Boolean)
    orgc_uuid: Mapped[UUID | None] = mapped_column(Uuid)
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_threat_level: Mapped[str] = mapped_column(String(30))
    event_analysis: Mapped[str] = mapped_column(String(30))
    distribution: Mapped[str] = mapped_column(String(30))
    event_distribution: Mapped[str] = mapped_column(String(30))
    sharing_group_id: Mapped[str | None] = mapped_column(String(100))
    published: Mapped[bool] = mapped_column(Boolean)
    tags: Mapped[list] = mapped_column(JSON, default=list)


class RejectionModel(Base):
    __tablename__ = 'rejeicao_indicador'
    __table_args__ = (
        UniqueConstraint('source_instance_id', 'attribute_uuid', 'reason'),
        CheckConstraint("reason IN ('invalid', 'unsupported')", name='valid_reason'),
        {'schema': 'collection'},
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_instance_id: Mapped[str] = mapped_column(ForeignKey('collection.endpoint_coleta.id'))
    event_uuid: Mapped[UUID] = mapped_column(Uuid)
    attribute_uuid: Mapped[UUID] = mapped_column(Uuid)
    misp_type: Mapped[str] = mapped_column(String(100))
    raw_value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(String(100))
    rejected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WarninglistModel(Base):
    __tablename__ = 'entrada_warninglist'
    __table_args__ = (UniqueConstraint('source_instance_id', 'list_name', 'list_type', 'normalized_value'), {'schema': 'collection'})
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_instance_id: Mapped[str] = mapped_column(ForeignKey('collection.endpoint_coleta.id'))
    list_name: Mapped[str] = mapped_column(String(200))
    list_type: Mapped[str] = mapped_column(String(50))
    normalized_value: Mapped[str] = mapped_column(Text)
    supported: Mapped[bool] = mapped_column(Boolean)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
