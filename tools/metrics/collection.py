"""Collection metrics depend only on reflected read-only tables."""
from sqlalchemy import func, select


def collection_metrics(connection, tables):
    metrics = []
    rejections = tables.get('collection.rejeicao_indicador')
    if rejections is not None:
        query = select(rejections.c.source_instance_id, rejections.c.reason, func.count()).group_by(
            rejections.c.source_instance_id, rejections.c.reason)
        metrics.extend((f'rejections:{source}:{reason}', count) for source, reason, count in connection.execute(query))
    warninglists = tables.get('collection.entrada_warninglist')
    if warninglists is not None:
        count = connection.scalar(select(func.count()).select_from(warninglists).where(warninglists.c.supported.is_(False)))
        metrics.append(('unsupported_warninglist_entries', count))
    endpoints = tables.get('collection.endpoint_coleta')
    if endpoints is not None:
        for row in connection.execute(select(endpoints.c.id, endpoints.c.status, endpoints.c.last_run_at,
                                             endpoints.c.last_success_at, endpoints.c.error, endpoints.c.warnings)).mappings():
            for key in ('status', 'last_run_at', 'last_success_at', 'error', 'warnings'):
                metrics.append((f'collection:{row["id"]}:{key}', row[key]))
    return metrics
