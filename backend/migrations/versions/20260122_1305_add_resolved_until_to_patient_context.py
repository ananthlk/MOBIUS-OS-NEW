"""Add resolved_until field to patient_context

Adds time-bound suppression period for resolved patients.
When attention_status = 'resolved', resolved_until indicates
when the suppression period ends (visit_date + X days or fixed period).

Revision ID: r1e2s3o4l5v6u7
Revises: p1l2a3n4c5t6
Create Date: 2026-01-22 13:05:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'r1e2s3o4l5v6u7'
down_revision = 's1i2d3e4c5a6r'  # Points to 20260121_0300_add_sidecar_tables
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add resolved_until column to patient_context
    op.add_column(
        'patient_context',
        sa.Column(
            'resolved_until',
            sa.DateTime(),
            nullable=True,
            comment='Time-bound suppression period end date. When attention_status = "resolved", tasks/bottlenecks are suppressed until this date.'
        )
    )


def downgrade() -> None:
    op.drop_column('patient_context', 'resolved_until')
