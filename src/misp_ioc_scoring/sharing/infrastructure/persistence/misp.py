"""SQL `SharingStore`: effective policy, peers, suspension and one current attempt per (peer, IOC)."""
from dataclasses import fields

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from misp_ioc_scoring.shared.database import transaction
from misp_ioc_scoring.sharing.domain.sharing import AttemptState, ShareAttempt

from .models import MispPeerModel, SharingAttemptModel, SharingPolicyModel

_ATTEMPT_FIELDS = [f.name for f in fields(ShareAttempt)]


class SqlSharingStore:
    """Each write commits on its own, so a later failure never hides an earlier request."""

    def __init__(self, engine, policy):
        self.engine = engine
        self.policy = policy

    @property
    def policy_hash(self):
        return self.policy.policy_hash

    def record_policy(self, loaded_at):
        with transaction(self.engine) as session:
            query = insert(SharingPolicyModel).values(policy_hash=self.policy_hash, loaded_at=loaded_at,
                                                      peers=self.policy.public_view())
            session.execute(query.on_conflict_do_update(index_elements=["policy_hash"],
                                                        set_={"loaded_at": loaded_at}))
            for peer in self.policy.peers:
                values = dict(peer_id=peer.peer_id, base_url=peer.base_url,
                              credential_secret_ref=peer.credential_secret_ref,
                              minimum_priority_score=peer.minimum_priority_score, distribution=peer.distribution,
                              sharing_group_uuid=peer.sharing_group_uuid,
                              outbound_event_uuid=peer.outbound_event_uuid, loaded_at=loaded_at)
                query = insert(MispPeerModel).values(**values)
                session.execute(query.on_conflict_do_update(
                    index_elements=["peer_id"], set_={k: query.excluded[k] for k in values if k != "peer_id"}))

    def suspend(self, reason, at):
        with transaction(self.engine) as session:
            session.execute(update(SharingPolicyModel).where(SharingPolicyModel.policy_hash == self.policy_hash)
                            .values(suspended_at=at, suspension_reason=str(reason)))

    def resume(self):
        with transaction(self.engine) as session:
            session.execute(update(SharingPolicyModel).where(SharingPolicyModel.policy_hash == self.policy_hash)
                            .values(suspended_at=None, suspension_reason=None))

    def attempts(self, peer_id):
        with transaction(self.engine) as session:
            rows = session.scalars(select(SharingAttemptModel).where(SharingAttemptModel.peer_id == peer_id))
            return {row.ioc_id: ShareAttempt(**{name: getattr(row, name) for name in _ATTEMPT_FIELDS}) for row in rows}

    def save(self, attempt: ShareAttempt):
        values = {name: getattr(attempt, name) for name in _ATTEMPT_FIELDS}
        values["state"] = AttemptState(values["state"]).value
        values["last_error"] = values["last_error"][:100] if values["last_error"] else None
        with transaction(self.engine) as session:
            query = insert(SharingAttemptModel).values(**values)
            session.execute(query.on_conflict_do_update(
                index_elements=["peer_id", "ioc_id"],
                set_={**{k: query.excluded[k] for k in values if k not in ("peer_id", "ioc_id")},
                      "updated_at": query.excluded.updated_at}))
