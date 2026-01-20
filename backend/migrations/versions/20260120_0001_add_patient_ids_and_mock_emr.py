"""Add patient_ids and mock_emr tables

Revision ID: a1b2c3d4e5f6
Revises: 263b5633c96e
Create Date: 2026-01-20 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '263b5633c96e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create patient_ids table (ID translation layer)
    op.create_table('patient_ids',
        sa.Column('patient_id_record', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('id_type', sa.String(length=50), nullable=False),
        sa.Column('id_value', sa.String(length=255), nullable=False),
        sa.Column('source_system', sa.String(length=100), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.PrimaryKeyConstraint('patient_id_record'),
        sa.UniqueConstraint('id_type', 'id_value', name='uq_patient_ids_type_value'),
    )
    
    # Create indexes for patient_ids
    op.create_index('idx_patient_ids_type_value', 'patient_ids', ['id_type', 'id_value'])
    op.create_index('idx_patient_ids_context', 'patient_ids', ['patient_context_id'])
    
    # Create mock_emr table (clinical data)
    op.create_table('mock_emr',
        sa.Column('mock_emr_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('allergies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('medications', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('vitals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recent_visits', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('primary_care_provider', sa.String(length=255), nullable=True),
        sa.Column('emergency_contact_name', sa.String(length=255), nullable=True),
        sa.Column('emergency_contact_phone', sa.String(length=50), nullable=True),
        sa.Column('emergency_contact_relation', sa.String(length=100), nullable=True),
        sa.Column('blood_type', sa.String(length=10), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.PrimaryKeyConstraint('mock_emr_id'),
        sa.UniqueConstraint('patient_context_id', name='uq_mock_emr_patient_context'),
    )


def downgrade() -> None:
    # Drop mock_emr table
    op.drop_table('mock_emr')
    
    # Drop patient_ids indexes and table
    op.drop_index('idx_patient_ids_context', table_name='patient_ids')
    op.drop_index('idx_patient_ids_type_value', table_name='patient_ids')
    op.drop_table('patient_ids')
