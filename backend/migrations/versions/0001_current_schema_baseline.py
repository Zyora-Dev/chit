"""Current schema baseline.

Revision ID: 0001
Revises: None
"""
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Existing installations are created additively by app.db.init_db.
    # New schema changes must be added as subsequent Alembic revisions.
    pass


def downgrade():
    pass