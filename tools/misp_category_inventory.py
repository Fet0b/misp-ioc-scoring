"""Print aggregate URL and domain categories visible to the observer role."""
import json

from sqlalchemy import text

from misp_ioc_scoring.shared.configuration import load_configuration
from misp_ioc_scoring.shared.database import engine_from_configuration


def inventory(connection):
    connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
    sources = connection.execute(text("""
        SELECT id AS source_instance_id,
               CASE WHEN generation > 0 AND status = 'completed' AND last_success_at IS NOT NULL
                    THEN 'available' ELSE 'unavailable' END AS status
        FROM collection.endpoint_coleta
        ORDER BY id
    """)).mappings()
    counts = connection.execute(text("""
        SELECT source_instance_id, misp_type, category, count(*) AS attributes,
               min(collected_at) AS earliest, max(collected_at) AS latest
        FROM collection.observacao_origem
        WHERE removed_at IS NULL AND misp_type IN ('domain', 'url')
        GROUP BY source_instance_id, misp_type, category
        ORDER BY source_instance_id, misp_type, category
    """)).mappings()
    return {"sources": [dict(row) for row in sources], "counts": [dict(row) for row in counts]}


def main():
    config = load_configuration("migration")
    engine = engine_from_configuration(config)
    try:
        with engine.connect() as connection:
            print(json.dumps(inventory(connection), default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
