"""Preserve local attribute IDs and track collection generations."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = depends_on = None


def upgrade():
    for table in ("observacao_origem", "rejeicao_indicador"):
        op.add_column(table, sa.Column("attribute_id", sa.BigInteger()), schema="collection")
    op.add_column("endpoint_coleta", sa.Column("generation", sa.BigInteger(),
                  nullable=False, server_default="0"), schema="collection")


def downgrade():
    op.drop_column("endpoint_coleta", "generation", schema="collection")
    for table in ("observacao_origem", "rejeicao_indicador"):
        op.drop_column(table, "attribute_id", schema="collection")
