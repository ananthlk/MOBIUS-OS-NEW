"""
Payment probability and task models for decision agents.

These tables support:
1. Payment probability tracking (for ProceedDecisionAgent)
2. Task templates with sub-steps (for TaskingDecisionAgent)
3. Task instances with step progress (for ExecutionModeAgent)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Boolean, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class PaymentProbability(Base):
    """
    Payment probability assessment for a patient context.
    
    Populated by batch job. Used by ProceedDecisionAgent to determine
    color (GREEN >= 85%, YELLOW 60-84%, RED < 60%).
    """
    
    __tablename__ = "payment_probability"
    
    probability_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_context_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("patient_context.patient_context_id"), 
        nullable=False
    )
    
    # Target date for payment assessment
    target_date = Column(Date, nullable=False)
    
    # Overall probability (0.0 - 1.0)
    overall_probability = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)  # How confident we are in this estimate
    
    # Micro-probabilities (0.0 - 1.0)
    prob_appointment_attendance = Column(Float, nullable=True)  # Will patient show up?
    prob_eligibility = Column(Float, nullable=True)             # Funding source aligned?
    prob_coverage = Column(Float, nullable=True)                # Service reimbursable?
    prob_no_errors = Column(Float, nullable=True)               # No payor/provider errors?
    
    # Lowest factor (for actionable summary)
    lowest_factor = Column(String(50), nullable=True)    # "eligibility", "coverage", "attendance", "errors"
    lowest_factor_reason = Column(Text, nullable=True)   # Human-readable reason
    
    # LLM-generated problem statement (for "Needs Attention" display)
    # Format: "Action - Reason" e.g., "Confirm Medicaid eligibility - prior insurance expired"
    problem_statement = Column(String(255), nullable=True)
    
    # Ordered list of issues with context (for multiple problems)
    # Example: [{"issue": "eligibility", "action": "Confirm eligibility", "reason": "expired", "severity": "high"}]
    problem_details = Column(JSONB, nullable=True)
    
    # Batch job metadata
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    batch_job_id = Column(String(100), nullable=True)
    
    # Relationship
    patient_context = relationship("PatientContext")


class TaskTemplate(Base):
    """
    Admin-defined reusable task definition.
    
    Examples: "Verify Insurance Eligibility", "Obtain Prior Authorization"
    A template can have multiple TaskSteps for sub-tasks.
    """
    
    __tablename__ = "task_template"
    
    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenant.tenant_id"), 
        nullable=False
    )
    
    # Task definition
    task_code = Column(String(50), unique=True, nullable=False)  # "verify_eligibility"
    task_name = Column(String(255), nullable=False)              # "Verify Insurance Eligibility"
    task_description = Column(Text, nullable=True)
    
    # Who can do this (multiple allowed)
    assignable_to = Column(JSONB, nullable=True)      # ["user", "system", "patient", "role"]
    assignable_roles = Column(JSONB, nullable=True)   # ["billing_specialist"] if "role" in assignable_to
    
    # System capability
    can_system_execute = Column(Boolean, default=False, nullable=False)
    requires_human_in_loop = Column(Boolean, default=False, nullable=False)
    
    # Success tracking (configurable threshold per task)
    success_rate_threshold = Column(Float, default=0.8, nullable=False)  # Below this = COPILOT
    historical_success_rate = Column(Float, nullable=True)
    
    # Value and impact
    value_tier = Column(String(20), nullable=True)        # "high", "medium", "low"
    expected_probability_lift = Column(Float, nullable=True)  # How much this improves payment odds
    
    # Task-level oversight requirement
    always_requires_oversight = Column(Boolean, default=False, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    tenant = relationship("Tenant")
    steps = relationship("TaskStep", back_populates="template", order_by="TaskStep.step_order")
    instances = relationship("TaskInstance", back_populates="template")


class TaskStep(Base):
    """
    Sub-task/step within a TaskTemplate.
    
    Example: "Check Eligibility" might have 10 steps:
    1. Retrieve patient demographics
    2. Query insurance database
    3. Verify coverage dates
    ...etc
    """
    
    __tablename__ = "task_step"
    
    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("task_template.template_id"), 
        nullable=False
    )
    
    step_order = Column(Integer, nullable=False)  # 1, 2, 3...
    step_code = Column(String(50), nullable=False)
    step_name = Column(String(255), nullable=False)
    step_description = Column(Text, nullable=True)
    
    # Step-specific attributes
    can_system_execute = Column(Boolean, default=False, nullable=False)
    requires_human_in_loop = Column(Boolean, default=False, nullable=False)
    is_optional = Column(Boolean, default=False, nullable=False)
    
    # Dependency (which step must complete before this one)
    depends_on_step_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("task_step.step_id"), 
        nullable=True
    )
    
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    template = relationship("TaskTemplate", back_populates="steps")
    depends_on = relationship("TaskStep", remote_side=[step_id])


class TaskInstance(Base):
    """
    Patient-specific task assignment.
    
    Created when a task needs to be done for a specific patient.
    Populated by batch job or triggered by events.
    """
    
    __tablename__ = "task_instance"
    
    instance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("task_template.template_id"), 
        nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("patient_context.patient_context_id"), 
        nullable=True  # Can be null for non-patient tasks
    )
    
    # Assignment
    assigned_to_type = Column(String(50), nullable=True)   # "user", "system", "patient", "role"
    assigned_to_id = Column(UUID(as_uuid=True), nullable=True)  # user_id if assigned to specific user
    assigned_role = Column(String(100), nullable=True)     # If assigned to role
    
    # Status
    status = Column(String(20), default="pending", nullable=False)  # "pending", "in_progress", "completed", "cancelled"
    priority = Column(Integer, default=3, nullable=False)  # 1=highest, 5=lowest
    
    # Context
    reason = Column(Text, nullable=True)              # Why this task was created
    expected_impact = Column(Float, nullable=True)    # Estimated probability improvement
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Batch job metadata
    batch_job_id = Column(String(100), nullable=True)
    
    # Relationships
    template = relationship("TaskTemplate", back_populates="instances")
    patient_context = relationship("PatientContext")
    step_instances = relationship("StepInstance", back_populates="task_instance")


class StepInstance(Base):
    """
    Track progress on individual steps within a TaskInstance.
    
    Each TaskInstance can have multiple StepInstances corresponding
    to the TaskSteps defined in its template.
    """
    
    __tablename__ = "step_instance"
    
    step_instance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_instance_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("task_instance.instance_id"), 
        nullable=False
    )
    step_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("task_step.step_id"), 
        nullable=False
    )
    
    # Status
    status = Column(String(20), default="pending", nullable=False)  # "pending", "in_progress", "completed", "skipped", "failed"
    
    # Execution details
    executed_by = Column(String(50), nullable=True)      # "system", "user", "patient"
    executed_by_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Result
    result_data = Column(JSONB, nullable=True)  # Step output/result
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    task_instance = relationship("TaskInstance", back_populates="step_instances")
    step = relationship("TaskStep")


class UserPreference(Base):
    """
    User-level preferences including oversight settings.
    
    Used by ExecutionModeAgent to determine if user wants
    COPILOT mode even when AGENTIC is possible.
    """
    
    __tablename__ = "user_preference"
    
    preference_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("app_user.user_id"), 
        nullable=False,
        unique=True
    )
    
    # Oversight preference
    always_require_oversight = Column(Boolean, default=False, nullable=False)
    
    # Other preferences can be added here
    notification_preferences = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationship
    user = relationship("AppUser")
