import logging
logger = logging.getLogger(__name__)


def report_status(source_instance_id: str, status: str, code: str | None = None):
    logger.log(logging.ERROR if status == 'failed' else logging.INFO, 'collection',
               extra={'event': 'collection_status', 'source_instance_id': source_instance_id,
                      'status': status, 'code': code or 'ok'})
