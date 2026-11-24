"""Re-scoring candidates: one row per logical IOC (traceability only)."""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "candidato_rescoring",
        sa.Column("ioc_id", sa.Uuid(), primary_key=True),
        sa.Column("pending", sa.Boolean(), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False),
        sa.Column("scored_revision", sa.Integer()),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(100)),
        schema="scoring")
    op.create_index("ix_candidato_rescoring_pending", "candidato_rescoring", ["pending", "marked_at"], schema="scoring")


def downgrade():
    op.drop_table("candidato_rescoring", schema="scoring")
