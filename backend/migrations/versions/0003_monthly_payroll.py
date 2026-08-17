"""Monthly payroll runs and items.
Revision ID: 0003
Revises: 0002
"""
revision="0003";down_revision="0002";branch_labels=None;depends_on=None
def upgrade():
    from alembic import op
    from app.models.payroll import PayrollRun,PayrollItem
    bind=op.get_bind();PayrollRun.__table__.create(bind,checkfirst=True);PayrollItem.__table__.create(bind,checkfirst=True)
def downgrade():
    from alembic import op
    op.drop_table("payroll_items");op.drop_table("payroll_runs")
