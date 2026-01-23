"""Add evidence layers (4-5-6) tables

Revision ID: e1v2i3d4e5n6
Revises: p1c2t3x4t5m6
Create Date: 2026-01-22

This migration adds the 6-layer architecture tables:
1. raw_data (Layer 6) - Actual raw content from source systems
2. source_document (Layer 5) - Catalog of documents/transactions
3. evidence (Layer 4) - Extracted facts that inform probability calculations
4. Updates plan_step with rationale and evidence_ids columns
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e1v2i3d4e5n6'
down_revision = 'o1v2e3r4r5i6d7e'  # Previous: add_override_color_to_patient_context
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get connection and inspector for checking existing columns/tables
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # =========================================================================
    # Layer 6: raw_data table
    # =========================================================================
    if 'raw_data' not in existing_tables:
        op.create_table(
            'raw_data',
            sa.Column('raw_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('tenant.tenant_id'), nullable=False),
            sa.Column('content_type', sa.String(50), nullable=False),
            sa.Column('raw_content', postgresql.JSONB(), nullable=True),
            sa.Column('file_reference', sa.String(500), nullable=True),
            sa.Column('source_system', sa.String(100), nullable=False),
            sa.Column('collected_at', sa.DateTime(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        print("  [created] raw_data table (Layer 6)")
    else:
        print("  [skip] raw_data table already exists")
    
    # =========================================================================
    # Layer 5: source_document table
    # =========================================================================
    if 'source_document' not in existing_tables:
        op.create_table(
            'source_document',
            sa.Column('source_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('tenant.tenant_id'), nullable=False),
            sa.Column('raw_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('raw_data.raw_id'), nullable=True),
            sa.Column('document_type', sa.String(50), nullable=False),
            sa.Column('document_label', sa.String(255), nullable=False),
            sa.Column('source_system', sa.String(100), nullable=False),
            sa.Column('transaction_id', sa.String(255), nullable=True),
            sa.Column('document_date', sa.DateTime(), nullable=False),
            sa.Column('trust_score', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        # Add index for document lookups
        op.create_index('idx_source_document_tenant', 'source_document', ['tenant_id'])
        op.create_index('idx_source_document_type', 'source_document', ['document_type'])
        print("  [created] source_document table (Layer 5)")
    else:
        print("  [skip] source_document table already exists")
    
    # =========================================================================
    # Layer 4: evidence table
    # =========================================================================
    if 'evidence' not in existing_tables:
        op.create_table(
            'evidence',
            sa.Column('evidence_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('patient_context_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('patient_context.patient_context_id'), nullable=False),
            sa.Column('source_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('source_document.source_id'), nullable=True),
            sa.Column('factor_type', sa.String(20), nullable=False),
            sa.Column('fact_type', sa.String(50), nullable=False),
            sa.Column('fact_summary', sa.String(500), nullable=False),
            sa.Column('fact_data', postgresql.JSONB(), nullable=False),
            sa.Column('is_stale', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('stale_after', sa.DateTime(), nullable=True),
            sa.Column('impact_direction', sa.String(10), nullable=True),
            sa.Column('impact_weight', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        # Add indexes for evidence lookups
        op.create_index('idx_evidence_patient', 'evidence', ['patient_context_id'])
        op.create_index('idx_evidence_factor', 'evidence', ['factor_type'])
        op.create_index('idx_evidence_source', 'evidence', ['source_id'])
        print("  [created] evidence table (Layer 4)")
    else:
        print("  [skip] evidence table already exists")
    
    # =========================================================================
    # Update plan_step with rationale and evidence_ids (Layer 3 enhancement)
    # =========================================================================
    if 'plan_step' in existing_tables:
        existing_columns = [c['name'] for c in inspector.get_columns('plan_step')]
        
        if 'rationale' not in existing_columns:
            op.add_column('plan_step', sa.Column('rationale', sa.Text(), nullable=True))
            print("  [added] plan_step.rationale column")
        else:
            print("  [skip] plan_step.rationale already exists")
        
        if 'evidence_ids' not in existing_columns:
            op.add_column('plan_step', sa.Column('evidence_ids', postgresql.JSONB(), nullable=True))
            print("  [added] plan_step.evidence_ids column")
        else:
            print("  [skip] plan_step.evidence_ids already exists")
    
    # Refresh existing_tables after potential changes
    existing_tables = inspector.get_table_names()
    
    # =========================================================================
    # Join Table: fact_source_link (many-to-many: Evidence <-> SourceDocument)
    # =========================================================================
    if 'fact_source_link' not in existing_tables:
        op.create_table(
            'fact_source_link',
            sa.Column('link_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('fact_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('evidence.evidence_id'), nullable=False),
            sa.Column('source_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('source_document.source_id'), nullable=False),
            sa.Column('role', sa.String(50), nullable=False, server_default='primary'),
            sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('idx_fact_source_link_fact', 'fact_source_link', ['fact_id'])
        op.create_index('idx_fact_source_link_source', 'fact_source_link', ['source_id'])
        print("  [created] fact_source_link join table")
    else:
        print("  [skip] fact_source_link table already exists")
    
    # =========================================================================
    # Join Table: plan_step_fact_link (many-to-many: PlanStep <-> Evidence)
    # =========================================================================
    if 'plan_step_fact_link' not in existing_tables:
        op.create_table(
            'plan_step_fact_link',
            sa.Column('link_id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('plan_step_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('plan_step.step_id'), nullable=False),
            sa.Column('fact_id', postgresql.UUID(as_uuid=True), 
                      sa.ForeignKey('evidence.evidence_id'), nullable=False),
            sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('idx_plan_step_fact_link_step', 'plan_step_fact_link', ['plan_step_id'])
        op.create_index('idx_plan_step_fact_link_fact', 'plan_step_fact_link', ['fact_id'])
        print("  [created] plan_step_fact_link join table")
    else:
        print("  [skip] plan_step_fact_link table already exists")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    
    # Drop join tables first (they reference evidence)
    if 'plan_step_fact_link' in existing_tables:
        op.drop_index('idx_plan_step_fact_link_fact', 'plan_step_fact_link')
        op.drop_index('idx_plan_step_fact_link_step', 'plan_step_fact_link')
        op.drop_table('plan_step_fact_link')
    
    if 'fact_source_link' in existing_tables:
        op.drop_index('idx_fact_source_link_source', 'fact_source_link')
        op.drop_index('idx_fact_source_link_fact', 'fact_source_link')
        op.drop_table('fact_source_link')
    
    # Remove columns from plan_step
    if 'plan_step' in existing_tables:
        existing_columns = [c['name'] for c in inspector.get_columns('plan_step')]
        if 'evidence_ids' in existing_columns:
            op.drop_column('plan_step', 'evidence_ids')
        if 'rationale' in existing_columns:
            op.drop_column('plan_step', 'rationale')
    
    # Drop tables in reverse order (respecting foreign keys)
    if 'evidence' in existing_tables:
        op.drop_index('idx_evidence_source', 'evidence')
        op.drop_index('idx_evidence_factor', 'evidence')
        op.drop_index('idx_evidence_patient', 'evidence')
        op.drop_table('evidence')
    
    if 'source_document' in existing_tables:
        op.drop_index('idx_source_document_type', 'source_document')
        op.drop_index('idx_source_document_tenant', 'source_document')
        op.drop_table('source_document')
    
    if 'raw_data' in existing_tables:
        op.drop_table('raw_data')
