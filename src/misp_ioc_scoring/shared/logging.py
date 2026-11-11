"""Structured operational events with an allowlist of output fields."""
import json
import logging
from datetime import datetime, timezone

_SECRETS: set[str] = set()
_ALLOWED = ('event', 'source_instance_id', 'run_id', 'count', 'code', 'status')


def register_secret(value: str) -> None:
    if value:
        _SECRETS.add(value)


def _redact(value: object) -> str:
    result = str(value)
    for secret in sorted(_SECRETS, key=len, reverse=True):
        result = result.replace(secret, '[REDACTED]')
    return result


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Exception text, arbitrary messages and extra fields may contain raw payloads.
        result = {
            'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
        }
        for key in _ALLOWED:
            if hasattr(record, key):
                result[key] = _redact(getattr(record, key))
        if record.exc_info:
            result['exception_type'] = record.exc_info[0].__name__
        return json.dumps(result, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger('pymisp').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
