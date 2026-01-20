"""Add orders, billing, and messages tables for unified EMR

Revision ID: g2h3i4j5k6l7
Revises: f1g2h3i4j5k6
Create Date: 2026-01-20 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'g2h3i4j5k6l7'
down_revision = 'f1g2h3i4j5k6'  # Previous: add_scheduling_tables
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # ORDERS TABLES
    # ==========================================================================
    
    # Clinical Order (base order table)
    op.create_table(
        'clinical_order',
        sa.Column('order_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('order_type', sa.String(50), nullable=False),
        sa.Column('order_name', sa.String(255), nullable=False),
        sa.Column('order_code', sa.String(50), nullable=True),
        sa.Column('order_description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('priority', sa.String(20), default='routine', nullable=False),
        sa.Column('ordering_provider_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('provider.provider_id'), nullable=True),
        sa.Column('ordering_provider_name', sa.String(255), nullable=True),
        sa.Column('performing_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('performing_facility', sa.String(255), nullable=True),
        sa.Column('diagnosis_codes', postgresql.JSONB(), nullable=True),
        sa.Column('clinical_notes', sa.Text(), nullable=True),
        sa.Column('scheduled_date', sa.Date(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('result_date', sa.DateTime(), nullable=True),
        sa.Column('result_status', sa.String(50), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('result_details', postgresql.JSONB(), nullable=True),
        sa.Column('ordered_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_clinical_order_tenant_id', 'clinical_order', ['tenant_id'])
    op.create_index('ix_clinical_order_patient_context_id', 'clinical_order', ['patient_context_id'])
    op.create_index('ix_clinical_order_order_type', 'clinical_order', ['order_type'])
    op.create_index('ix_clinical_order_status', 'clinical_order', ['status'])
    op.create_index('ix_clinical_order_ordered_at', 'clinical_order', ['ordered_at'])
    
    # Lab Order
    op.create_table(
        'lab_order',
        sa.Column('lab_order_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinical_order.order_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('specimen_type', sa.String(100), nullable=True),
        sa.Column('collection_method', sa.String(100), nullable=True),
        sa.Column('fasting_required', sa.Boolean(), default=False, nullable=False),
        sa.Column('collected_at', sa.DateTime(), nullable=True),
        sa.Column('collected_by', sa.String(255), nullable=True),
        sa.Column('lab_name', sa.String(255), nullable=True),
        sa.Column('lab_accession', sa.String(100), nullable=True),
        sa.Column('results', postgresql.JSONB(), nullable=True),
        sa.Column('reference_ranges', postgresql.JSONB(), nullable=True),
    )
    op.create_index('ix_lab_order_order_id', 'lab_order', ['order_id'])
    
    # Imaging Order
    op.create_table(
        'imaging_order',
        sa.Column('imaging_order_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinical_order.order_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('modality', sa.String(50), nullable=True),
        sa.Column('body_part', sa.String(100), nullable=True),
        sa.Column('laterality', sa.String(20), nullable=True),
        sa.Column('contrast', sa.Boolean(), default=False, nullable=False),
        sa.Column('contrast_type', sa.String(100), nullable=True),
        sa.Column('appointment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('performed_at', sa.DateTime(), nullable=True),
        sa.Column('radiologist_name', sa.String(255), nullable=True),
        sa.Column('study_accession', sa.String(100), nullable=True),
        sa.Column('report_status', sa.String(50), nullable=True),
        sa.Column('report_text', sa.Text(), nullable=True),
        sa.Column('impression', sa.Text(), nullable=True),
    )
    op.create_index('ix_imaging_order_order_id', 'imaging_order', ['order_id'])
    
    # Medication Order
    op.create_table(
        'medication_order',
        sa.Column('medication_order_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinical_order.order_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('medication_name', sa.String(255), nullable=False),
        sa.Column('generic_name', sa.String(255), nullable=True),
        sa.Column('ndc', sa.String(20), nullable=True),
        sa.Column('rxnorm_code', sa.String(20), nullable=True),
        sa.Column('dose', sa.String(100), nullable=True),
        sa.Column('dose_unit', sa.String(50), nullable=True),
        sa.Column('route', sa.String(50), nullable=True),
        sa.Column('frequency', sa.String(100), nullable=True),
        sa.Column('duration', sa.String(100), nullable=True),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('refills', sa.Integer(), default=0, nullable=False),
        sa.Column('daw', sa.Boolean(), default=False, nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('pharmacy_name', sa.String(255), nullable=True),
        sa.Column('pharmacy_npi', sa.String(20), nullable=True),
        sa.Column('dispense_status', sa.String(50), nullable=True),
        sa.Column('filled_at', sa.DateTime(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
    )
    op.create_index('ix_medication_order_order_id', 'medication_order', ['order_id'])
    
    # Referral Order
    op.create_table(
        'referral_order',
        sa.Column('referral_order_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('order_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clinical_order.order_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('specialty', sa.String(100), nullable=True),
        sa.Column('referred_to_provider', sa.String(255), nullable=True),
        sa.Column('referred_to_facility', sa.String(255), nullable=True),
        sa.Column('referred_to_phone', sa.String(50), nullable=True),
        sa.Column('referred_to_fax', sa.String(50), nullable=True),
        sa.Column('reason_for_referral', sa.Text(), nullable=True),
        sa.Column('clinical_summary', sa.Text(), nullable=True),
        sa.Column('auth_required', sa.Boolean(), default=False, nullable=False),
        sa.Column('auth_number', sa.String(100), nullable=True),
        sa.Column('auth_status', sa.String(50), nullable=True),
        sa.Column('auth_expiry', sa.Date(), nullable=True),
        sa.Column('visits_authorized', sa.Integer(), nullable=True),
        sa.Column('visits_used', sa.Integer(), default=0, nullable=False),
        sa.Column('appointment_date', sa.Date(), nullable=True),
        sa.Column('appointment_notes', sa.Text(), nullable=True),
        sa.Column('consultation_received', sa.Boolean(), default=False, nullable=False),
        sa.Column('consultation_date', sa.Date(), nullable=True),
        sa.Column('consultation_notes', sa.Text(), nullable=True),
    )
    op.create_index('ix_referral_order_order_id', 'referral_order', ['order_id'])
    
    # ==========================================================================
    # BILLING TABLES
    # ==========================================================================
    
    # Patient Insurance
    op.create_table(
        'patient_insurance',
        sa.Column('insurance_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('coverage_type', sa.String(20), nullable=False),
        sa.Column('payer_name', sa.String(255), nullable=False),
        sa.Column('payer_id', sa.String(50), nullable=True),
        sa.Column('payer_phone', sa.String(50), nullable=True),
        sa.Column('payer_address', sa.Text(), nullable=True),
        sa.Column('policy_number', sa.String(100), nullable=True),
        sa.Column('group_number', sa.String(100), nullable=True),
        sa.Column('group_name', sa.String(255), nullable=True),
        sa.Column('subscriber_name', sa.String(255), nullable=True),
        sa.Column('subscriber_dob', sa.Date(), nullable=True),
        sa.Column('subscriber_relationship', sa.String(50), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('termination_date', sa.Date(), nullable=True),
        sa.Column('plan_type', sa.String(50), nullable=True),
        sa.Column('copay_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('deductible', sa.Numeric(10, 2), nullable=True),
        sa.Column('deductible_met', sa.Numeric(10, 2), nullable=True),
        sa.Column('out_of_pocket_max', sa.Numeric(10, 2), nullable=True),
        sa.Column('out_of_pocket_met', sa.Numeric(10, 2), nullable=True),
        sa.Column('verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('verified_by', sa.String(255), nullable=True),
        sa.Column('eligibility_status', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_patient_insurance_tenant_id', 'patient_insurance', ['tenant_id'])
    op.create_index('ix_patient_insurance_patient_context_id', 'patient_insurance', ['patient_context_id'])
    op.create_index('ix_patient_insurance_coverage_type', 'patient_insurance', ['coverage_type'])
    
    # Claim (created before Charge due to FK)
    op.create_table(
        'claim',
        sa.Column('claim_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('claim_number', sa.String(50), nullable=True),
        sa.Column('payer_claim_number', sa.String(100), nullable=True),
        sa.Column('insurance_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_insurance.insurance_id'), nullable=True),
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('service_date_from', sa.Date(), nullable=True),
        sa.Column('service_date_to', sa.Date(), nullable=True),
        sa.Column('diagnosis_codes', postgresql.JSONB(), nullable=True),
        sa.Column('total_charges', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('allowed_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('paid_amount', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('adjustment_amount', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('patient_responsibility', sa.Numeric(10, 2), nullable=True),
        sa.Column('claim_type', sa.String(20), nullable=True),
        sa.Column('claim_frequency', sa.String(10), nullable=True),
        sa.Column('billing_provider_npi', sa.String(20), nullable=True),
        sa.Column('billing_provider_name', sa.String(255), nullable=True),
        sa.Column('rendering_provider_npi', sa.String(20), nullable=True),
        sa.Column('rendering_provider_name', sa.String(255), nullable=True),
        sa.Column('facility_name', sa.String(255), nullable=True),
        sa.Column('place_of_service', sa.String(10), nullable=True),
        sa.Column('status', sa.String(50), default='draft', nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('submission_method', sa.String(50), nullable=True),
        sa.Column('clearinghouse', sa.String(100), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('adjudicated_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('denial_reason', sa.String(500), nullable=True),
        sa.Column('denial_codes', postgresql.JSONB(), nullable=True),
        sa.Column('appeal_deadline', sa.Date(), nullable=True),
        sa.Column('appealed_at', sa.DateTime(), nullable=True),
        sa.Column('appeal_status', sa.String(50), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_claim_tenant_id', 'claim', ['tenant_id'])
    op.create_index('ix_claim_patient_context_id', 'claim', ['patient_context_id'])
    op.create_index('ix_claim_status', 'claim', ['status'])
    op.create_index('ix_claim_submitted_at', 'claim', ['submitted_at'])
    
    # Charge
    op.create_table(
        'charge',
        sa.Column('charge_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('service_date', sa.Date(), nullable=False),
        sa.Column('cpt_code', sa.String(20), nullable=True),
        sa.Column('hcpcs_code', sa.String(20), nullable=True),
        sa.Column('description', sa.String(500), nullable=False),
        sa.Column('modifier_1', sa.String(10), nullable=True),
        sa.Column('modifier_2', sa.String(10), nullable=True),
        sa.Column('modifier_3', sa.String(10), nullable=True),
        sa.Column('modifier_4', sa.String(10), nullable=True),
        sa.Column('diagnosis_pointers', postgresql.JSONB(), nullable=True),
        sa.Column('units', sa.Numeric(10, 2), default=1, nullable=False),
        sa.Column('unit_charge', sa.Numeric(10, 2), nullable=False),
        sa.Column('total_charge', sa.Numeric(10, 2), nullable=False),
        sa.Column('allowed_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('adjustment_amount', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('paid_amount', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('patient_responsibility', sa.Numeric(10, 2), nullable=True),
        sa.Column('balance', sa.Numeric(10, 2), nullable=True),
        sa.Column('rendering_provider_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rendering_provider_name', sa.String(255), nullable=True),
        sa.Column('place_of_service', sa.String(10), nullable=True),
        sa.Column('facility_name', sa.String(255), nullable=True),
        sa.Column('status', sa.String(50), default='pending', nullable=False),
        sa.Column('claim_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('claim.claim_id'), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_charge_tenant_id', 'charge', ['tenant_id'])
    op.create_index('ix_charge_patient_context_id', 'charge', ['patient_context_id'])
    op.create_index('ix_charge_service_date', 'charge', ['service_date'])
    op.create_index('ix_charge_claim_id', 'charge', ['claim_id'])
    
    # Payment
    op.create_table(
        'payment',
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=True),
        sa.Column('payment_source', sa.String(50), nullable=False),
        sa.Column('payer_name', sa.String(255), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=True),
        sa.Column('check_number', sa.String(50), nullable=True),
        sa.Column('reference_number', sa.String(100), nullable=True),
        sa.Column('era_check_number', sa.String(50), nullable=True),
        sa.Column('era_check_date', sa.Date(), nullable=True),
        sa.Column('claim_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('claim.claim_id'), nullable=True),
        sa.Column('status', sa.String(50), default='posted', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=False),
        sa.Column('posted_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_payment_tenant_id', 'payment', ['tenant_id'])
    op.create_index('ix_payment_patient_context_id', 'payment', ['patient_context_id'])
    op.create_index('ix_payment_payment_date', 'payment', ['payment_date'])
    
    # Patient Statement
    op.create_table(
        'patient_statement',
        sa.Column('statement_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('statement_number', sa.String(50), nullable=True),
        sa.Column('statement_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('previous_balance', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('new_charges', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('payments_received', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('adjustments', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('balance_due', sa.Numeric(10, 2), nullable=False),
        sa.Column('current', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('days_30', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('days_60', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('days_90', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('days_120_plus', sa.Numeric(10, 2), default=0, nullable=False),
        sa.Column('delivery_method', sa.String(50), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(50), default='generated', nullable=False),
        sa.Column('custom_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_patient_statement_tenant_id', 'patient_statement', ['tenant_id'])
    op.create_index('ix_patient_statement_patient_context_id', 'patient_statement', ['patient_context_id'])
    
    # ==========================================================================
    # MESSAGING TABLES
    # ==========================================================================
    
    # Message Thread
    op.create_table(
        'message_thread',
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=True),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('category', sa.String(50), default='general', nullable=False),
        sa.Column('thread_type', sa.String(50), default='internal', nullable=False),
        sa.Column('priority', sa.String(20), default='normal', nullable=False),
        sa.Column('status', sa.String(50), default='open', nullable=False),
        sa.Column('assigned_to_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('assigned_to_name', sa.String(255), nullable=True),
        sa.Column('assigned_pool', sa.String(100), nullable=True),
        sa.Column('message_count', sa.Integer(), default=0, nullable=False),
        sa.Column('unread_count', sa.Integer(), default=0, nullable=False),
        sa.Column('last_message_at', sa.DateTime(), nullable=True),
        sa.Column('last_message_preview', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_message_thread_tenant_id', 'message_thread', ['tenant_id'])
    op.create_index('ix_message_thread_patient_context_id', 'message_thread', ['patient_context_id'])
    op.create_index('ix_message_thread_status', 'message_thread', ['status'])
    op.create_index('ix_message_thread_assigned_pool', 'message_thread', ['assigned_pool'])
    
    # Message
    op.create_table(
        'message',
        sa.Column('message_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('thread_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('message_thread.thread_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('sender_type', sa.String(50), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sender_name', sa.String(255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('reply_to_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('message.message_id'), nullable=True),
        sa.Column('is_read', sa.Boolean(), default=False, nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('has_attachments', sa.Boolean(), default=False, nullable=False),
        sa.Column('attachment_count', sa.Integer(), default=0, nullable=False),
        sa.Column('is_urgent', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_private', sa.Boolean(), default=False, nullable=False),
        sa.Column('requires_response', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_system_message', sa.Boolean(), default=False, nullable=False),
        sa.Column('system_message_type', sa.String(50), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_message_thread_id', 'message', ['thread_id'])
    op.create_index('ix_message_sent_at', 'message', ['sent_at'])
    
    # Message Attachment
    op.create_table(
        'message_attachment',
        sa.Column('attachment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('message.message_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('file_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('storage_path', sa.String(500), nullable=True),
        sa.Column('storage_bucket', sa.String(100), nullable=True),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_message_attachment_message_id', 'message_attachment', ['message_id'])
    
    # Message Recipient
    op.create_table(
        'message_recipient',
        sa.Column('recipient_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('message.message_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('recipient_type', sa.String(50), nullable=False),
        sa.Column('recipient_id_ref', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('recipient_name', sa.String(255), nullable=True),
        sa.Column('recipient_pool', sa.String(100), nullable=True),
        sa.Column('recipient_role', sa.String(20), default='to', nullable=False),
        sa.Column('is_read', sa.Boolean(), default=False, nullable=False),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('folder', sa.String(50), default='inbox', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_message_recipient_message_id', 'message_recipient', ['message_id'])
    op.create_index('ix_message_recipient_recipient_id_ref', 'message_recipient', ['recipient_id_ref'])
    
    # Message Template
    op.create_table(
        'message_template',
        sa.Column('template_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('subject_template', sa.String(500), nullable=True),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('available_variables', postgresql.JSONB(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_system', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.String(255), nullable=True),
    )
    op.create_index('ix_message_template_tenant_id', 'message_template', ['tenant_id'])


def downgrade() -> None:
    # Drop messaging tables
    op.drop_table('message_template')
    op.drop_table('message_recipient')
    op.drop_table('message_attachment')
    op.drop_table('message')
    op.drop_table('message_thread')
    
    # Drop billing tables
    op.drop_table('patient_statement')
    op.drop_table('payment')
    op.drop_table('charge')
    op.drop_table('claim')
    op.drop_table('patient_insurance')
    
    # Drop order tables
    op.drop_table('referral_order')
    op.drop_table('medication_order')
    op.drop_table('imaging_order')
    op.drop_table('lab_order')
    op.drop_table('clinical_order')
