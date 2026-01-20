"""Add user_reported_issue table

Revision ID: e1f2g3h4i5j6
Revises: d1e2f3g4h5i6
Create Date: 2026-01-20 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e1f2g3h4i5j6'
down_revision = 'd1e2f3g4h5i6'  # Previous: detection_config
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_reported_issue',
        sa.Column('issue_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('reported_by_id', sa.UUID(), nullable=True),
        sa.Column('issue_text', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending', comment='pending | processed | dismissed'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('payment_probability_id', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], name='fk_user_issue_patient_context'),
        sa.ForeignKeyConstraint(['reported_by_id'], ['app_user.user_id'], name='fk_user_issue_reported_by'),
        sa.ForeignKeyConstraint(['payment_probability_id'], ['payment_probability.probability_id'], name='fk_user_issue_probability'),
        sa.PrimaryKeyConstraint('issue_id')
    )
    
    # Index for finding pending issues (batch job query)
    op.create_index('ix_user_reported_issue_status', 'user_reported_issue', ['status'], unique=False)
    op.create_index('ix_user_reported_issue_patient', 'user_reported_issue', ['patient_context_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_reported_issue_patient', table_name='user_reported_issue')
    op.drop_index('ix_user_reported_issue_status', table_name='user_reported_issue')
    op.drop_table('user_reported_issue')
