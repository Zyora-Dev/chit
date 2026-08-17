"""Dynamic users, roles and permissions.
Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa
revision="0005";down_revision="0004";branch_labels=None;depends_on=None
def upgrade():
    bind=op.get_bind();op.add_column("users",sa.Column("login_id",sa.String(50),nullable=True));op.create_index("ix_users_login_id","users",["login_id"],unique=True)
    from app.models.rbac import Permission,Role,CompanyUser,role_permissions
    Permission.__table__.create(bind,checkfirst=True);Role.__table__.create(bind,checkfirst=True);role_permissions.create(bind,checkfirst=True);CompanyUser.__table__.create(bind,checkfirst=True)
def downgrade():
    op.drop_table("company_users");op.drop_table("role_permissions");op.drop_table("roles");op.drop_table("permissions");op.drop_index("ix_users_login_id",table_name="users");op.drop_column("users","login_id")
