"""Create module-owned schemas."""
from alembic import op
revision = '0000'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for schema in ('collection', 'scoring', 'sharing'):
        op.execute(f'CREATE SCHEMA {schema}')
    op.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')


def downgrade():
    for schema in ('sharing', 'scoring', 'collection'):
        op.execute(f'DROP SCHEMA {schema}')
