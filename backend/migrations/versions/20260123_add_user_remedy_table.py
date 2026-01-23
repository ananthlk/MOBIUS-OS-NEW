"""Add user_remedy table for capturing user-tried remedies

Revision ID: u5e7r3m2e1d0
Revises: f1a2c3t4o5r6
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'u5e7r3m2e1d0'
down_revision = 'add_factor_overrides'  # After add_factor_overrides
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_remedy',
        sa.Column('remedy_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('factor_type', sa.String(20), nullable=False),
        sa.Column('remedy_text', sa.Text(), nullable=False),
        sa.Column('outcome', sa.String(20), nullable=False),
        sa.Column('outcome_notes', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id']),
        sa.ForeignKeyConstraint(['plan_id'], ['resolution_plan.plan_id']),
        sa.ForeignKeyConstraint(['created_by'], ['app_user.user_id']),
        sa.PrimaryKeyConstraint('remedy_id')
    )
    
    # Index for efficient lookups by patient and factor
    op.create_index(
        'ix_user_remedy_patient_factor',
        'user_remedy',
        ['patient_context_id', 'factor_type']
    )
    
    # Index for learning queries (aggregate by factor + outcome)
    op.create_index(
        'ix_user_remedy_factor_outcome',
        'user_remedy',
        ['factor_type', 'outcome']
    )


def downgrade() -> None:
    op.drop_index('ix_user_remedy_factor_outcome', table_name='user_remedy')
    op.drop_index('ix_user_remedy_patient_factor', table_name='user_remedy')
    op.drop_table('user_remedy')
