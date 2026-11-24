"""Re-scoring candidate metrics from the reflected `scoring.candidato_rescoring` table."""
from datetime import datetime, timezone

from sqlalchemy import func, select


def candidate_metrics(connection, tables, now=None):
    candidates = tables.get('scoring.candidato_rescoring')
    if candidates is None:
        return []
    now = now or datetime.now(timezone.utc)
    pending = connection.scalar(select(func.count()).select_from(candidates).where(candidates.c.pending.is_(True)))
    oldest = connection.scalar(select(func.min(candidates.c.marked_at)).where(candidates.c.pending.is_(True)))
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    last_error = connection.execute(select(candidates.c.last_error, candidates.c.last_attempt_at)
                                    .where(candidates.c.last_error.is_not(None))
                                    .order_by(candidates.c.last_attempt_at.desc()).limit(1)).first()
    return [
        ('candidates:pending', pending),
        ('candidates:oldest_pending_age_seconds', (now - oldest).total_seconds() if oldest else None),
        ('candidates:last_error', last_error[0] if last_error else 'none'),
        ('candidates:last_error_at', last_error[1] if last_error else None),
    ]
