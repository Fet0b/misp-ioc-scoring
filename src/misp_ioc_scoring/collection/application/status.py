import logging
logger = logging.getLogger(__name__)


def report_status(source_instance_id: str, status: str, code: str | None = None, counts: dict | None = None):
    """Structured status of one collection run: counts only, never values or payloads."""
    counts = counts or {}
    extra = {'event': 'collection_status', 'source_instance_id': source_instance_id,
             'status': status, 'code': code or 'ok'}
    if counts:
        extra.update(count=counts.get('applied', 0), removed=counts.get('removed', 0),
                     rejections={source_instance_id: dict(sorted(counts.get('rejected', {}).items()))})
    logger.log(logging.ERROR if status == 'failed' else logging.INFO, 'collection', extra=extra)
