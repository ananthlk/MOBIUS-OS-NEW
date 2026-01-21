"""Add sidecar tables for UI support.

Creates tables for:
- user_alert: Cross-patient notifications for toasts
- user_owned_task: Track "I'll handle this" tasks
- milestone: Care journey progress
- milestone_history: Timeline of actions per milestone

Revision ID: a1b2c3d4e5f6
Revises: 20260121_0200_add_plan_context_to_mini_submission
Create Date: 2026-01-21 03:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '20260121_0200_add_plan_context_to_mini_submission'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # user_alert - Cross-patient notifications
    # ==========================================================================
    op.create_table(
        'user_alert',
        sa.Column('alert_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('app_user.user_id'), nullable=False),
        
        # Alert content
        sa.Column('alert_type', sa.String(20), nullable=False),  # 'win', 'update', 'reminder', 'conflict'
        sa.Column('priority', sa.String(10), server_default='normal', nullable=False),  # 'high', 'normal'
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('subtitle', sa.String(255), nullable=True),
        
        # Patient context (for cross-patient toasts)
        sa.Column('patient_context_id', UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=True),
        sa.Column('patient_name', sa.String(255), nullable=True),
        sa.Column('patient_key', sa.String(100), nullable=True),
        
        # Action
        sa.Column('action_type', sa.String(50), nullable=True),  # 'open_sidecar', 'external'
        sa.Column('action_url', sa.String(500), nullable=True),
        
        # Related entities
        sa.Column('related_plan_id', UUID(as_uuid=True), sa.ForeignKey('resolution_plan.plan_id'), nullable=True),
        sa.Column('related_step_id', UUID(as_uuid=True), sa.ForeignKey('plan_step.step_id'), nullable=True),
        sa.Column('related_milestone_id', UUID(as_uuid=True), nullable=True),  # FK added after milestone table
        
        # State
        sa.Column('read', sa.Boolean, server_default='false', nullable=False),
        sa.Column('dismissed', sa.Boolean, server_default='false', nullable=False),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
        sa.Column('read_at', sa.DateTime, nullable=True),
    )
    
    # Index for fast unread alert queries
    op.create_index(
        'idx_user_alert_user_unread',
        'user_alert',
        ['user_id', 'read'],
        postgresql_where=sa.text('read = false')
    )
    
    op.create_index('idx_user_alert_user_id', 'user_alert', ['user_id'])
    op.create_index('idx_user_alert_patient', 'user_alert', ['patient_context_id'])
    
    # ==========================================================================
    # milestone - Care journey progress
    # ==========================================================================
    op.create_table(
        'milestone',
        sa.Column('milestone_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('patient_context_id', UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        
        # Milestone info
        sa.Column('milestone_type', sa.String(30), nullable=False),  # 'visit', 'eligibility', 'authorization', 'documentation'
        sa.Column('label', sa.String(255), nullable=False),  # "John's insurance verified"
        sa.Column('label_template', sa.String(255), nullable=True),  # "{{possessive}} insurance verified"
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),  # 'complete', 'in_progress', 'blocked', 'pending'
        
        # Completion info
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('completed_by', sa.String(20), nullable=True),  # 'user', 'mobius', 'external'
        sa.Column('completed_by_user_id', UUID(as_uuid=True), sa.ForeignKey('app_user.user_id'), nullable=True),
        
        # Blocking reason (if status = 'blocked')
        sa.Column('blocking_reason', sa.String(500), nullable=True),
        sa.Column('blocking_step_id', UUID(as_uuid=True), sa.ForeignKey('plan_step.step_id'), nullable=True),
        
        # Ordering
        sa.Column('milestone_order', sa.Integer, server_default='0', nullable=False),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
    )
    
    op.create_index('idx_milestone_patient', 'milestone', ['patient_context_id'])
    op.create_index('idx_milestone_tenant', 'milestone', ['tenant_id'])
    op.create_index('idx_milestone_type', 'milestone', ['milestone_type'])
    
    # Now add the FK from user_alert to milestone
    op.create_foreign_key(
        'fk_user_alert_milestone',
        'user_alert',
        'milestone',
        ['related_milestone_id'],
        ['milestone_id']
    )
    
    # ==========================================================================
    # milestone_history - Timeline of actions
    # ==========================================================================
    op.create_table(
        'milestone_history',
        sa.Column('history_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('milestone_id', UUID(as_uuid=True), sa.ForeignKey('milestone.milestone_id'), nullable=False),
        
        # Actor
        sa.Column('actor', sa.String(20), nullable=False),  # 'user', 'mobius', 'payer', 'system'
        sa.Column('actor_name', sa.String(100), nullable=True),
        sa.Column('actor_user_id', UUID(as_uuid=True), sa.ForeignKey('app_user.user_id'), nullable=True),
        
        # Action
        sa.Column('action', sa.String(500), nullable=False),  # "Submitted authorization request"
        sa.Column('action_type', sa.String(50), nullable=True),  # 'submit', 'approve', 'deny', 'verify', 'note'
        
        # Artifact
        sa.Column('artifact_type', sa.String(30), nullable=True),  # 'document', 'confirmation', 'reference'
        sa.Column('artifact_label', sa.String(255), nullable=True),  # "Auth #12345"
        sa.Column('artifact_url', sa.String(500), nullable=True),
        sa.Column('artifact_data', JSONB, nullable=True),  # Additional artifact metadata
        
        # Timestamp
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
    )
    
    op.create_index('idx_milestone_history_milestone', 'milestone_history', ['milestone_id'])
    op.create_index('idx_milestone_history_created', 'milestone_history', ['milestone_id', 'created_at'])
    
    # ==========================================================================
    # user_owned_task - Track "I'll handle this"
    # ==========================================================================
    op.create_table(
        'user_owned_task',
        sa.Column('ownership_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('app_user.user_id'), nullable=False),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenant.tenant_id'), nullable=False),
        
        # What they're owning
        sa.Column('plan_step_id', UUID(as_uuid=True), sa.ForeignKey('plan_step.step_id'), nullable=False),
        sa.Column('plan_id', UUID(as_uuid=True), sa.ForeignKey('resolution_plan.plan_id'), nullable=False),
        sa.Column('patient_context_id', UUID(as_uuid=True), sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        
        # Denormalized for display (avoid joins in hot path)
        sa.Column('question_text', sa.String(500), nullable=True),
        sa.Column('patient_name', sa.String(255), nullable=True),
        sa.Column('patient_key', sa.String(100), nullable=True),
        
        # Status
        sa.Column('status', sa.String(20), server_default='active', nullable=False),  # 'active', 'resolved', 'reminder_sent', 'handed_back'
        
        # Initial note (optional)
        sa.Column('initial_note', sa.Text, nullable=True),
        
        # Batch job monitors these
        sa.Column('resolution_detected_at', sa.DateTime, nullable=True),
        sa.Column('resolution_signal', sa.String(255), nullable=True),  # "Auth approved in payer portal"
        sa.Column('resolution_source', sa.String(50), nullable=True),  # 'batch', 'user', 'system'
        
        # Reminders
        sa.Column('last_reminder_at', sa.DateTime, nullable=True),
        sa.Column('reminder_count', sa.Integer, server_default='0', nullable=False),
        sa.Column('next_reminder_at', sa.DateTime, nullable=True),
        
        # Timestamps
        sa.Column('assigned_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
    )
    
    op.create_index('idx_user_owned_task_user', 'user_owned_task', ['user_id'])
    op.create_index('idx_user_owned_task_patient', 'user_owned_task', ['patient_context_id'])
    op.create_index(
        'idx_user_owned_task_active',
        'user_owned_task',
        ['user_id', 'status'],
        postgresql_where=sa.text("status = 'active'")
    )
    op.create_index('idx_user_owned_task_step', 'user_owned_task', ['plan_step_id'])
    
    # ==========================================================================
    # milestone_substep - Substeps within a milestone
    # ==========================================================================
    op.create_table(
        'milestone_substep',
        sa.Column('substep_id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('milestone_id', UUID(as_uuid=True), sa.ForeignKey('milestone.milestone_id'), nullable=False),
        
        # Substep info
        sa.Column('label', sa.String(255), nullable=False),  # "Verify coverage dates"
        sa.Column('status', sa.String(20), server_default='pending', nullable=False),  # 'complete', 'current', 'pending'
        sa.Column('substep_order', sa.Integer, server_default='0', nullable=False),
        
        # Completion
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('completed_by', sa.String(20), nullable=True),  # 'user', 'mobius'
        sa.Column('completed_by_user_id', UUID(as_uuid=True), sa.ForeignKey('app_user.user_id'), nullable=True),
        
        # Link to plan step (if applicable)
        sa.Column('plan_step_id', UUID(as_uuid=True), sa.ForeignKey('plan_step.step_id'), nullable=True),
        
        sa.Column('created_at', sa.DateTime, server_default=sa.text('NOW()'), nullable=False),
    )
    
    op.create_index('idx_milestone_substep_milestone', 'milestone_substep', ['milestone_id'])


def downgrade() -> None:
    op.drop_table('milestone_substep')
    op.drop_table('user_owned_task')
    op.drop_table('milestone_history')
    op.drop_constraint('fk_user_alert_milestone', 'user_alert', type_='foreignkey')
    op.drop_table('milestone')
    op.drop_table('user_alert')
