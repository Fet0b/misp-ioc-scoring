"""Persistent ownership, source evidence and synchronization attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = depends_on = None


def upgrade():
    op.create_table("pihole_entry",
        sa.Column("destination", sa.String(), primary_key=True),
        sa.Column("hostname", sa.String(253), primary_key=True),
        sa.Column("marker", sa.String(), nullable=False),
        sa.Column("remote_id", sa.BigInteger()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        schema="sharing")
    op.create_table("pihole_attempt",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("destination", sa.String(), nullable=False),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        schema="sharing")


def downgrade():
    op.drop_table("pihole_attempt", schema="sharing")
    op.drop_table("pihole_entry", schema="sharing")
