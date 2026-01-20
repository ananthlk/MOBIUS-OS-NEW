"""add_crm_scheduler_tables

Add tables for CRM/Scheduler system:
- appointment: Core appointment scheduling
- appointment_reminder: Pre/post visit reminders
- intake_form: Patient intake form tracking
- insurance_verification: Insurance eligibility verification
- intake_checklist: Overall intake readiness tracking

Revision ID: c1d2e3f4a5b6
Revises: b8c9d0e1f2a3
Create Date: 2026-01-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create appointment table
    op.create_table('appointment',
        sa.Column('appointment_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False, default=30),
        sa.Column('appointment_type', sa.String(length=50), nullable=False, default='follow_up'),
        sa.Column('status', sa.String(length=20), nullable=False, default='scheduled'),
        sa.Column('provider_name', sa.String(length=255), nullable=True),
        sa.Column('provider_id', sa.UUID(), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('room', sa.String(length=50), nullable=True),
        sa.Column('chief_complaint', sa.Text(), nullable=True),
        sa.Column('visit_reason', sa.Text(), nullable=True),
        sa.Column('checked_in_at', sa.DateTime(), nullable=True),
        sa.Column('wait_time_minutes', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('no_show_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('rescheduled_from_id', sa.UUID(), nullable=True),
        sa.Column('rescheduled_to_id', sa.UUID(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('patient_instructions', sa.Text(), nullable=True),
        sa.Column('needs_confirmation', sa.Boolean(), nullable=False, default=True),
        sa.Column('needs_insurance_verification', sa.Boolean(), nullable=False, default=False),
        sa.Column('needs_prior_auth', sa.Boolean(), nullable=False, default=False),
        sa.Column('extended_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.ForeignKeyConstraint(['rescheduled_from_id'], ['appointment.appointment_id'], ),
        sa.PrimaryKeyConstraint('appointment_id')
    )
    
    # Create index on appointment for common queries
    op.create_index('ix_appointment_scheduled_date', 'appointment', ['scheduled_date'])
    op.create_index('ix_appointment_patient_context_id', 'appointment', ['patient_context_id'])
    op.create_index('ix_appointment_status', 'appointment', ['status'])
    
    # Create appointment_reminder table
    op.create_table('appointment_reminder',
        sa.Column('reminder_id', sa.UUID(), nullable=False),
        sa.Column('appointment_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('reminder_type', sa.String(length=30), nullable=False, default='pre_visit'),
        sa.Column('channel', sa.String(length=20), nullable=False, default='sms'),
        sa.Column('scheduled_date', sa.Date(), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(), nullable=True),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, default='pending'),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('patient_responded', sa.Boolean(), nullable=False, default=False),
        sa.Column('patient_response', sa.Text(), nullable=True),
        sa.Column('response_at', sa.DateTime(), nullable=True),
        sa.Column('staff_action', sa.String(length=50), nullable=True),
        sa.Column('staff_action_at', sa.DateTime(), nullable=True),
        sa.Column('staff_action_by', sa.UUID(), nullable=True),
        sa.Column('staff_notes', sa.Text(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, default=0),
        sa.Column('max_attempts', sa.Integer(), nullable=False, default=3),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('message_template', sa.String(length=100), nullable=True),
        sa.Column('message_content', sa.Text(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('extended_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.appointment_id'], ),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.PrimaryKeyConstraint('reminder_id')
    )
    
    # Create indexes on appointment_reminder
    op.create_index('ix_appointment_reminder_status', 'appointment_reminder', ['status'])
    op.create_index('ix_appointment_reminder_due_date', 'appointment_reminder', ['due_date'])
    op.create_index('ix_appointment_reminder_reminder_type', 'appointment_reminder', ['reminder_type'])
    
    # Create intake_form table
    op.create_table('intake_form',
        sa.Column('form_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('form_type', sa.String(length=50), nullable=False),
        sa.Column('form_name', sa.String(length=255), nullable=True),
        sa.Column('form_version', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, default='not_started'),
        sa.Column('total_fields', sa.Integer(), nullable=True),
        sa.Column('completed_fields', sa.Integer(), nullable=True, default=0),
        sa.Column('completion_percentage', sa.Integer(), nullable=True, default=0),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_modified_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=False, default=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.UUID(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('is_valid', sa.Boolean(), nullable=False, default=False),
        sa.Column('validation_errors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('form_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('document_url', sa.String(length=500), nullable=True),
        sa.Column('document_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.PrimaryKeyConstraint('form_id')
    )
    
    # Create indexes on intake_form
    op.create_index('ix_intake_form_patient_context_id', 'intake_form', ['patient_context_id'])
    op.create_index('ix_intake_form_status', 'intake_form', ['status'])
    
    # Create insurance_verification table
    op.create_table('insurance_verification',
        sa.Column('verification_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('appointment_id', sa.UUID(), nullable=True),
        sa.Column('insurance_id', sa.String(length=100), nullable=True),
        sa.Column('insurance_name', sa.String(length=255), nullable=True),
        sa.Column('member_id', sa.String(length=100), nullable=True),
        sa.Column('group_number', sa.String(length=100), nullable=True),
        sa.Column('subscriber_name', sa.String(length=255), nullable=True),
        sa.Column('subscriber_relationship', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, default='pending'),
        sa.Column('verification_date', sa.Date(), nullable=True),
        sa.Column('service_date', sa.Date(), nullable=True),
        sa.Column('is_eligible', sa.Boolean(), nullable=True),
        sa.Column('coverage_start_date', sa.Date(), nullable=True),
        sa.Column('coverage_end_date', sa.Date(), nullable=True),
        sa.Column('copay_amount', sa.Integer(), nullable=True),
        sa.Column('coinsurance_percentage', sa.Integer(), nullable=True),
        sa.Column('deductible_amount', sa.Integer(), nullable=True),
        sa.Column('deductible_met', sa.Integer(), nullable=True),
        sa.Column('out_of_pocket_max', sa.Integer(), nullable=True),
        sa.Column('out_of_pocket_met', sa.Integer(), nullable=True),
        sa.Column('requires_prior_auth', sa.Boolean(), nullable=False, default=False),
        sa.Column('prior_auth_number', sa.String(length=100), nullable=True),
        sa.Column('prior_auth_status', sa.String(length=30), nullable=True),
        sa.Column('prior_auth_expires', sa.Date(), nullable=True),
        sa.Column('payer_response_code', sa.String(length=50), nullable=True),
        sa.Column('payer_response_message', sa.Text(), nullable=True),
        sa.Column('payer_response_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('verified_manually', sa.Boolean(), nullable=False, default=False),
        sa.Column('verified_by', sa.UUID(), nullable=True),
        sa.Column('verification_notes', sa.Text(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_retry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.appointment_id'], ),
        sa.PrimaryKeyConstraint('verification_id')
    )
    
    # Create indexes on insurance_verification
    op.create_index('ix_insurance_verification_patient_context_id', 'insurance_verification', ['patient_context_id'])
    op.create_index('ix_insurance_verification_status', 'insurance_verification', ['status'])
    
    # Create intake_checklist table
    op.create_table('intake_checklist',
        sa.Column('checklist_id', sa.UUID(), nullable=False),
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('patient_context_id', sa.UUID(), nullable=False),
        sa.Column('appointment_id', sa.UUID(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, default='incomplete'),
        sa.Column('demographics_complete', sa.Boolean(), nullable=False, default=False),
        sa.Column('insurance_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('consent_signed', sa.Boolean(), nullable=False, default=False),
        sa.Column('hipaa_signed', sa.Boolean(), nullable=False, default=False),
        sa.Column('medical_history_complete', sa.Boolean(), nullable=False, default=False),
        sa.Column('photo_id_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('insurance_card_scanned', sa.Boolean(), nullable=False, default=False),
        sa.Column('copay_collected', sa.Boolean(), nullable=False, default=False),
        sa.Column('total_items', sa.Integer(), nullable=False, default=8),
        sa.Column('completed_items', sa.Integer(), nullable=False, default=0),
        sa.Column('has_issues', sa.Boolean(), nullable=False, default=False),
        sa.Column('issues', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_updated_by', sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], ),
        sa.ForeignKeyConstraint(['patient_context_id'], ['patient_context.patient_context_id'], ),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointment.appointment_id'], ),
        sa.PrimaryKeyConstraint('checklist_id')
    )
    
    # Create indexes on intake_checklist
    op.create_index('ix_intake_checklist_patient_context_id', 'intake_checklist', ['patient_context_id'])
    op.create_index('ix_intake_checklist_status', 'intake_checklist', ['status'])


def downgrade() -> None:
    # Drop indexes and tables in reverse order
    op.drop_index('ix_intake_checklist_status', table_name='intake_checklist')
    op.drop_index('ix_intake_checklist_patient_context_id', table_name='intake_checklist')
    op.drop_table('intake_checklist')
    
    op.drop_index('ix_insurance_verification_status', table_name='insurance_verification')
    op.drop_index('ix_insurance_verification_patient_context_id', table_name='insurance_verification')
    op.drop_table('insurance_verification')
    
    op.drop_index('ix_intake_form_status', table_name='intake_form')
    op.drop_index('ix_intake_form_patient_context_id', table_name='intake_form')
    op.drop_table('intake_form')
    
    op.drop_index('ix_appointment_reminder_reminder_type', table_name='appointment_reminder')
    op.drop_index('ix_appointment_reminder_due_date', table_name='appointment_reminder')
    op.drop_index('ix_appointment_reminder_status', table_name='appointment_reminder')
    op.drop_table('appointment_reminder')
    
    op.drop_index('ix_appointment_status', table_name='appointment')
    op.drop_index('ix_appointment_patient_context_id', table_name='appointment')
    op.drop_index('ix_appointment_scheduled_date', table_name='appointment')
    op.drop_table('appointment')
