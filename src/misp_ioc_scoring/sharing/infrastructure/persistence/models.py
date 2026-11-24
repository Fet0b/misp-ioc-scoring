"""Persisted Pi-hole policy, ownership and synchronization attempts."""
from sqlalchemy import BigInteger, DateTime, Float, Integer, JSON, String, Uuid, func
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


class MispPeerModel(Base):
    __tablename__ = "peer_misp"
    __table_args__ = {"schema": "sharing"}

    peer_id = mapped_column(String(100), primary_key=True)
    base_url = mapped_column(String, nullable=False)
    credential_secret_ref = mapped_column(String, nullable=False, comment="secret")
    minimum_priority_score = mapped_column(Float, nullable=False)
    distribution = mapped_column(String(2), nullable=False)
    sharing_group_uuid = mapped_column(String(100))
    outbound_event_uuid = mapped_column(Uuid, nullable=False)
    loaded_at = mapped_column(DateTime(timezone=True), nullable=False)


class SharingPolicyModel(Base):
    __tablename__ = "politica_compartilhamento"
    __table_args__ = {"schema": "sharing"}

    policy_hash = mapped_column(String(64), primary_key=True)
    loaded_at = mapped_column(DateTime(timezone=True), nullable=False)
    peers = mapped_column(JSON, nullable=False)
    suspended_at = mapped_column(DateTime(timezone=True))
    suspension_reason = mapped_column(String(60))


class SharingAttemptModel(Base):
    __tablename__ = "tentativa_compartilhamento"
    __table_args__ = {"schema": "sharing"}

    peer_id = mapped_column(String(100), primary_key=True)
    ioc_id = mapped_column(Uuid, primary_key=True)
    scoring_run_id = mapped_column(Uuid)
    policy_hash = mapped_column(String(64), nullable=False)
    outbound_attribute_uuid = mapped_column(Uuid, nullable=False)
    permitting_source_instance_id = mapped_column(String(100))
    permitting_attribute_uuid = mapped_column(Uuid)
    outbound_distribution = mapped_column(String(2))
    outbound_sharing_group_uuid = mapped_column(String(100))
    state = mapped_column(String(20), nullable=False)
    reason = mapped_column(String(40))
    attempts = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at = mapped_column(DateTime(timezone=True))
    last_error = mapped_column(String(100))
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now())
