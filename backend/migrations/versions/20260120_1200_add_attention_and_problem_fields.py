"""add_attention_and_problem_fields

Add problem_statement/problem_details to payment_probability
Add attention_status fields to patient_context

Revision ID: b8c9d0e1f2a3
Revises: 7a66ac2bfed8
Create Date: 2026-01-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = '7a66ac2bfed8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add problem_statement and problem_details to payment_probability
    op.add_column('payment_probability', 
        sa.Column('problem_statement', sa.String(length=255), nullable=True,
                  comment='LLM-generated: Action - Reason format')
    )
    op.add_column('payment_probability',
        sa.Column('problem_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                  comment='Ordered list of issues with context')
    )
    
    # Add attention_status fields to patient_context
    op.add_column('patient_context',
        sa.Column('attention_status', sa.String(length=30), nullable=True,
                  comment='User override: resolved | confirmed_unresolved | unable_to_confirm')
    )
    op.add_column('patient_context',
        sa.Column('attention_status_at', sa.DateTime(), nullable=True)
    )
    op.add_column('patient_context',
        sa.Column('attention_status_by_id', sa.UUID(), nullable=True)
    )
    
    # Add foreign key for attention_status_by_id
    op.create_foreign_key(
        'fk_patient_context_attention_status_by',
        'patient_context', 'app_user',
        ['attention_status_by_id'], ['user_id']
    )


def downgrade() -> None:
    # Remove foreign key first
    op.drop_constraint('fk_patient_context_attention_status_by', 'patient_context', type_='foreignkey')
    
    # Remove attention_status fields from patient_context
    op.drop_column('patient_context', 'attention_status_by_id')
    op.drop_column('patient_context', 'attention_status_at')
    op.drop_column('patient_context', 'attention_status')
    
    # Remove problem fields from payment_probability
    op.drop_column('payment_probability', 'problem_details')
    op.drop_column('payment_probability', 'problem_statement')
