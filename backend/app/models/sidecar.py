"""
Sidecar models for UI support.

These tables support:
1. UserAlert - Cross-patient notifications for toasts
2. UserOwnedTask - Track "I'll handle this" tasks
3. Milestone - Care journey progress (visit, eligibility, authorization, documentation)
4. MilestoneHistory - Timeline of actions per milestone
5. MilestoneSubstep - Substeps within a milestone
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


# =============================================================================
# Enums (as string constants)
# =============================================================================

class AlertType:
    """Alert type values."""
    WIN = "win"
    UPDATE = "update"
    REMINDER = "reminder"
    CONFLICT = "conflict"


class AlertPriority:
    """Alert priority values."""
    HIGH = "high"
    NORMAL = "normal"


class MilestoneType:
    """Milestone type values."""
    VISIT = "visit"
    ELIGIBILITY = "eligibility"
    AUTHORIZATION = "authorization"
    DOCUMENTATION = "documentation"


class MilestoneStatus:
    """Milestone status values."""
    COMPLETE = "complete"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    PENDING = "pending"


class SubstepStatus:
    """Substep status values."""
    COMPLETE = "complete"
    CURRENT = "current"
    PENDING = "pending"


class ActorType:
    """Actor type values for history entries."""
    USER = "user"
    MOBIUS = "mobius"
    PAYER = "payer"
    SYSTEM = "system"


class OwnershipStatus:
    """User owned task status values."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    REMINDER_SENT = "reminder_sent"
    HANDED_BACK = "handed_back"


class CompletedBy:
    """Who completed a milestone."""
    USER = "user"
    MOBIUS = "mobius"
    EXTERNAL = "external"


# =============================================================================
# UserAlert Model
# =============================================================================

class UserAlert(Base):
    """
    Cross-patient notifications for toasts and alert badge.
    
    Created by batch job or system events. Displayed as toasts
    in top-right corner of browser, regardless of which patient
    the user is currently viewing.
    """
    
    __tablename__ = "user_alert"
    
    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=False
    )
    
    # Alert content
    alert_type = Column(String(20), nullable=False)  # win, update, reminder, conflict
    priority = Column(String(10), default=AlertPriority.NORMAL, nullable=False)
    title = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True)
    
    # Patient context (for cross-patient toasts)
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=True
    )
    patient_name = Column(String(255), nullable=True)
    patient_key = Column(String(100), nullable=True)
    
    # Action
    action_type = Column(String(50), nullable=True)  # open_sidecar, external
    action_url = Column(String(500), nullable=True)
    
    # Related entities
    related_plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resolution_plan.plan_id"),
        nullable=True
    )
    related_step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=True
    )
    related_milestone_id = Column(
        UUID(as_uuid=True),
        ForeignKey("milestone.milestone_id"),
        nullable=True
    )
    
    # State
    read = Column(Boolean, default=False, nullable=False)
    dismissed = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    read_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("AppUser")
    patient_context = relationship("PatientContext")
    related_plan = relationship("ResolutionPlan")
    related_step = relationship("PlanStep")
    related_milestone = relationship("Milestone")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.alert_id),
            "type": self.alert_type,
            "priority": self.priority,
            "title": self.title,
            "subtitle": self.subtitle,
            "patient_key": self.patient_key,
            "patient_name": self.patient_name,
            "action": {
                "type": self.action_type,
                "url": self.action_url,
            } if self.action_type else None,
            "read": self.read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# Milestone Model
# =============================================================================

class Milestone(Base):
    """
    Care journey progress milestone.
    
    Each patient has 4 milestones:
    - visit: Visit confirmed
    - eligibility: Insurance verified
    - authorization: Service authorization secured
    - documentation: Documentation ready
    """
    
    __tablename__ = "milestone"
    
    milestone_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Milestone info
    milestone_type = Column(String(30), nullable=False)
    label = Column(String(255), nullable=False)
    label_template = Column(String(255), nullable=True)  # "{{possessive}} insurance verified"
    status = Column(String(20), default=MilestoneStatus.PENDING, nullable=False)
    
    # Completion info
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String(20), nullable=True)
    completed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=True
    )
    
    # Blocking info
    blocking_reason = Column(String(500), nullable=True)
    blocking_step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=True
    )
    
    # Ordering
    milestone_order = Column(Integer, default=0, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    patient_context = relationship("PatientContext")
    tenant = relationship("Tenant")
    completed_by_user = relationship("AppUser")
    blocking_step = relationship("PlanStep")
    history = relationship("MilestoneHistory", back_populates="milestone", order_by="MilestoneHistory.created_at.desc()")
    substeps = relationship("MilestoneSubstep", back_populates="milestone", order_by="MilestoneSubstep.substep_order")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.milestone_id),
            "type": self.milestone_type,
            "label": self.label,
            "status": self.status,
            "substeps": [s.to_dict() for s in self.substeps] if self.substeps else [],
            "history": [h.to_dict() for h in self.history[:10]] if self.history else [],  # Limit to 10 most recent
        }


