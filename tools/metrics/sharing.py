"""MISP sharing metrics computed only from reflected, exported tables."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select


def sharing_metrics(connection, tables, max_age_hours, now=None):
    metrics = []
    attempts = tables.get('sharing.tentativa_compartilhamento')
    if attempts is not None:
        for peer, state, count in connection.execute(
                select(attempts.c.peer_id, attempts.c.state, func.count())
                .group_by(attempts.c.peer_id, attempts.c.state).order_by(attempts.c.peer_id, attempts.c.state)):
            metrics.append((f'sharing:{peer}:{state}', count))
        pending = connection.scalar(select(func.count()).select_from(attempts).where(
            attempts.c.state.in_(('eligible', 'requested', 'ambiguous'))))
        failed = connection.scalar(select(func.count()).select_from(attempts).where(attempts.c.state == 'failed'))
        metrics += [('sharing:pending', pending), ('sharing:failed', failed)]
    policies = tables.get('sharing.politica_compartilhamento')
    if policies is not None:
        current = connection.execute(select(policies.c.policy_hash, policies.c.loaded_at)
                                     .order_by(policies.c.loaded_at.desc()).limit(1)).first()
        metrics.append(('sharing:policy_hash', current[0] if current else 'none'))
    runs = tables.get('scoring.execucao_scoring')
    if runs is not None:
        now = now or datetime.now(timezone.utc)
        last = connection.scalar(select(func.max(runs.c.finished_at)).where(runs.c.status == 'completed'))
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        metrics.append(('sharing:suspended', last is None or last <= now - timedelta(hours=max_age_hours)))
    return metrics
