"""
Patient intake and registration models for CRM/Scheduler system.

These tables support:
1. Patient intake forms and document collection
2. Insurance verification tracking
3. Registration workflow management
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.db.postgres import Base


class FormType(enum.Enum):
    """Type of intake form."""
    DEMOGRAPHICS = "demographics"
    INSURANCE = "insurance"
    CONSENT = "consent"
    MEDICAL_HISTORY = "medical_history"
    HIPAA = "hipaa"
    FINANCIAL_POLICY = "financial_policy"
    RELEASE_OF_INFO = "release_of_info"
    ADVANCE_DIRECTIVE = "advance_directive"
    PHARMACY = "pharmacy"
    EMERGENCY_CONTACT = "emergency_contact"
    OTHER = "other"


class FormStatus(enum.Enum):
    """Status of intake form completion."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    NEEDS_UPDATE = "needs_update"
    EXPIRED = "expired"


class VerificationStatus(enum.Enum):
    """Insurance verification status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"


class IntakeForm(Base):
    """
    Patient intake form record.
    
    Tracks completion status of various intake forms
    required for patient registration.
    """
    
    __tablename__ = "intake_form"
    
    form_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Form identification
    form_type = Column(String(50), nullable=False)
    form_name = Column(String(255), nullable=True)
    form_version = Column(String(20), nullable=True)
    
    # Status tracking
    status = Column(String(30), default="not_started", nullable=False)
    
    # Progress tracking
    total_fields = Column(Integer, nullable=True)
    completed_fields = Column(Integer, default=0, nullable=True)
    completion_percentage = Column(Integer, default=0, nullable=True)
    
    # Timestamps
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_modified_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Review tracking
    needs_review = Column(Boolean, default=False, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(UUID(as_uuid=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    
    # Validation
    is_valid = Column(Boolean, default=False, nullable=False)
    validation_errors = Column(JSONB, nullable=True)
    
    # Form data (encrypted/sensitive data should be handled separately)
    form_data = Column(JSONB, nullable=True)
    
    # Document storage reference
    document_url = Column(String(500), nullable=True)
    document_id = Column(String(100), nullable=True)
    
    # Audit
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "form_id": str(self.form_id),
            "patient_context_id": str(self.patient_context_id),
            "form_type": self.form_type,
            "form_name": self.form_name,
            "status": self.status,
            "total_fields": self.total_fields,
            "completed_fields": self.completed_fields,
            "completion_percentage": self.completion_percentage,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "needs_review": self.needs_review,
            "is_valid": self.is_valid,
        }


class InsuranceVerification(Base):
    """
    Insurance eligibility verification record.
    
    Tracks the verification status of a patient's
    insurance coverage for upcoming appointments.
    """
    
    __tablename__ = "insurance_verification"
    
    verification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    appointment_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("appointment.appointment_id"), 
        nullable=True
    )
    
    # Insurance identification
    insurance_id = Column(String(100), nullable=True)  # Policy number
    insurance_name = Column(String(255), nullable=True)  # Payer name
    member_id = Column(String(100), nullable=True)
    group_number = Column(String(100), nullable=True)
    
    # Subscriber info
    subscriber_name = Column(String(255), nullable=True)
    subscriber_relationship = Column(String(50), nullable=True)  # "self", "spouse", "child", "other"
    
    # Verification status
    status = Column(String(30), default="pending", nullable=False)
    
    # Verification dates
    verification_date = Column(Date, nullable=True)
    service_date = Column(Date, nullable=True)  # Date of service being verified for
    
    # Eligibility results
    is_eligible = Column(Boolean, nullable=True)
    coverage_start_date = Column(Date, nullable=True)
    coverage_end_date = Column(Date, nullable=True)
    
    # Benefits info
    copay_amount = Column(Integer, nullable=True)  # In cents
    coinsurance_percentage = Column(Integer, nullable=True)
    deductible_amount = Column(Integer, nullable=True)  # In cents
    deductible_met = Column(Integer, nullable=True)  # In cents
    out_of_pocket_max = Column(Integer, nullable=True)  # In cents
    out_of_pocket_met = Column(Integer, nullable=True)  # In cents
    
    # Prior authorization
    requires_prior_auth = Column(Boolean, default=False, nullable=False)
    prior_auth_number = Column(String(100), nullable=True)
    prior_auth_status = Column(String(30), nullable=True)
    prior_auth_expires = Column(Date, nullable=True)
    
    # Payer response
    payer_response_code = Column(String(50), nullable=True)
    payer_response_message = Column(Text, nullable=True)
    payer_response_data = Column(JSONB, nullable=True)
    
    # Manual verification
    verified_manually = Column(Boolean, default=False, nullable=False)
    verified_by = Column(UUID(as_uuid=True), nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    # Failure tracking
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    last_retry_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    appointment = relationship("Appointment")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "verification_id": str(self.verification_id),
            "patient_context_id": str(self.patient_context_id),
            "appointment_id": str(self.appointment_id) if self.appointment_id else None,
            "insurance_name": self.insurance_name,
            "member_id": self.member_id,
            "status": self.status,
            "is_eligible": self.is_eligible,
            "coverage_start_date": self.coverage_start_date.isoformat() if self.coverage_start_date else None,
            "coverage_end_date": self.coverage_end_date.isoformat() if self.coverage_end_date else None,
            "copay_amount": self.copay_amount,
            "deductible_amount": self.deductible_amount,
            "deductible_met": self.deductible_met,
            "requires_prior_auth": self.requires_prior_auth,
            "prior_auth_status": self.prior_auth_status,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "failure_reason": self.failure_reason,
        }


class IntakeChecklist(Base):
    """
    Overall intake/registration checklist for a patient visit.
    
    Aggregates all requirements for a patient to be
    considered "ready" for their appointment.
    """
    
    __tablename__ = "intake_checklist"
    
    checklist_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    appointment_id = Column(
        UUID(as_uuid=True), 
        ForeignKey("appointment.appointment_id"), 
        nullable=True
    )
    
    # Overall status
    status = Column(String(30), default="incomplete", nullable=False)  # "incomplete", "ready", "issues"
    
    # Individual item statuses
    demographics_complete = Column(Boolean, default=False, nullable=False)
    insurance_verified = Column(Boolean, default=False, nullable=False)
    consent_signed = Column(Boolean, default=False, nullable=False)
    hipaa_signed = Column(Boolean, default=False, nullable=False)
    medical_history_complete = Column(Boolean, default=False, nullable=False)
    photo_id_verified = Column(Boolean, default=False, nullable=False)
    insurance_card_scanned = Column(Boolean, default=False, nullable=False)
    copay_collected = Column(Boolean, default=False, nullable=False)
    
    # Counts
    total_items = Column(Integer, default=8, nullable=False)
    completed_items = Column(Integer, default=0, nullable=False)
    
    # Issues/blockers
    has_issues = Column(Boolean, default=False, nullable=False)
    issues = Column(JSONB, nullable=True)  # List of issue descriptions
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Staff tracking
    last_updated_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    appointment = relationship("Appointment")
    
    def calculate_status(self):
        """Recalculate status based on item completion."""
        items = [
            self.demographics_complete,
            self.insurance_verified,
            self.consent_signed,
            self.hipaa_signed,
            self.medical_history_complete,
            self.photo_id_verified,
            self.insurance_card_scanned,
            self.copay_collected,
        ]
        self.completed_items = sum(1 for item in items if item)
        self.total_items = len(items)
        
        if self.has_issues:
            self.status = "issues"
        elif self.completed_items == self.total_items:
            self.status = "ready"
            if not self.completed_at:
                self.completed_at = datetime.utcnow()
        else:
            self.status = "incomplete"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "checklist_id": str(self.checklist_id),
            "patient_context_id": str(self.patient_context_id),
            "appointment_id": str(self.appointment_id) if self.appointment_id else None,
            "status": self.status,
            "total_items": self.total_items,
            "completed_items": self.completed_items,
            "demographics_complete": self.demographics_complete,
            "insurance_verified": self.insurance_verified,
            "consent_signed": self.consent_signed,
            "hipaa_signed": self.hipaa_signed,
            "medical_history_complete": self.medical_history_complete,
            "photo_id_verified": self.photo_id_verified,
            "insurance_card_scanned": self.insurance_card_scanned,
            "copay_collected": self.copay_collected,
            "has_issues": self.has_issues,
            "issues": self.issues,
        }
