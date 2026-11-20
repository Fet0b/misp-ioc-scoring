"""Collection tables with provenance, rejections and warninglists."""
import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ioc',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('normalized_value', sa.Text(), nullable=False),
        sa.Column('input_revision', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ioc')),
        sa.UniqueConstraint('type', 'normalized_value', name=op.f('uq_ioc_type')),
        schema='collection'
    )
    op.create_table('endpoint_coleta',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.Text(), nullable=False),
        sa.Column('credential_secret_ref', sa.Text(), nullable=False, comment='secret'),
        sa.Column('interval_seconds', sa.Float(), nullable=False),
        sa.Column('to_ids_only', sa.Boolean(), nullable=False),
        sa.Column('removal_ratio', sa.Float(), nullable=False),
        sa.Column('version', sa.String(length=100), nullable=True),
        sa.Column('last_successful_checkpoint', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('error', sa.String(length=100), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_endpoint_coleta')),
        schema='collection'
    )
    op.create_table('observacao_origem',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('ioc_id', sa.Uuid(), nullable=False),
        sa.Column('source_instance_id', sa.String(length=100), nullable=False),
        sa.Column('event_uuid', sa.Uuid(), nullable=False),
        sa.Column('attribute_uuid', sa.Uuid(), nullable=False),
        sa.Column('raw_value', sa.Text(), nullable=False),
        sa.Column('misp_type', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('to_ids', sa.Boolean(), nullable=False),
        sa.Column('orgc_uuid', sa.Uuid(), nullable=True),
        sa.Column('source_created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_modified_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_threat_level', sa.String(length=30), nullable=False),
        sa.Column('event_analysis', sa.String(length=30), nullable=False),
        sa.Column('distribution', sa.String(length=30), nullable=False),
        sa.Column('event_distribution', sa.String(length=30), nullable=False),
        sa.Column('sharing_group_id', sa.String(length=100), nullable=True),
        sa.Column('published', sa.Boolean(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['ioc_id'], ['collection.ioc.id'], name=op.f('fk_observacao_origem_ioc_id_ioc')),
        sa.ForeignKeyConstraint(['source_instance_id'], ['collection.endpoint_coleta.id'], name=op.f('fk_observacao_origem_source_instance_id_endpoint_coleta')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_observacao_origem')),
        sa.UniqueConstraint('source_instance_id', 'attribute_uuid', name=op.f('uq_observacao_origem_source_instance_id')),
        schema='collection'
    )
    op.create_index(op.f('ix_observacao_origem_ioc_id'), 'observacao_origem', ['ioc_id'], unique=False, schema='collection')
    op.create_table('rejeicao_indicador',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_instance_id', sa.String(length=100), nullable=False),
        sa.Column('event_uuid', sa.Uuid(), nullable=False),
        sa.Column('attribute_uuid', sa.Uuid(), nullable=False),
        sa.Column('misp_type', sa.String(length=100), nullable=False),
        sa.Column('raw_value', sa.Text(), nullable=False),
        sa.Column('reason', sa.String(length=30), nullable=False),
        sa.Column('detail', sa.String(length=100), nullable=False),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reason IN ('invalid', 'unsupported')", name=op.f('ck_rejeicao_indicador_valid_reason')),
        sa.ForeignKeyConstraint(['source_instance_id'], ['collection.endpoint_coleta.id'], name=op.f('fk_rejeicao_indicador_source_instance_id_endpoint_coleta')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rejeicao_indicador')),
        sa.UniqueConstraint('source_instance_id', 'attribute_uuid', 'reason', name=op.f('uq_rejeicao_indicador_source_instance_id')),
        schema='collection'
    )
    op.create_table('entrada_warninglist',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('source_instance_id', sa.String(length=100), nullable=False),
        sa.Column('list_name', sa.String(length=200), nullable=False),
        sa.Column('list_type', sa.String(length=50), nullable=False),
        sa.Column('normalized_value', sa.Text(), nullable=False),
        sa.Column('supported', sa.Boolean(), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['source_instance_id'], ['collection.endpoint_coleta.id'], name=op.f('fk_entrada_warninglist_source_instance_id_endpoint_coleta')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_entrada_warninglist')),
        sa.UniqueConstraint('source_instance_id', 'list_name', 'list_type', 'normalized_value', name=op.f('uq_entrada_warninglist_source_instance_id')),
        schema='collection'
    )


def downgrade():
    for table in ('entrada_warninglist', 'rejeicao_indicador', 'observacao_origem', 'ioc', 'endpoint_coleta'):
        op.drop_table(table, schema='collection')
