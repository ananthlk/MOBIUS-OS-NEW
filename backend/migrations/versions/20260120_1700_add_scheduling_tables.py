"""Add scheduling tables for unified EMR

Revision ID: f1g2h3i4j5k6
Revises: e1f2g3h4i5j6
Create Date: 2026-01-20 17:00:00.000000

This migration adds:
1. provider - Healthcare provider records
2. provider_schedule - Weekly availability templates
3. time_slot - Individual bookable slots
4. schedule_exception - Time off, holidays, blocked time
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f1g2h3i4j5k6'
down_revision = 'e1f2g3h4i5j6'  # Previous: add_user_reported_issue
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create provider table
    op.create_table(
        'provider',
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('provider_name', sa.String(255), nullable=False),
        sa.Column('credentials', sa.String(100), nullable=True),
        sa.Column('specialty', sa.String(100), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('npi', sa.String(20), nullable=True),
        sa.Column('default_slot_duration', sa.Integer(), default=30, nullable=False),
        sa.Column('max_patients_per_day', sa.Integer(), nullable=True),
        sa.Column('accepts_new_patients', sa.Boolean(), default=True, nullable=False),
        sa.Column('primary_location', sa.String(255), nullable=True),
        sa.Column('locations', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('photo_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_provider_tenant_id', 'provider', ['tenant_id'])
    op.create_index('ix_provider_specialty', 'provider', ['specialty'])
    op.create_index('ix_provider_is_active', 'provider', ['is_active'])

    # Create provider_schedule table
    op.create_table(
        'provider_schedule',
        sa.Column('schedule_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('provider.provider_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('slot_duration_minutes', sa.Integer(), default=30, nullable=False),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('room', sa.String(50), nullable=True),
        sa.Column('allowed_appointment_types', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_until', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_provider_schedule_provider_id', 'provider_schedule', ['provider_id'])
    op.create_index('ix_provider_schedule_day_of_week', 'provider_schedule', ['day_of_week'])

    # Create time_slot table
    op.create_table(
        'time_slot',
        sa.Column('slot_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('provider.provider_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('slot_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), default=30, nullable=False),
        sa.Column('status', sa.String(20), default='available', nullable=False),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('appointment.appointment_id'), nullable=True),
        sa.Column('location', sa.String(255), nullable=True),
        sa.Column('room', sa.String(50), nullable=True),
        sa.Column('block_reason', sa.String(255), nullable=True),
        sa.Column('blocked_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('held_until', sa.DateTime(), nullable=True),
        sa.Column('held_by_session', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_time_slot_provider_id', 'time_slot', ['provider_id'])
    op.create_index('ix_time_slot_slot_date', 'time_slot', ['slot_date'])
    op.create_index('ix_time_slot_status', 'time_slot', ['status'])
    op.create_index('ix_time_slot_provider_date', 'time_slot', ['provider_id', 'slot_date'])

    # Create schedule_exception table
    op.create_table(
        'schedule_exception',
        sa.Column('exception_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('provider.provider_id'), nullable=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('exception_type', sa.String(50), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=True),
        sa.Column('end_time', sa.Time(), nullable=True),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_recurring', sa.Boolean(), default=False, nullable=False),
        sa.Column('recurrence_pattern', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index('ix_schedule_exception_provider_id', 'schedule_exception', ['provider_id'])
    op.create_index('ix_schedule_exception_dates', 'schedule_exception', ['start_date', 'end_date'])


def downgrade() -> None:
    op.drop_table('schedule_exception')
    op.drop_table('time_slot')
    op.drop_table('provider_schedule')
    op.drop_table('provider')
