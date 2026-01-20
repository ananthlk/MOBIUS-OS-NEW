"""
Appointment and reminder models for CRM/Scheduler system.

These tables support:
1. Appointment scheduling and status tracking
2. Pre-visit and post-visit reminders
3. Follow-up management
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.db.postgres import Base


class AppointmentStatus(enum.Enum):
    """Appointment lifecycle status."""
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"


class AppointmentType(enum.Enum):
    """Type of appointment."""
    NEW_PATIENT = "new_patient"
    FOLLOW_UP = "follow_up"
    ANNUAL_EXAM = "annual_exam"
    URGENT = "urgent"
    TELEHEALTH = "telehealth"
    PROCEDURE = "procedure"
    CONSULTATION = "consultation"
    LAB_WORK = "lab_work"
    OTHER = "other"


class ReminderType(enum.Enum):
    """Type of reminder."""
    PRE_VISIT = "pre_visit"
    POST_VISIT = "post_visit"
    NO_SHOW_FOLLOW_UP = "no_show_follow_up"
    RECALL = "recall"
    CUSTOM = "custom"


class ReminderStatus(enum.Enum):
    """Reminder delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderChannel(enum.Enum):
    """Communication channel for reminder."""
    SMS = "sms"
    EMAIL = "email"
    PHONE_CALL = "phone_call"
    PORTAL = "portal"
    MAIL = "mail"


class Appointment(Base):
    """
    Core appointment record.
    
    Links to PatientContext for patient identity and supports
    full appointment lifecycle tracking.
    """
    
    __tablename__ = "appointment"
    
    appointment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("tenant.tenant_id"), 
        nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("patient_context.patient_context_id"), 
        nullable=False
    )
    
    # Scheduling details
    scheduled_date = Column(Date, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30, nullable=False)
    
    # Appointment type and status
    appointment_type = Column(String(50), default="follow_up", nullable=False)
    status = Column(String(20), default="scheduled", nullable=False)
    
    # Provider/resource assignment
    provider_name = Column(String(255), nullable=True)
    provider_id = Column(UUID(as_uuid=True), nullable=True)
    location = Column(String(255), nullable=True)
    room = Column(String(50), nullable=True)
    
    # Visit reason
    chief_complaint = Column(Text, nullable=True)
    visit_reason = Column(Text, nullable=True)
    
    # Check-in tracking
    checked_in_at = Column(DateTime, nullable=True)
    wait_time_minutes = Column(Integer, nullable=True)
    
    # Completion tracking
    completed_at = Column(DateTime, nullable=True)
    no_show_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Rescheduling
    rescheduled_from_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("appointment.appointment_id"), 
        nullable=True
    )
    rescheduled_to_id = Column(UUID(as_uuid=True), nullable=True)
    
    # Notes
    internal_notes = Column(Text, nullable=True)
    patient_instructions = Column(Text, nullable=True)
    
    # Flags for CRM attention
    needs_confirmation = Column(Boolean, default=True, nullable=False)
    needs_insurance_verification = Column(Boolean, default=False, nullable=False)
    needs_prior_auth = Column(Boolean, default=False, nullable=False)
    
    # Extended data
    extended_data = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    reminders = relationship("AppointmentReminder", back_populates="appointment")
    rescheduled_from = relationship("Appointment", remote_side=[appointment_id], foreign_keys=[rescheduled_from_id])
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "appointment_id": str(self.appointment_id),
            "patient_context_id": str(self.patient_context_id),
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "duration_minutes": self.duration_minutes,
            "appointment_type": self.appointment_type,
            "status": self.status,
            "provider_name": self.provider_name,
            "location": self.location,
            "room": self.room,
            "chief_complaint": self.chief_complaint,
            "visit_reason": self.visit_reason,
            "checked_in_at": self.checked_in_at.isoformat() if self.checked_in_at else None,
            "wait_time_minutes": self.wait_time_minutes,
            "needs_confirmation": self.needs_confirmation,
            "needs_insurance_verification": self.needs_insurance_verification,
            "needs_prior_auth": self.needs_prior_auth,
        }


class AppointmentReminder(Base):
    """
    Reminder/follow-up for an appointment.
    
    Supports pre-visit reminders, post-visit follow-ups,
    no-show outreach, and recall reminders.
    """
    
    __tablename__ = "appointment_reminder"
    
    reminder_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    appointment_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("appointment.appointment_id"), 
        nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("patient_context.patient_context_id"), 
        nullable=False
    )
    
    # Reminder type and timing
    reminder_type = Column(String(30), default="pre_visit", nullable=False)
    channel = Column(String(20), default="sms", nullable=False)
    
    # Scheduling
    scheduled_date = Column(Date, nullable=False)
    scheduled_time = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=False)
    
    # Status tracking
    status = Column(String(20), default="pending", nullable=False)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Response/completion tracking
    patient_responded = Column(Boolean, default=False, nullable=False)
    patient_response = Column(Text, nullable=True)
    response_at = Column(DateTime, nullable=True)
    
    # Staff action tracking
    staff_action = Column(String(50), nullable=True)  # "called", "left_voicemail", "sent_letter"
    staff_action_at = Column(DateTime, nullable=True)
    staff_action_by = Column(UUID(as_uuid=True), nullable=True)
    staff_notes = Column(Text, nullable=True)
    
    # Attempt tracking
    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    last_attempt_at = Column(DateTime, nullable=True)
    
    # Content
    message_template = Column(String(100), nullable=True)
    message_content = Column(Text, nullable=True)
    
    # Failure tracking
    failure_reason = Column(Text, nullable=True)
    
    # Extended data
    extended_data = Column(JSONB, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    appointment = relationship("Appointment", back_populates="reminders")
    patient_context = relationship("PatientContext")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "reminder_id": str(self.reminder_id),
            "appointment_id": str(self.appointment_id),
            "patient_context_id": str(self.patient_context_id),
            "reminder_type": self.reminder_type,
            "channel": self.channel,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "patient_responded": self.patient_responded,
            "patient_response": self.patient_response,
            "attempt_count": self.attempt_count,
            "staff_action": self.staff_action,
            "staff_notes": self.staff_notes,
        }
