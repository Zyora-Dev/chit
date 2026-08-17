"""Track the once-only company onboarding WhatsApp welcome.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("companies", sa.Column("welcome_whatsapp_sent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("companies", "welcome_whatsapp_sent_at")