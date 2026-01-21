"""
Resolution Plan models for action-centric task management.

These tables support:
1. ResolutionPlan - The plan to resolve a patient's probability gaps
2. PlanStep - Questions/actions in the plan (with branching support)
3. StepAnswer - User answers to steps
4. PlanNote - Team notes and context
5. PlanModification - Audit log of plan changes

Storage strategy:
- PostgreSQL: Normalized tables (source of truth)
- Firestore: Denormalized projection for real-time UI
- BigQuery: Future analytics (ETL from PostgreSQL)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, Text, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


# =============================================================================
# Enums (as string constants for flexibility)
# =============================================================================

class PlanStatus:
    """Resolution plan status values."""
    DRAFT = "draft"
    ACTIVE = "active"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"


class StepStatus:
    """Plan step status values."""
    PENDING = "pending"       # Not yet addressed
    CURRENT = "current"       # Currently being worked on
    ANSWERED = "answered"     # User provided an answer, but not resolved
    RESOLVED = "resolved"     # Batch job or user confirmed resolution
    SKIPPED = "skipped"       # Intentionally skipped
    # Legacy - keep for backward compatibility
    COMPLETED = "resolved"    # Alias for resolved


class StepType:
    """Plan step type values."""
    QUESTION = "question"           # Yes/No or multiple choice
    FORM = "form"                   # Input fields (payer, policy, etc.)
    CONFIRMATION = "confirmation"   # System suggestion to confirm
    ACTION = "action"               # Action button (submit, send, etc.)
    BRANCH = "branch"               # Multiple path options


class InputType:
    """Input type for step rendering."""
    SINGLE_CHOICE = "single_choice"     # Radio buttons / button group
    MULTI_CHOICE = "multi_choice"       # Checkboxes
    FORM = "form"                       # Input fields
    CONFIRMATION = "confirmation"       # Confirm/Edit/Incorrect
    BRANCH_CHOICE = "branch_choice"     # Path selection cards


class FactorType:
    """Probability factor types."""
    ELIGIBILITY = "eligibility"
    COVERAGE = "coverage"
    ATTENDANCE = "attendance"
    ERRORS = "errors"


class AnswerMode:
    """How the answer was provided."""
    AGENTIC = "agentic"         # System auto-answered
    COPILOT = "copilot"         # System suggested, user confirmed
    USER_DRIVEN = "user_driven"  # User provided manually


# =============================================================================
# Resolution Plan Models
# =============================================================================

class ResolutionPlan(Base):
    """
    The plan to resolve a patient's probability gaps.
    
    Created by batch job when probability issues are detected.
    Contains steps (questions/actions) to resolve the gaps.
    """
    
    __tablename__ = "resolution_plan"
    
    plan_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Gap identification
    gap_types = Column(JSONB, nullable=False)  # ["eligibility", "coverage"]
    
    # Plan status
    status = Column(String(20), default=PlanStatus.ACTIVE, nullable=False)
    current_step_id = Column(UUID(as_uuid=True), nullable=True)  # FK added after PlanStep defined
    
    # Probability tracking (internal, not shown to users)
    initial_probability = Column(Float, nullable=True)
    current_probability = Column(Float, nullable=True)
    target_probability = Column(Float, default=0.85, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Resolution details
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)
    resolution_type = Column(String(50), nullable=True)  # "verified", "self_pay", "cancelled", etc.
    resolution_notes = Column(Text, nullable=True)
    
    # Escalation details
    escalated_at = Column(DateTime, nullable=True)
    escalated_to = Column(UUID(as_uuid=True), ForeignKey("app_user.user_id"), nullable=True)
    escalation_reason = Column(Text, nullable=True)
    
    # Batch job metadata
    batch_job_id = Column(String(100), nullable=True)
    
    # Relationships
    patient_context = relationship("PatientContext")
    tenant = relationship("Tenant")
    steps = relationship("PlanStep", back_populates="plan", order_by="PlanStep.step_order")
    notes = relationship("PlanNote", back_populates="plan", order_by="PlanNote.created_at.desc()")
    modifications = relationship("PlanModification", back_populates="plan", order_by="PlanModification.created_at.desc()")
    resolved_by_user = relationship("AppUser", foreign_keys=[resolved_by])
    escalated_to_user = relationship("AppUser", foreign_keys=[escalated_to])
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "plan_id": str(self.plan_id),
            "patient_context_id": str(self.patient_context_id),
            "gap_types": self.gap_types,
            "status": self.status,
            "current_step_id": str(self.current_step_id) if self.current_step_id else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_type": self.resolution_type,
        }
    
    def get_progress(self) -> dict:
        """Get progress counts by factor type."""
        progress = {}
        for step in self.steps:
            factor = step.factor_type or "general"
            if factor not in progress:
                progress[factor] = {"done": 0, "total": 0}
            progress[factor]["total"] += 1
            if step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
                progress[factor]["done"] += 1
        return progress


class PlanStep(Base):
    """
    A question or action in a resolution plan.
    
    References TaskTemplate for master contract consistency.
    Supports branching via parent_step_id.
    """
    
    __tablename__ = "plan_step"
    
    step_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resolution_plan.plan_id"),
        nullable=False
    )
    
    # Link to master template (contract between batch and UI)
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_template.template_id"),
        nullable=True  # Can be null for custom/ad-hoc steps
    )
    
    # Step identification
    step_order = Column(Integer, nullable=False)
    step_code = Column(String(50), nullable=False)  # "has_insurance", "verify_active"
    
    # Step type and rendering
    step_type = Column(String(20), default=StepType.QUESTION, nullable=False)
    input_type = Column(String(20), default=InputType.SINGLE_CHOICE, nullable=False)
    
    # Content
    question_text = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    
    # Answer options with branching
    # Format: [{"code": "yes", "label": "Yes", "next_step_code": "collect_payer"},
    #          {"code": "no", "label": "No", "next_step_code": "self_pay_path"}]
    answer_options = Column(JSONB, nullable=True)
    
    # Form fields (for input_type = form)
    # Format: [{"field": "payer_name", "label": "Payer", "type": "text", "required": true}]
    form_fields = Column(JSONB, nullable=True)
    
    # System capability
    can_system_answer = Column(Boolean, default=False, nullable=False)
    system_suggestion = Column(JSONB, nullable=True)  # {"answer": "yes", "source": "portal_upload", "confidence": 0.9}
    
    # Assignment
    assignable_activities = Column(JSONB, nullable=True)  # ["verify_eligibility", "check_in_patients"]
    assigned_to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=True
    )
    
    # Status
    status = Column(String(20), default=StepStatus.PENDING, nullable=False)
    
    # Factor type (for grouping in UI)
    factor_type = Column(String(20), nullable=True)  # "eligibility", "coverage", "attendance"
    
    # Branching support
    parent_step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=True
    )
    is_branch = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    answered_at = Column(DateTime, nullable=True)   # When user provided answer
    resolved_at = Column(DateTime, nullable=True)   # When batch/user confirmed resolution
    completed_at = Column(DateTime, nullable=True)  # Legacy - alias for resolved_at
    
    # Relationships
    plan = relationship("ResolutionPlan", back_populates="steps")
    template = relationship("TaskTemplate")
    assigned_to = relationship("AppUser")
    parent_step = relationship("PlanStep", remote_side=[step_id])
    answers = relationship("StepAnswer", back_populates="step", order_by="StepAnswer.created_at.desc()")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "step_id": str(self.step_id),
            "step_code": self.step_code,
            "step_type": self.step_type,
            "input_type": self.input_type,
            "question_text": self.question_text,
            "description": self.description,
            "answer_options": self.answer_options,
            "form_fields": self.form_fields,
            "can_system_answer": self.can_system_answer,
            "system_suggestion": self.system_suggestion,
            "assignable_activities": self.assignable_activities,
            "assigned_to_user_id": str(self.assigned_to_user_id) if self.assigned_to_user_id else None,
            "status": self.status,
            "factor_type": self.factor_type,
            "is_branch": self.is_branch,
        }


class StepAnswer(Base):
    """
    User's answer to a plan step.
    
    Records who answered, how (agentic/copilot/user), and what they answered.
    """
    
    __tablename__ = "step_answer"
    
    answer_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=False
    )
    
    # Answer content
    answer_code = Column(String(50), nullable=False)  # "yes", "no", "approved", etc.
    answer_details = Column(JSONB, nullable=True)  # For form data: {"payer": "BlueCross", "policy": "BCB123"}
    
    # Who and how
    answered_by = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=True  # Null if system answered
    )
    answer_mode = Column(String(20), default=AnswerMode.USER_DRIVEN, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    step = relationship("PlanStep", back_populates="answers")
    answered_by_user = relationship("AppUser")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "answer_id": str(self.answer_id),
            "step_id": str(self.step_id),
            "answer_code": self.answer_code,
            "answer_details": self.answer_details,
            "answered_by": str(self.answered_by) if self.answered_by else None,
            "answer_mode": self.answer_mode,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PlanNote(Base):
    """
    Team notes and context for a resolution plan.
    
    For the Notes tab - freeform context capture.
    """
    
    __tablename__ = "plan_note"
    
    note_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resolution_plan.plan_id"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=False
    )
    
    # Note content
    note_text = Column(Text, nullable=False)
    related_factor = Column(String(20), nullable=True)  # "eligibility", "coverage", etc.
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    plan = relationship("ResolutionPlan", back_populates="notes")
    user = relationship("AppUser")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "note_id": str(self.note_id),
            "user_id": str(self.user_id),
            "user_name": self.user.display_name if self.user else None,
            "note_text": self.note_text,
            "related_factor": self.related_factor,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PlanModification(Base):
    """
    Audit log of plan modifications.
    
    Tracks add step, skip step, reassign, resolve, escalate, etc.
    """
    
    __tablename__ = "plan_modification"
    
    modification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resolution_plan.plan_id"),
        nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=False
    )
    
    # Modification details
    action = Column(String(50), nullable=False)  # "add_step", "skip_step", "reassign", "resolve", "escalate"
    details = Column(JSONB, nullable=True)  # Action-specific details
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    plan = relationship("ResolutionPlan", back_populates="modifications")
    user = relationship("AppUser")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "modification_id": str(self.modification_id),
            "user_id": str(self.user_id),
            "user_name": self.user.display_name if self.user else None,
            "action": self.action,
            "details": self.details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
