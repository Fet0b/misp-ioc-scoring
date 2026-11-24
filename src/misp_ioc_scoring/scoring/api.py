from misp_ioc_scoring.scoring.domain.simple_blocking import BLOCKABLE_TYPES


def blocking_decision(session, source_instance_id, *, attribute_uuid=None, attribute_id=None):
    """Return a read-only effective decision, or None when no attribute is known."""
    from sqlalchemy import text

    if (attribute_uuid is None) == (attribute_id is None):
        raise ValueError("Provide exactly one attribute identifier")
    column = "attribute_uuid" if attribute_uuid is not None else "attribute_id"
    identifier = attribute_uuid if attribute_uuid is not None else attribute_id
    rows = session.execute(text(
        f"SELECT * FROM scoring.decisao_bloqueio_efetiva WHERE source_instance_id=:source AND {column}=:identifier"
    ), {"source": source_instance_id, "identifier": identifier}).mappings().fetchmany(2)
    if len(rows) > 1:
        raise ValueError("Ambiguous local attribute ID")
    return rows[0] if rows else None


def effective_blocks(session):
    from sqlalchemy import text

    return session.execute(text("""
        SELECT source_instance_id, attribute_uuid, as_of, rule_version
        FROM scoring.decisao_bloqueio_efetiva WHERE block
    """)).mappings()
