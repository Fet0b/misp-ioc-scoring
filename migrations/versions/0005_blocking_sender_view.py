"""Expose effective decisions rather than a possibly stale persisted boolean."""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = depends_on = None


def upgrade():
    op.execute("""
    CREATE VIEW scoring.decisao_bloqueio_efetiva AS
    SELECT d.source_instance_id, d.attribute_uuid, d.attribute_id,
           d.block AND validity.current AND statement_timestamp() < d.expires_at AS block,
           CASE WHEN NOT validity.current THEN 'stale'
                WHEN d.block AND statement_timestamp() >= d.expires_at THEN 'expired' ELSE d.reason END AS reason,
           d.as_of, d.expires_at, r.rule_version
    FROM scoring.decisao_bloqueio d
    JOIN scoring.execucao_bloqueio r ON r.id=d.run_id
    JOIN collection.endpoint_coleta e ON e.id=d.source_instance_id
    CROSS JOIN LATERAL (SELECT e.status='completed' AND e.generation=d.generation
        AND statement_timestamp() < d.as_of + (d.evidence->>'max_age_hours')::double precision * interval '1 hour'
        AND r.status='completed' AS current) validity
    """)
    op.execute("GRANT SELECT ON scoring.decisao_bloqueio_efetiva TO scoring_sharing, observer")


def downgrade():
    op.execute("DROP VIEW scoring.decisao_bloqueio_efetiva")
