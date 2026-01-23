"""Add factor_modes to resolution_plan and assignee_type to plan_step.

Revision ID: f1a2c3t4o5r6
Revises: 20260122_add_evidence_layers
Create Date: 2026-01-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'f1a2c3t4o5r6'
down_revision = 'e1v2i3d4e5n6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Add factor_modes to resolution_plan
    if 'resolution_plan' in existing_tables:
        existing_columns = [c['name'] for c in inspector.get_columns('resolution_plan')]
        
        if 'factor_modes' not in existing_columns:
            op.add_column('resolution_plan', 
                sa.Column('factor_modes', postgresql.JSONB(), server_default='{}'))
            print("  [added] resolution_plan.factor_modes column")
        else:
            print("  [skip] resolution_plan.factor_modes already exists")
    
    # Add assignee_type to plan_step
    if 'plan_step' in existing_tables:
        existing_columns = [c['name'] for c in inspector.get_columns('plan_step')]
        
        if 'assignee_type' not in existing_columns:
            op.add_column('plan_step',
                sa.Column('assignee_type', sa.String(20), nullable=True))
            print("  [added] plan_step.assignee_type column")
        else:
            print("  [skip] plan_step.assignee_type already exists")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Remove assignee_type from plan_step
    if 'plan_step' in existing_tables:
        existing_columns = [c['name'] for c in inspector.get_columns('plan_step')]
        if 'assignee_type' in existing_columns:
            op.drop_column('plan_step', 'assignee_type')
    
    # Remove factor_modes from resolution_plan
    if 'resolution_plan' in existing_tables:
        existing_columns = [c['name'] for c in inspector.get_columns('resolution_plan')]
        if 'factor_modes' in existing_columns:
            op.drop_column('resolution_plan', 'factor_modes')
