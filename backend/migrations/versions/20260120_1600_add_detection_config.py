"""Add detection_config table for patient context detection

Revision ID: d1e2f3g4h5i6
Revises: c1d2e3f4a5b6
Create Date: 2026-01-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


# revision identifiers, used by Alembic.
revision = 'd1e2f3g4h5i6'
down_revision = 'c1d2e3f4a5b6'  # Previous migration: add_crm_scheduler_tables
branch_labels = None
depends_on = None


def upgrade():
    # Create detection_config table
    op.create_table('detection_config',
        sa.Column('config_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('domain_pattern', sa.String(length=255), nullable=False),
        sa.Column('emr_system', sa.String(length=50), nullable=True),
        sa.Column('patterns_json', JSONB, nullable=False, server_default='{}'),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('description', sa.String(length=1000), nullable=True),
    )
    
    # Create indexes
    op.create_index('idx_detection_config_tenant', 'detection_config', ['tenant_id'])
    op.create_index('idx_detection_config_domain', 'detection_config', ['domain_pattern'])
    op.create_index('idx_detection_config_tenant_priority', 'detection_config', ['tenant_id', 'priority'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_detection_config_tenant_priority', table_name='detection_config')
    op.drop_index('idx_detection_config_domain', table_name='detection_config')
    op.drop_index('idx_detection_config_tenant', table_name='detection_config')
    
    # Drop table
    op.drop_table('detection_config')
