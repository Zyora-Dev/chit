"""Collection agent accounts, assignments, shifts and live locations.
Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
revision="0004";down_revision="0003";branch_labels=None;depends_on=None
def upgrade():
    bind=op.get_bind();op.add_column("users",sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.text("true")))
    from app.models.agent import CollectionAgent,AgentGroupAssignment,AgentMemberAssignment,AgentShift,AgentLocation
    for table in (CollectionAgent.__table__,AgentGroupAssignment.__table__,AgentMemberAssignment.__table__,AgentShift.__table__,AgentLocation.__table__):table.create(bind,checkfirst=True)
def downgrade():
    for name in ("agent_locations","agent_shifts","agent_member_assignments","agent_group_assignments","collection_agents"):op.drop_table(name)
    op.drop_column("users","is_active")
