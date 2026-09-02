"""Add Agent GPS evidence fields.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_locations", sa.Column("is_mocked", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("chit_payments", sa.Column("collection_accuracy_meters", sa.Numeric(8, 2), nullable=True))
    op.add_column("chit_payments", sa.Column("collection_recorded_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("chit_payments", "collection_recorded_at")
    op.drop_column("chit_payments", "collection_accuracy_meters")
    op.drop_column("agent_locations", "is_mocked")