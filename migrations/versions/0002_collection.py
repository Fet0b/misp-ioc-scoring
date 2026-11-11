"""Collection tables with provenance, rejections and warninglists."""
from alembic import op
from misp_ioc_scoring.collection.infrastructure.persistence.models import (
    EndpointModel, IOCModel, ObservationModel, RejectionModel, WarninglistModel,
)
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    for model in (EndpointModel, IOCModel, ObservationModel, RejectionModel, WarninglistModel):
        model.__table__.create(op.get_bind())


def downgrade():
    for model in (WarninglistModel, RejectionModel, ObservationModel, IOCModel, EndpointModel):
        model.__table__.drop(op.get_bind())
