"""Keep the event sharing group of each observation; legacy rows stay NULL until re-collected."""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = depends_on = None


def upgrade():
    op.add_column("observacao_origem", sa.Column("event_sharing_group_id", sa.String(100)), schema="collection")


def downgrade():
    op.drop_column("observacao_origem", "event_sharing_group_id", schema="collection")
