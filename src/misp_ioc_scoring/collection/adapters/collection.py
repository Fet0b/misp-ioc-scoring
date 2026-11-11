"""Paginated MISP queries and enabled warninglist retrieval."""
import hashlib
import json
from datetime import datetime
from pydantic import ValidationError
from misp_ioc_scoring.collection.adapters.schemas import EventPayload
from misp_ioc_scoring.collection.domain.warninglists import WarninglistEntry
from misp_ioc_scoring.shared.errors import OperationalError


class CollectionSource:
    def __init__(self, client, source_instance_id: str, to_ids_only: bool, page_size=500):
        self.client = client
        self.source_instance_id = source_instance_id
        self.to_ids_only = to_ids_only
        self.page_size = page_size

    def observations(self, collected_at: datetime, since: datetime | None = None):
        page = 1
        seen_pages = set()
        while True:
            params = dict(controller='events', return_format='json', page=page,
                          limit=self.page_size, metadata=False, deleted=False)
            if self.to_ids_only:
                params['to_ids'] = True
            if since:
                params['timestamp'] = [int(since.timestamp()), int(collected_at.timestamp())]
            payload = self.client.call('search', **params)
            rows = payload.get('response', payload) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise OperationalError('misp_payload_invalid')
            if not rows:
                break
            fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).digest()
            if fingerprint in seen_pages:
                raise OperationalError('misp_pagination_repeated')
            seen_pages.add(fingerprint)
            try:
                for row in rows:
                    event = EventPayload.model_validate(row.get('Event', row))
                    for observation in event.observations(self.source_instance_id, collected_at):
                        if observation.removed_at is None and (not self.to_ids_only or observation.to_ids):
                            yield observation
            except (ValidationError, ValueError, KeyError, TypeError, AttributeError):
                raise OperationalError('misp_payload_invalid') from None
            if len(rows) < self.page_size:
                break
            page += 1

    def warninglists(self):
        payload = self.client.call('warninglists')
        rows = payload.get('response', payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise OperationalError('misp_warninglists_invalid')
        for row in rows:
            item = row.get('Warninglist', row)
            enabled = item.get('enabled')
            if enabled not in (True, 1, '1', 'true'):
                continue
            detail = self.client.call('get_warninglist', warninglist=item['id'])
            detail = detail.get('Warninglist', detail)
            for value in detail.get('WarninglistEntry', []):
                raw = value['value'] if isinstance(value, dict) else value
                kind = detail['type']
                if kind == 'hostname':
                    raw = raw.encode('idna').decode('ascii').lower().rstrip('.')
                yield WarninglistEntry(self.source_instance_id, detail['name'], kind, raw)
