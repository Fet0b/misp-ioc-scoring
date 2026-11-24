"""CARIOCA scoring metrics computed only from reflected, exported tables."""
import json

from sqlalchemy import func, select


def _warnings(value):
    if isinstance(value, str):
        value = json.loads(value or '[]')
    return list(value or [])


def scoring_metrics(connection, tables):
    runs = tables.get('scoring.execucao_scoring')
    if runs is None:
        return []
    metrics = []
    for status, count in connection.execute(select(runs.c.status, func.count()).group_by(runs.c.status)):
        metrics.append((f'scoring:runs:{status}', count))
    last = connection.execute(select(runs).where(runs.c.status == 'completed')
                              .order_by(runs.c.finished_at.desc(), runs.c.id).limit(1)).mappings().first()
    if last is None:
        metrics.append(('scoring:last_success', 'none'))
        return metrics
    warnings = _warnings(last['warnings'])
    duration = (last['finished_at'] - last['started_at']).total_seconds() if last['started_at'] else None
    metrics += [
        ('scoring:last_success:run_id', last['id']),
        ('scoring:last_success:as_of', last['as_of']),
        ('scoring:last_success:finished_at', last['finished_at']),
        ('scoring:last_success:duration_seconds', duration),
        ('scoring:last_success:valid_population', last['valid_population']),
        ('scoring:last_success:observations_evaluated', last['observations_evaluated']),
        ('scoring:last_success:excluded', last['excluded']),
        ('scoring:last_success:warning:empty_population', 'empty_population' in warnings),
        ('scoring:last_success:warning:minmax_degenerate',
         ','.join(w.split(':', 1)[1] for w in warnings if w.startswith('minmax_degenerate:')) or 'none'),
    ]
    exclusions = tables.get('scoring.exclusao_score')
    if exclusions is not None:
        query = (select(exclusions.c.reason, func.count()).where(exclusions.c.scoring_run_id == last['id'])
                 .group_by(exclusions.c.reason).order_by(exclusions.c.reason))
        metrics.extend((f'scoring:last_success:exclusions:{reason}', count)
                       for reason, count in connection.execute(query))
    results = tables.get('scoring.resultado_score')
    if results is not None:
        cutoff = connection.scalar(select(func.min(results.c.priority_score)).where(
            results.c.scoring_run_id == last['id'], results.c.in_top_n.is_(True)))
        metrics.append(('scoring:last_success:top_n_cutoff', cutoff))
    return metrics
