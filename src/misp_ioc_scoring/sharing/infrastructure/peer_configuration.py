"""Peers of the `scoring-sharing` container, read once at startup (FR-015).

`MISP_PEERS_SECRET_REF` points to JSON:
{"local": {"base_url": ..., "credential_secret_ref": ..., "allow_http": false},
 "peers": [{"peer_id": ..., "base_url": ..., "credential_secret_ref": ...,
            "minimum_priority_score": 0-100, "distribution": "1"|"2"|"3"|"4",
            "sharing_group_uuid": optional, "allow_http": false}]}
Secrets stay as references; the effective policy hash never includes them.
"""
import hashlib
import json
import math
from dataclasses import asdict, dataclass

from misp_ioc_scoring.shared.configuration import resolve_secret
from misp_ioc_scoring.shared.errors import ConfigurationError
from misp_ioc_scoring.sharing.domain.sharing import PeerPolicy

_REFERENCE_PREFIXES = ('file:/', 'env:')


@dataclass(frozen=True)
class LocalInstance:
    base_url: str
    credential_secret_ref: str
    allow_http: bool = False


@dataclass(frozen=True)
class SharingPolicy:
    local: LocalInstance
    peers: tuple[PeerPolicy, ...]
    interval_seconds: float
    retry_attempts: int
    retry_backoff_seconds: float

    def public_view(self) -> dict:
        """Policy without secret references (what is persisted and hashed)."""
        peers = [{k: v for k, v in asdict(peer).items() if k != 'credential_secret_ref'} for peer in self.peers]
        return {'local': self.local.base_url, 'peers': peers, 'interval_seconds': self.interval_seconds,
                'retry_attempts': self.retry_attempts, 'retry_backoff_seconds': self.retry_backoff_seconds}

    @property
    def policy_hash(self) -> str:
        canonical = json.dumps(self.public_view(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(canonical.encode()).hexdigest()


def _url(value, allow_http, code):
    from urllib.parse import urlsplit
    if not isinstance(value, str):
        raise ConfigurationError(code)
    parsed = urlsplit(value)
    if parsed.scheme not in ({'https', 'http'} if allow_http else {'https'}) or not parsed.hostname \
            or parsed.username or parsed.password:
        raise ConfigurationError(code)
    return value.rstrip('/')


def _reference(value, code):
    if not isinstance(value, str) or not value.startswith(_REFERENCE_PREFIXES):
        raise ConfigurationError(code)
    return value


def parse_sharing_policy(raw_text, *, interval_seconds, retry_attempts, retry_backoff_seconds) -> SharingPolicy:
    try:
        raw = json.loads(raw_text)
        local_raw, peers_raw = raw['local'], raw['peers']
        if not isinstance(local_raw, dict) or not isinstance(peers_raw, list) or not peers_raw:
            raise ValueError
    except (TypeError, ValueError, KeyError):
        raise ConfigurationError('MISP_PEERS') from None
    allow_local_http = local_raw.get('allow_http') is True
    local = LocalInstance(_url(local_raw.get('base_url'), allow_local_http, 'MISP_PEERS_LOCAL'),
                          _reference(local_raw.get('credential_secret_ref'), 'MISP_PEERS_LOCAL'), allow_local_http)
    peers = []
    for item in peers_raw:
        if not isinstance(item, dict):
            raise ConfigurationError('MISP_PEERS')
        peer_id = item.get('peer_id')
        if not isinstance(peer_id, str) or not peer_id.strip() or len(peer_id) > 100:
            raise ConfigurationError('MISP_PEERS_PEER_ID')
        minimum = item.get('minimum_priority_score')
        if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or not math.isfinite(minimum) \
                or not 0 <= minimum <= 100:
            raise ConfigurationError('MISP_PEERS_MINIMUM_PRIORITY_SCORE')
        distribution = str(item.get('distribution'))
        group = item.get('sharing_group_uuid')
        if distribution not in {'1', '2', '3', '4'} or (distribution == '4') != bool(group):
            raise ConfigurationError('MISP_PEERS_DISTRIBUTION')
        allow_http = item.get('allow_http') is True
        peers.append(PeerPolicy(peer_id=peer_id, base_url=_url(item.get('base_url'), allow_http, 'MISP_PEERS_BASE_URL'),
                                credential_secret_ref=_reference(item.get('credential_secret_ref'),
                                                                 'MISP_PEERS_CREDENTIAL_SECRET_REF'),
                                minimum_priority_score=float(minimum), distribution=distribution,
                                sharing_group_uuid=group or None, allow_http=allow_http))
    if len({peer.peer_id for peer in peers}) != len(peers):
        raise ConfigurationError('MISP_PEERS_PEER_ID')
    return SharingPolicy(local, tuple(peers), interval_seconds, retry_attempts, retry_backoff_seconds)


def load_sharing_policy(configuration) -> SharingPolicy:
    text = resolve_secret(configuration.misp_peers_secret_ref).get_secret_value()
    return parse_sharing_policy(text, interval_seconds=configuration.sharing_interval_seconds,
                                retry_attempts=configuration.sharing_retry_attempts,
                                retry_backoff_seconds=configuration.sharing_retry_backoff_seconds)
