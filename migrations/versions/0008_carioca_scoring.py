"""CARIOCA configuration, runs, statistics, observation evaluations, results and exclusions."""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = depends_on = None

COMPONENTS = ("age_days", "attribute_raw", "attribute_norm", "threat_level", "analysis", "cade_raw",
              "cade_norm", "event_raw", "event_norm", "source_value", "source_norm")
EXCLUSIONS = ("incomplete_configuration", "missing_data", "unpublished", "not_to_ids",
              "type_without_decay_group", "expired")


def _components():
    return [sa.Column(name, sa.Float(), nullable=False) for name in COMPONENTS]


def upgrade():
    op.create_table(
        "configuracao_carioca",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("approved_by", sa.String(200)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_ref", sa.String(500)),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="scoring")
    op.create_table(
        "execucao_scoring",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("configuration_id", sa.Uuid(), sa.ForeignKey("scoring.configuracao_carioca.id")),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("observations_evaluated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_population", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("excluded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error", sa.String(100)),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="valid_status"),
        schema="scoring")
    op.create_index("ix_execucao_scoring_current", "execucao_scoring", ["status", "finished_at"], schema="scoring")
    op.create_table(
        "estatisticas_populacao",
        sa.Column("scoring_run_id", sa.Uuid(), sa.ForeignKey("scoring.execucao_scoring.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sigma_by_category", sa.JSON(), nullable=False),
        sa.Column("n_by_category_stats", sa.JSON(), nullable=False),
        sa.Column("bounds", sa.JSON(), nullable=False),
        sa.Column("organizations", sa.JSON(), nullable=False),
        sa.Column("minmax_degenerate", sa.JSON(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        schema="scoring")
    op.create_table(
        "avaliacao_observacao",
        sa.Column("scoring_run_id", sa.Uuid(), sa.ForeignKey("scoring.execucao_scoring.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("source_instance_id", sa.String(100), primary_key=True),
        sa.Column("attribute_uuid", sa.Uuid(), primary_key=True),
        sa.Column("ioc_id", sa.Uuid(), nullable=False),
        sa.Column("event_uuid", sa.Uuid(), nullable=False),
        sa.Column("orgc_uuid", sa.Uuid(), nullable=False),
        sa.Column("decay_group", sa.String(20), nullable=False),
        *_components(),
        sa.Column("priority", sa.Float(), nullable=False),
        sa.Column("minmax_degenerate", sa.JSON(), nullable=False),
        schema="scoring")
    op.create_table(
        "resultado_score",
        sa.Column("scoring_run_id", sa.Uuid(), sa.ForeignKey("scoring.execucao_scoring.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("ioc_id", sa.Uuid(), primary_key=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ioc_type", sa.String(100), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("input_revision", sa.Integer(), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("in_top_n", sa.Boolean(), nullable=False),
        sa.Column("winning_source_instance_id", sa.String(100), nullable=False),
        sa.Column("winning_attribute_uuid", sa.Uuid(), nullable=False),
        sa.Column("observations_evaluated", sa.Integer(), nullable=False),
        sa.Column("decay_group", sa.String(20), nullable=False),
        sa.Column("event_uuid", sa.Uuid(), nullable=False),
        sa.Column("orgc_uuid", sa.Uuid(), nullable=False),
        *_components(),
        sa.Column("minmax_degenerate", sa.JSON(), nullable=False),
        sa.Column("event_categories", sa.JSON(), nullable=False),
        sa.CheckConstraint("priority_score BETWEEN 0 AND 100", name="valid_priority"),
        sa.UniqueConstraint("scoring_run_id", "rank", name="uq_resultado_score_rank"),
        schema="scoring")
    op.create_table(
        "exclusao_score",
        sa.Column("scoring_run_id", sa.Uuid(), sa.ForeignKey("scoring.execucao_scoring.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("ioc_id", sa.Uuid(), primary_key=True),
        sa.Column("reason", sa.String(40), nullable=False),
        sa.CheckConstraint("reason IN (" + ", ".join(f"'{r}'" for r in EXCLUSIONS) + ")", name="valid_reason"),
        schema="scoring")


def downgrade():
    for table in ("exclusao_score", "resultado_score", "avaliacao_observacao", "estatisticas_populacao",
                  "execucao_scoring", "configuracao_carioca"):
        op.drop_table(table, schema="scoring")
