"""Add resolution plan tables

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2026-01-21

This migration adds:
1. resolution_plan - The plan to resolve patient probability gaps
2. plan_step - Questions/actions in the plan
3. step_answer - User answers to steps
4. plan_note - Team notes and context
5. plan_modification - Audit log of changes
6. Updates task_template with assignable_activities and factor_type
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'r1e2s3o4l5v6'
down_revision = 'h1i2j3k4l5m6'  # Previous: add_user_awareness_tables
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get connection and inspector for checking existing columns/tables
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Add assignable_activities and factor_type to task_template (if not exists)
    existing_columns = [c['name'] for c in inspector.get_columns('task_template')]
    
    if 'assignable_activities' not in existing_columns:
        op.add_column('task_template', sa.Column('assignable_activities', postgresql.JSONB(), nullable=True))
    
    if 'factor_type' not in existing_columns:
        op.add_column('task_template', sa.Column('factor_type', sa.String(20), nullable=True))
    
    # Check if resolution_plan table already exists
    existing_tables = inspector.get_table_names()
    
    if 'resolution_plan' in existing_tables:
        print("  [skip] resolution_plan table already exists")
        return  # All tables likely exist, skip
    
    # Create resolution_plan table
    op.create_table(
        'resolution_plan',
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('tenant.tenant_id'), nullable=False),
        sa.Column('gap_types', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, default='active'),
        sa.Column('current_step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('initial_probability', sa.Float(), nullable=True),
        sa.Column('current_probability', sa.Float(), nullable=True),
        sa.Column('target_probability', sa.Float(), nullable=True, default=0.85),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id'), nullable=True),
        sa.Column('resolution_type', sa.String(50), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('escalated_to', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id'), nullable=True),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.Column('batch_job_id', sa.String(100), nullable=True),
    )
    op.create_index('ix_resolution_plan_patient_context_id', 'resolution_plan', ['patient_context_id'])
    op.create_index('ix_resolution_plan_tenant_id', 'resolution_plan', ['tenant_id'])
    op.create_index('ix_resolution_plan_status', 'resolution_plan', ['status'])
    
    # Create plan_step table
    op.create_table(
        'plan_step',
        sa.Column('step_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('resolution_plan.plan_id'), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('task_template.template_id'), nullable=True),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('step_code', sa.String(50), nullable=False),
        sa.Column('step_type', sa.String(20), nullable=False, default='question'),
        sa.Column('input_type', sa.String(20), nullable=False, default='single_choice'),
        sa.Column('question_text', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('answer_options', postgresql.JSONB(), nullable=True),
        sa.Column('form_fields', postgresql.JSONB(), nullable=True),
        sa.Column('can_system_answer', sa.Boolean(), nullable=False, default=False),
        sa.Column('system_suggestion', postgresql.JSONB(), nullable=True),
        sa.Column('assignable_activities', postgresql.JSONB(), nullable=True),
        sa.Column('assigned_to_user_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('factor_type', sa.String(20), nullable=True),
        sa.Column('parent_step_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('plan_step.step_id'), nullable=True),
        sa.Column('is_branch', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_plan_step_plan_id', 'plan_step', ['plan_id'])
    op.create_index('ix_plan_step_status', 'plan_step', ['status'])
    op.create_index('ix_plan_step_factor_type', 'plan_step', ['factor_type'])
    
    # Add FK from resolution_plan.current_step_id to plan_step.step_id
    op.create_foreign_key(
        'fk_resolution_plan_current_step',
        'resolution_plan', 'plan_step',
        ['current_step_id'], ['step_id']
    )
    
    # Create step_answer table
    op.create_table(
        'step_answer',
        sa.Column('answer_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('plan_step.step_id'), nullable=False),
        sa.Column('answer_code', sa.String(50), nullable=False),
        sa.Column('answer_details', postgresql.JSONB(), nullable=True),
        sa.Column('answered_by', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id'), nullable=True),
        sa.Column('answer_mode', sa.String(20), nullable=False, default='user_driven'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_step_answer_step_id', 'step_answer', ['step_id'])
    
    # Create plan_note table
    op.create_table(
        'plan_note',
        sa.Column('note_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('resolution_plan.plan_id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id'), nullable=False),
        sa.Column('note_text', sa.Text(), nullable=False),
        sa.Column('related_factor', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_plan_note_plan_id', 'plan_note', ['plan_id'])
    
    # Create plan_modification table
    op.create_table(
        'plan_modification',
        sa.Column('modification_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('plan_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('resolution_plan.plan_id'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('app_user.user_id'), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_plan_modification_plan_id', 'plan_modification', ['plan_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('plan_modification')
    op.drop_table('plan_note')
    op.drop_table('step_answer')
    
    # Drop FK from resolution_plan to plan_step first
    op.drop_constraint('fk_resolution_plan_current_step', 'resolution_plan', type_='foreignkey')
    
    op.drop_table('plan_step')
    op.drop_table('resolution_plan')
    
    # Remove columns from task_template
    op.drop_column('task_template', 'factor_type')
    op.drop_column('task_template', 'assignable_activities')