# =============================================================================
# MilestoneHistory Model
# =============================================================================

class MilestoneHistory(Base):
    """
    Timeline of actions for a milestone.
    
    Records who did what, when, and any artifacts produced.
    """
    
    __tablename__ = "milestone_history"
    
    history_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    milestone_id = Column(
        UUID(as_uuid=True),
        ForeignKey("milestone.milestone_id"),
        nullable=False
    )
    
    # Actor
    actor = Column(String(20), nullable=False)  # user, mobius, payer, system
    actor_name = Column(String(100), nullable=True)
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=True
    )
    
    # Action
    action = Column(String(500), nullable=False)
    action_type = Column(String(50), nullable=True)  # submit, approve, deny, verify, note
    
    # Artifact
    artifact_type = Column(String(30), nullable=True)  # document, confirmation, reference
    artifact_label = Column(String(255), nullable=True)
    artifact_url = Column(String(500), nullable=True)
    artifact_data = Column(JSONB, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    milestone = relationship("Milestone", back_populates="history")
    actor_user = relationship("AppUser")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        result = {
            "timestamp": self.created_at.isoformat() if self.created_at else None,
            "actor": self.actor,
            "actor_name": self.actor_name,
            "action": self.action,
        }
        
        if self.artifact_type:
            result["artifact"] = {
                "type": self.artifact_type,
                "label": self.artifact_label,
                "url": self.artifact_url,
            }
        
        return result


# =============================================================================
# MilestoneSubstep Model
# =============================================================================

class MilestoneSubstep(Base):
    """
    Substep within a milestone.
    
    Example substeps for "eligibility" milestone:
    - Verify coverage dates
    - Check plan type
    - Confirm member ID
    """
    
    __tablename__ = "milestone_substep"
    
    substep_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    milestone_id = Column(
        UUID(as_uuid=True),
        ForeignKey("milestone.milestone_id"),
        nullable=False
    )
    
    # Substep info
    label = Column(String(255), nullable=False)
    status = Column(String(20), default=SubstepStatus.PENDING, nullable=False)
    substep_order = Column(Integer, default=0, nullable=False)
    
    # Completion
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(String(20), nullable=True)
    completed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=True
    )
    
    # Link to plan step
    plan_step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=True
    )
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    milestone = relationship("Milestone", back_populates="substeps")
    completed_by_user = relationship("AppUser")
    plan_step = relationship("PlanStep")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.substep_id),
            "label": self.label,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "completed_by": self.completed_by,
        }


# =============================================================================
# UserOwnedTask Model
# =============================================================================

class UserOwnedTask(Base):
    """
    Track tasks where user said "I'll handle this".
    
    Batch job monitors these for:
    - Auto-resolution detection
    - Reminder sending after threshold
    """
    
    __tablename__ = "user_owned_task"
    
    ownership_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # What they're owning
    plan_step_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plan_step.step_id"),
        nullable=False
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("resolution_plan.plan_id"),
        nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=False
    )
    
    # Denormalized for display
    question_text = Column(String(500), nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_key = Column(String(100), nullable=True)
    
    # Status
    status = Column(String(20), default=OwnershipStatus.ACTIVE, nullable=False)
    
    # Initial note
    initial_note = Column(Text, nullable=True)
    
    # Resolution tracking (batch monitors)
    resolution_detected_at = Column(DateTime, nullable=True)
    resolution_signal = Column(String(255), nullable=True)
    resolution_source = Column(String(50), nullable=True)  # batch, user, system
    
    # Reminders
    last_reminder_at = Column(DateTime, nullable=True)
    reminder_count = Column(Integer, default=0, nullable=False)
    next_reminder_at = Column(DateTime, nullable=True)
    
    # Timestamps
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("AppUser")
    tenant = relationship("Tenant")
    plan_step = relationship("PlanStep")
    plan = relationship("ResolutionPlan")
    patient_context = relationship("PatientContext")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.ownership_id),
            "bottleneck_id": str(self.plan_step_id),
            "question_text": self.question_text,
            "patient_key": self.patient_key,
            "patient_name": self.patient_name,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "status": self.status,
            "resolution_detected": {
                "detected_at": self.resolution_detected_at.isoformat() if self.resolution_detected_at else None,
                "signal": self.resolution_signal,
            } if self.resolution_detected_at else None,
            "reminder_sent_at": self.last_reminder_at.isoformat() if self.last_reminder_at else None,
        }
