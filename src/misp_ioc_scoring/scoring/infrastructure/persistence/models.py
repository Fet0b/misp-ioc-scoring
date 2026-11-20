"""Persisted blocking runs and current decisions."""
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import mapped_column

from misp_ioc_scoring.shared.database import Base


class BlockingRunModel(Base):
    __tablename__ = "execucao_bloqueio"
    __table_args__ = {"schema": "scoring"}

    id = mapped_column(Uuid, primary_key=True)
    as_of = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at = mapped_column(DateTime(timezone=True))
    rule_version = mapped_column(String, nullable=False)
    status = mapped_column(String, nullable=False)


class BlockingDecisionModel(Base):
    __tablename__ = "decisao_bloqueio"
    __table_args__ = {"schema": "scoring"}

    source_instance_id = mapped_column(String, primary_key=True)
    attribute_uuid = mapped_column(Uuid, primary_key=True)
    attribute_id = mapped_column(BigInteger)
    run_id = mapped_column(ForeignKey("scoring.execucao_bloqueio.id"), nullable=False)
    generation = mapped_column(BigInteger, nullable=False)
    block = mapped_column(Boolean, nullable=False)
    reason = mapped_column(String, nullable=False)
    as_of = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at = mapped_column(DateTime(timezone=True), nullable=False)
    evidence = mapped_column(JSON, nullable=False)
