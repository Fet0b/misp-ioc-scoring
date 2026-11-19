"""Store current decisions and their evaluation runs."""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = depends_on = None


def upgrade():
    op.create_table("execucao_bloqueio",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("rule_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        schema="scoring")
    op.create_table("decisao_bloqueio",
        sa.Column("source_instance_id", sa.String(), primary_key=True),
        sa.Column("attribute_uuid", sa.Uuid(), primary_key=True),
        sa.Column("attribute_id", sa.BigInteger()),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("scoring.execucao_bloqueio.id"), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("block", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        schema="scoring")
    op.create_index("ix_blocking_local_id", "decisao_bloqueio",
                    ["source_instance_id", "attribute_id"], schema="scoring")


def downgrade():
    op.drop_table("decisao_bloqueio", schema="scoring")
    op.drop_table("execucao_bloqueio", schema="scoring")
