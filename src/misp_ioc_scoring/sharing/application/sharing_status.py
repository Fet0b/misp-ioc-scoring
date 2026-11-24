"""Structured status of a sharing round: counts per peer and state, never values."""
import logging

log = logging.getLogger(__name__)


def report_sharing(result):
    if result is None:
        return
    for peer_id, states in sorted(result.items()):
        log.info('sharing', extra={'event': 'sharing_status', 'source_instance_id': peer_id,
                                   'count': sum(states.values()), 'status': dict(sorted(states.items()))})
