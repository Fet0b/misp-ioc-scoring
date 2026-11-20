"""Record effective Pi-hole policy without persisting credentials."""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "pihole_policy",
        sa.Column("destination", sa.String(), primary_key=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("min_score", sa.Float()),
        sa.Column("interval_seconds", sa.Float(), nullable=False),
        sa.Column("password_secret_ref", sa.String(), nullable=False, comment="secret"),
        sa.CheckConstraint(
            "(model = 'default' AND min_score IS NULL) OR "
            "(model = 'carioca' AND min_score IS NOT NULL AND min_score BETWEEN 0 AND 100)",
            name="valid_model_cutoff",
        ),
        schema="sharing",
    )


def downgrade():
    op.drop_table("pihole_policy", schema="sharing")
