"""Outbound event per peer on the local MISP; delivery is left to native sync push.

Never logs credentials or indicator values. Attribute UUIDs are deterministic (UUID v5 of
peer and IOC), so a repeated round updates instead of duplicating.
"""
from misp_ioc_scoring.sharing.domain.sharing import PeerPolicy

_NETWORK_TYPES = {'domain', 'hostname', 'domain|ip', 'ip-src', 'ip-dst', 'ip-src|port', 'ip-dst|port'}


def _rows(payload):
    rows = payload.get('response', payload) if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


class MispSynchronization:
    def __init__(self, local_client, peer_client_factory):
        self.local = local_client
        self.peer_client_factory = peer_client_factory
        self._peer_clients = {}

    def _peer(self, peer: PeerPolicy):
        if peer.peer_id not in self._peer_clients:
            self._peer_clients[peer.peer_id] = self.peer_client_factory(peer)
        return self._peer_clients[peer.peer_id]

    def sharing_group_members(self) -> dict:
        """Local sharing group id -> (uuid, server URLs), read at the start of each round."""
        members = {}
        for row in _rows(self.local.call('sharing_groups')):
            group = row.get('SharingGroup', row)
            servers = frozenset(str(item.get('Server', item).get('url', '')).rstrip('/')
                                for item in row.get('SharingGroupServer', []) if isinstance(item, dict))
            members[str(group['id'])] = (str(group['uuid']), servers)
        return members

    @staticmethod
    def peer_groups(peer: PeerPolicy, members) -> set:
        return {group_id for group_id, (_, servers) in members.items() if peer.base_url.rstrip('/') in servers}

    def ensure_event(self, peer: PeerPolicy, members):
        uuid = str(peer.outbound_event_uuid)
        if self.local.call('event_exists', event=uuid):
            return uuid
        event = {'uuid': uuid, 'info': 'misp-ioc-scoring outbound ' + peer.peer_id,
                 'distribution': peer.distribution, 'threat_level_id': '4', 'analysis': '2', 'published': False}
        if peer.distribution == '4':
            group = next((gid for gid, (guuid, _) in members.items() if guuid == peer.sharing_group_uuid), None)
            if group is None:
                raise ValueError('sharing_group_unknown')
            event['sharing_group_id'] = group
        self.local.call('add_event', event=event)
        return uuid

    def upsert(self, peer: PeerPolicy, attempt, score):
        """`score` carries type, normalized value and the local sharing group id (if distribution 4)."""
        attribute = {'uuid': str(attempt.outbound_attribute_uuid), 'type': score.type,
                     'value': score.normalized_value, 'to_ids': True,
                     'category': 'Network activity' if score.type in _NETWORK_TYPES else 'Payload delivery',
                     'distribution': attempt.outbound_distribution, 'deleted': False}
        if attempt.outbound_distribution == '4':
            attribute['sharing_group_id'] = score.sharing_group_id
        if self.local.call('attribute_exists', attribute=attribute['uuid']):
            self.local.call('update_attribute', attribute=attribute)
        else:
            self.local.call('add_attribute', event=str(peer.outbound_event_uuid), attribute=attribute)

    def remove(self, peer: PeerPolicy, attribute_uuid):
        uuid = str(attribute_uuid)
        if self.local.call('attribute_exists', attribute=uuid):
            self.local.call('delete_attribute', attribute=uuid, hard=False)

    def publish(self, peer: PeerPolicy):
        """Starts native sync; it is a request, never a confirmation."""
        return self.local.call('publish', event=str(peer.outbound_event_uuid), alert=False)

    def confirmed(self, peer: PeerPolicy, attribute_uuid) -> bool:
        return bool(self._peer(peer).call('attribute_exists', attribute=str(attribute_uuid)))
