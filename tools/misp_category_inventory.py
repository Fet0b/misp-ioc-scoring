"""Print aggregate URL and domain categories visible to the observer role."""
import json

from sqlalchemy import text

from misp_ioc_scoring.shared.configuration import load_configuration
from misp_ioc_scoring.shared.database import engine_from_configuration


def main():
    config = load_configuration("migration")
    engine = engine_from_configuration(config)
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            rows = connection.execute(text("""
                SELECT source_instance_id, misp_type, category, count(*) AS attributes,
                       min(collected_at) AS earliest, max(collected_at) AS latest
                FROM collection.observacao_origem
                WHERE removed_at IS NULL AND misp_type IN ('domain', 'url')
                GROUP BY source_instance_id, misp_type, category
                ORDER BY source_instance_id, misp_type, category
            """)).mappings()
            print(json.dumps([dict(row) for row in rows], default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
