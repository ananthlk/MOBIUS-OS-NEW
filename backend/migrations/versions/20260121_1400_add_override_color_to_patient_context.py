"""Add override_color field to patient_context

Stores the user override color directly in the database.
When user sets attention_status, we map it to color and store override_color.
This ensures the color persists across loads and doesn't need frontend mapping.

Revision ID: o1v2e3r4r5i6d7e
Revises: r1e2s3o4l5v6u7
Create Date: 2026-01-21 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'o1v2e3r4r5i6d7e'
down_revision = 'r1e2s3o4l5v6u7'  # Points to 20260122_1305_add_resolved_until_to_patient_context
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add override_color column to patient_context
    op.add_column(
        'patient_context',
        sa.Column(
            'override_color',
            sa.String(20),
            nullable=True,
            comment='User override color. Values: "purple" | "green" | "yellow" | "red" | "blue" | "grey" | null. Stored when user overrides attention_status.'
        )
    )


def downgrade() -> None:
    op.drop_column('patient_context', 'override_color')
