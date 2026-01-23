"""Add factor_overrides column to patient_context

Revision ID: add_factor_overrides
Revises: f1a2c3t4o5r6
Create Date: 2026-01-23

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_factor_overrides'
down_revision = 'f1a2c3t4o5r6'
branch_labels = None
depends_on = None


def upgrade():
    # Add factor_overrides JSONB column for per-factor user status overrides
    op.add_column('patient_context', sa.Column('factor_overrides', postgresql.JSONB(), nullable=True))


def downgrade():
    op.drop_column('patient_context', 'factor_overrides')
