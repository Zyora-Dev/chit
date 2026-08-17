"""Security settings, MFA, recovery codes and session activity.
Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision="0006";down_revision="0005";branch_labels=None;depends_on=None

def upgrade():
    op.add_column("users",sa.Column("mfa_enabled",sa.Boolean(),server_default=sa.text("false"),nullable=False))
    op.add_column("users",sa.Column("mfa_secret_encrypted",sa.Text(),nullable=True))
    op.add_column("users",sa.Column("mfa_recovery_codes_hash",sa.Text(),nullable=True))
    op.add_column("users",sa.Column("mfa_enabled_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("auth_sessions",sa.Column("last_used_at",sa.DateTime(timezone=True),nullable=True))
    op.create_table("mfa_challenges",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("user_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("challenge_hash",sa.String(64),nullable=False),sa.Column("ip_address",sa.String(64),nullable=True),sa.Column("user_agent",sa.String(500),nullable=True),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("used_at",sa.DateTime(timezone=True),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_mfa_challenges_user_id","mfa_challenges",["user_id"])
    op.create_index("ix_mfa_challenges_challenge_hash","mfa_challenges",["challenge_hash"],unique=True)

def downgrade():
    op.drop_index("ix_mfa_challenges_challenge_hash",table_name="mfa_challenges");op.drop_index("ix_mfa_challenges_user_id",table_name="mfa_challenges");op.drop_table("mfa_challenges");op.drop_column("auth_sessions","last_used_at");op.drop_column("users","mfa_enabled_at");op.drop_column("users","mfa_recovery_codes_hash");op.drop_column("users","mfa_secret_encrypted");op.drop_column("users","mfa_enabled")
