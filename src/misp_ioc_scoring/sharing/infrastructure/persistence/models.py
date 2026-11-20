"""Persisted Pi-hole policy, ownership and synchronization attempts."""
from sqlalchemy import BigInteger, DateTime, Float, JSON, String, Uuid, func
from sqlalchemy.orm import mapped_column

from misp_ioc_scoring.shared.database import Base


class PiHolePolicyModel(Base):
    __tablename__ = "pihole_policy"
    __table_args__ = {"schema": "sharing"}

    destination = mapped_column(String, primary_key=True)
    model = mapped_column(String, nullable=False)
    min_score = mapped_column(Float)
    interval_seconds = mapped_column(Float, nullable=False)
    password_secret_ref = mapped_column(String, nullable=False, comment="secret")


class PiHoleEntryModel(Base):
    __tablename__ = "pihole_entry"
    __table_args__ = {"schema": "sharing"}

    destination = mapped_column(String, primary_key=True)
    hostname = mapped_column(String(253), primary_key=True)
    marker = mapped_column(String, nullable=False)
    remote_id = mapped_column(BigInteger)
    status = mapped_column(String, nullable=False)
    evidence = mapped_column(JSON, nullable=False)


class PiHoleAttemptModel(Base):
    __tablename__ = "pihole_attempt"
    __table_args__ = {"schema": "sharing"}

    id = mapped_column(Uuid, primary_key=True)
    destination = mapped_column(String, nullable=False)
    hostname = mapped_column(String(253), nullable=False)
    operation = mapped_column(String, nullable=False)
    status = mapped_column(String, nullable=False)
    attempted_at = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
