"""Add resolution plan context to mini_submission

Links mini submissions to the resolution plan and optionally the specific step
that was shown when the note was submitted.

Revision ID: a1b2c3d4e5f6
Revises: 20260120_1600_add_detection_config
Create Date: 2026-01-21 02:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p1l2a3n4c5t6'
down_revision = 'r1e2s3o4l5v6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make system_response_id nullable (for note-only submissions)
    op.alter_column(
        'mini_submission',
        'system_response_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True
    )
    
    # Add resolution_plan_id column
    op.add_column(
        'mini_submission',
        sa.Column(
            'resolution_plan_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('resolution_plan.plan_id'),
            nullable=True
        )
    )
    
    # Add plan_step_id column
    op.add_column(
        'mini_submission',
        sa.Column(
            'plan_step_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('plan_step.step_id'),
            nullable=True
        )
    )
    
    # Add indexes for efficient lookups
    op.create_index(
        'ix_mini_submission_resolution_plan_id',
        'mini_submission',
        ['resolution_plan_id']
    )
    op.create_index(
        'ix_mini_submission_plan_step_id',
        'mini_submission',
        ['plan_step_id']
    )


def downgrade() -> None:
    op.drop_index('ix_mini_submission_plan_step_id', table_name='mini_submission')
    op.drop_index('ix_mini_submission_resolution_plan_id', table_name='mini_submission')
    op.drop_column('mini_submission', 'plan_step_id')
    op.drop_column('mini_submission', 'resolution_plan_id')
    # Restore system_response_id to non-nullable
    op.alter_column(
        'mini_submission',
        'system_response_id',
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False
    )
