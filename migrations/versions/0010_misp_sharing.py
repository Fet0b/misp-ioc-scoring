"""MISP peers, effective sharing policy and one current sharing attempt per (peer, IOC)."""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = depends_on = None

STATES = ("eligible", "requested", "confirmed", "failed", "ambiguous", "ineligible", "suspended")


def upgrade():
    op.create_table(
        "peer_misp",
        sa.Column("peer_id", sa.String(100), primary_key=True),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("credential_secret_ref", sa.Text(), nullable=False, comment="secret"),
        sa.Column("minimum_priority_score", sa.Float(), nullable=False),
        sa.Column("distribution", sa.String(2), nullable=False),
        sa.Column("sharing_group_uuid", sa.String(100)),
        sa.Column("outbound_event_uuid", sa.Uuid(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("minimum_priority_score BETWEEN 0 AND 100", name="valid_minimum"),
        sa.CheckConstraint("distribution IN ('1', '2', '3', '4')", name="valid_distribution"),
        schema="sharing")
    op.create_table(
        "politica_compartilhamento",
        sa.Column("policy_hash", sa.String(64), primary_key=True),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("peers", sa.JSON(), nullable=False),
        sa.Column("suspended_at", sa.DateTime(timezone=True)),
        sa.Column("suspension_reason", sa.String(60)),
        schema="sharing")
    op.create_table(
        "tentativa_compartilhamento",
        sa.Column("peer_id", sa.String(100), sa.ForeignKey("sharing.peer_misp.peer_id"), primary_key=True),
        sa.Column("ioc_id", sa.Uuid(), primary_key=True),
        sa.Column("scoring_run_id", sa.Uuid()),
        sa.Column("policy_hash", sa.String(64), nullable=False),
        sa.Column("outbound_attribute_uuid", sa.Uuid(), nullable=False, unique=True),
        sa.Column("permitting_source_instance_id", sa.String(100)),
        sa.Column("permitting_attribute_uuid", sa.Uuid()),
        sa.Column("outbound_distribution", sa.String(2)),
        sa.Column("outbound_sharing_group_uuid", sa.String(100)),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(40)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("state IN (" + ", ".join(f"'{s}'" for s in STATES) + ")", name="valid_state"),
        sa.CheckConstraint("outbound_distribution IS NULL OR outbound_distribution IN ('0','1','2','3','4')",
                           name="valid_outbound_distribution"),
        schema="sharing")


def downgrade():
    for table in ("tentativa_compartilhamento", "politica_compartilhamento", "peer_misp"):
        op.drop_table(table, schema="sharing")
