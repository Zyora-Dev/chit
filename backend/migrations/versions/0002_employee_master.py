"""Employee master, salary history and private documents.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision="0002";down_revision="0001";branch_labels=None;depends_on=None

def upgrade():
    bind=op.get_bind()
    # Metadata creates the full employee schema consistently for fresh and existing databases.
    from app.models.employee import Employee, EmployeeDocument, EmployeeSalaryStructure
    Employee.__table__.create(bind,checkfirst=True)
    EmployeeSalaryStructure.__table__.create(bind,checkfirst=True)
    EmployeeDocument.__table__.create(bind,checkfirst=True)

def downgrade():
    op.drop_table("employee_documents");op.drop_table("employee_salary_structures");op.drop_table("employees")
