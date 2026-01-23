"""add_agentic_columns_to_payment_probability

Add missing columns for batch job workflow recommendations:
- agentic_confidence
- recommended_mode
- recommendation_reason
- agentic_actions

Revision ID: c4d5e6f7a8b9
Revises: 20260123_add_user_remedy_table
Create Date: 2026-01-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, None] = 'u5e7r3m2e1d0'  # After add_user_remedy_table
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add agentic/batch recommendation columns to payment_probability
    op.add_column('payment_probability', 
        sa.Column('agentic_confidence', sa.Float(), nullable=True,
                  comment='0.0-1.0, how confident Mobius is in automation')
    )
    op.add_column('payment_probability',
        sa.Column('recommended_mode', sa.String(length=20), nullable=True,
                  comment='mobius | together | manual')
    )
    op.add_column('payment_probability',
        sa.Column('recommendation_reason', sa.Text(), nullable=True,
                  comment='Why batch recommends this mode')
    )
    op.add_column('payment_probability',
        sa.Column('agentic_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='What Mobius would do automatically')
    )


def downgrade() -> None:
    op.drop_column('payment_probability', 'agentic_actions')
    op.drop_column('payment_probability', 'recommendation_reason')
    op.drop_column('payment_probability', 'recommended_mode')
    op.drop_column('payment_probability', 'agentic_confidence')
