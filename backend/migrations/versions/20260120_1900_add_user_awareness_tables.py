"""Add user awareness tables and fields.

Creates:
- auth_provider_link: Links external auth providers to Mobius accounts
- user_session: Active user sessions for token management
- activity: Reference data for user activities
- user_activity: Many-to-many link between users and activities

Extends:
- app_user: Add name, timezone, onboarding fields
- user_preference: Add tone, AI comfort level, autonomy preferences

Revision ID: a1b2c3d4e5f6
Revises: (depends on latest migration)
Create Date: 2026-01-20 19:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'h1i2j3k4l5m6'
down_revision = 'g2h3i4j5k6l7'  # Previous: add_orders_billing_messages
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # ==========================================================================
    # 1. Create auth_provider_link table
    # ==========================================================================
    if 'auth_provider_link' not in existing_tables:
        op.create_table(
            'auth_provider_link',
            sa.Column('link_id', postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('app_user.user_id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(50), nullable=False),  # 'email', 'google', 'microsoft', 'okta'
            sa.Column('provider_user_id', sa.String(255), nullable=True),  # External ID from provider
            sa.Column('email', sa.String(255), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('provider', 'provider_user_id', name='uq_auth_provider_link_provider_user'),
        )
        op.create_index('ix_auth_provider_link_user_id', 'auth_provider_link', ['user_id'])
        op.create_index('ix_auth_provider_link_email', 'auth_provider_link', ['email'])

    # ==========================================================================
    # 2. Create user_session table
    # ==========================================================================
    if 'user_session' not in existing_tables:
        op.create_table(
            'user_session',
            sa.Column('session_id', postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('user_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('app_user.user_id', ondelete='CASCADE'), nullable=False),
            sa.Column('refresh_token_hash', sa.String(255), nullable=True),
            sa.Column('device_info', postgresql.JSONB, nullable=True),  # Browser, OS info
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_user_session_user_id', 'user_session', ['user_id'])
        op.create_index('ix_user_session_expires_at', 'user_session', ['expires_at'])

    # ==========================================================================
    # 3. Create activity table (reference data)
    # ==========================================================================
    if 'activity' not in existing_tables:
        op.create_table(
            'activity',
            sa.Column('activity_id', postgresql.UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text('gen_random_uuid()')),
            sa.Column('activity_code', sa.String(50), unique=True, nullable=False),
            sa.Column('label', sa.String(100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('quick_actions', postgresql.JSONB, nullable=True),  # Available quick actions
            sa.Column('relevant_data_fields', postgresql.JSONB, nullable=True),  # Data fields to prioritize
            sa.Column('display_order', sa.Integer(), default=0, nullable=False),
            sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        )

    # ==========================================================================
    # 4. Create user_activity table (many-to-many)
    # ==========================================================================
    if 'user_activity' not in existing_tables:
        op.create_table(
            'user_activity',
            sa.Column('user_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('app_user.user_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('activity_id', postgresql.UUID(as_uuid=True),
                      sa.ForeignKey('activity.activity_id', ondelete='CASCADE'), primary_key=True),
            sa.Column('is_primary', sa.Boolean(), default=False, nullable=False),
            sa.Column('added_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=False),
        )
        op.create_index('ix_user_activity_user_id', 'user_activity', ['user_id'])

    # ==========================================================================
    # 5. Extend app_user table
    # ==========================================================================
    # Add new columns for user awareness (check if exists first)
    app_user_columns = [c['name'] for c in inspector.get_columns('app_user')]
    
    if 'password_hash' not in app_user_columns:
        op.add_column('app_user', sa.Column('password_hash', sa.String(255), nullable=True))
    if 'first_name' not in app_user_columns:
        op.add_column('app_user', sa.Column('first_name', sa.String(100), nullable=True))
    if 'preferred_name' not in app_user_columns:
        op.add_column('app_user', sa.Column('preferred_name', sa.String(100), nullable=True))
    if 'timezone' not in app_user_columns:
        op.add_column('app_user', sa.Column('timezone', sa.String(50), server_default='America/New_York', nullable=True))
    if 'locale' not in app_user_columns:
        op.add_column('app_user', sa.Column('locale', sa.String(10), server_default='en-US', nullable=True))
    if 'onboarding_completed_at' not in app_user_columns:
        op.add_column('app_user', sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True))
    if 'avatar_url' not in app_user_columns:
        op.add_column('app_user', sa.Column('avatar_url', sa.String(500), nullable=True))

    # ==========================================================================
    # 6. Extend user_preference table
    # ==========================================================================
    # Add new columns for personalization preferences (check if exists first)
    user_pref_columns = [c['name'] for c in inspector.get_columns('user_preference')]
    
    if 'tone' not in user_pref_columns:
        op.add_column('user_preference', sa.Column('tone', sa.String(20), server_default='professional', nullable=True))
    if 'greeting_enabled' not in user_pref_columns:
        op.add_column('user_preference', sa.Column('greeting_enabled', sa.Boolean(), server_default='true', nullable=False))
    if 'ai_experience_level' not in user_pref_columns:
        op.add_column('user_preference', sa.Column('ai_experience_level', sa.String(20), server_default='beginner', nullable=True))
    if 'autonomy_routine_tasks' not in user_pref_columns:
        op.add_column('user_preference', sa.Column('autonomy_routine_tasks', sa.String(20), server_default='confirm_first', nullable=True))
    if 'autonomy_sensitive_tasks' not in user_pref_columns:
        op.add_column('user_preference', sa.Column('autonomy_sensitive_tasks', sa.String(20), server_default='confirm_first', nullable=True))
    if 'display_preferences_json' not in user_pref_columns:
        op.add_column('user_preference', sa.Column('display_preferences_json', postgresql.JSONB, nullable=True))

    # ==========================================================================
    # 7. Seed default activities (only if table was just created or is empty)
    # ==========================================================================
    if 'activity' not in existing_tables:
        op.execute("""
            INSERT INTO activity (activity_id, activity_code, label, description, quick_actions, relevant_data_fields, display_order, is_active)
            VALUES 
        (gen_random_uuid(), 'schedule_appointments', 'Schedule appointments', 
         'Scheduling and managing patient appointments',
         '["find_available_slot", "reschedule", "cancel_appointment"]'::jsonb,
         '["appointment_status", "provider_availability"]'::jsonb, 1, true),
        
        (gen_random_uuid(), 'check_in_patients', 'Check in patients',
         'Patient check-in and arrival processing',
         '["verify_demographics", "collect_copay", "update_insurance"]'::jsonb,
         '["arrival_status", "copay_amount", "insurance_on_file"]'::jsonb, 2, true),
        
        (gen_random_uuid(), 'verify_eligibility', 'Verify eligibility',
         'Insurance eligibility verification',
         '["run_eligibility_check", "update_coverage", "flag_issue"]'::jsonb,
         '["eligibility_status", "coverage_dates", "benefit_details"]'::jsonb, 3, true),
        
        (gen_random_uuid(), 'submit_claims', 'Submit claims',
         'Medical claims submission and tracking',
         '["submit_claim", "check_status", "view_remittance"]'::jsonb,
         '["claim_status", "billing_codes", "expected_payment"]'::jsonb, 4, true),
        
        (gen_random_uuid(), 'rework_denials', 'Rework denied claims',
         'Handling claim denials and appeals',
         '["view_denial_reason", "appeal_claim", "correct_and_resubmit"]'::jsonb,
         '["denial_code", "appeal_deadline", "correction_needed"]'::jsonb, 5, true),
        
        (gen_random_uuid(), 'prior_authorization', 'Handle prior authorizations',
         'Prior authorization requests and tracking',
         '["submit_auth_request", "check_auth_status", "upload_clinical"]'::jsonb,
         '["auth_status", "auth_number", "expiration_date"]'::jsonb, 6, true),
        
        (gen_random_uuid(), 'patient_outreach', 'Patient outreach',
         'Patient communication and follow-up',
         '["send_reminder", "log_call", "schedule_callback"]'::jsonb,
         '["contact_history", "preferred_contact", "callback_notes"]'::jsonb, 7, true),
        
        (gen_random_uuid(), 'document_notes', 'Document clinical notes',
         'Clinical documentation and notes',
         '["add_note", "view_history", "flag_for_review"]'::jsonb,
         '["note_status", "last_updated", "provider_signature"]'::jsonb, 8, true),
        
        (gen_random_uuid(), 'coordinate_referrals', 'Coordinate referrals',
         'Managing patient referrals to specialists',
         '["create_referral", "check_referral_status", "upload_documents"]'::jsonb,
         '["referral_status", "specialist_info", "appointment_date"]'::jsonb, 9, true)
    """)


def downgrade() -> None:
    # Remove extended columns from user_preference
    op.drop_column('user_preference', 'display_preferences_json')
    op.drop_column('user_preference', 'autonomy_sensitive_tasks')
    op.drop_column('user_preference', 'autonomy_routine_tasks')
    op.drop_column('user_preference', 'ai_experience_level')
    op.drop_column('user_preference', 'greeting_enabled')
    op.drop_column('user_preference', 'tone')

    # Remove extended columns from app_user
    op.drop_column('app_user', 'avatar_url')
    op.drop_column('app_user', 'onboarding_completed_at')
    op.drop_column('app_user', 'locale')
    op.drop_column('app_user', 'timezone')
    op.drop_column('app_user', 'preferred_name')
    op.drop_column('app_user', 'first_name')
    op.drop_column('app_user', 'password_hash')

    # Drop tables in reverse order
    op.drop_table('user_activity')
    op.drop_table('activity')
    op.drop_table('user_session')
    op.drop_table('auth_provider_link')
