"""
Billing models for the Unified EMR.

These tables support:
1. Patient insurance information
2. Charges and line items
3. Claims (submission, status, payments)
4. Payments and adjustments
5. Patient statements
"""

import uuid
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.db.postgres import Base


class ClaimStatus(enum.Enum):
    """Status of an insurance claim."""
    DRAFT = "draft"
    READY = "ready"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    DENIED = "denied"
    APPEALED = "appealed"
    CLOSED = "closed"


class PatientInsurance(Base):
    """
    Patient insurance coverage information.
    """
    
    __tablename__ = "patient_insurance"
    
    insurance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Coverage type
    coverage_type = Column(String(20), nullable=False)  # primary, secondary, tertiary
    
    # Insurance company
    payer_name = Column(String(255), nullable=False)
    payer_id = Column(String(50), nullable=True)  # Electronic payer ID
    payer_phone = Column(String(50), nullable=True)
    payer_address = Column(Text, nullable=True)
    
    # Policy details
    policy_number = Column(String(100), nullable=True)
    group_number = Column(String(100), nullable=True)
    group_name = Column(String(255), nullable=True)
    
    # Subscriber info (if different from patient)
    subscriber_name = Column(String(255), nullable=True)
    subscriber_dob = Column(Date, nullable=True)
    subscriber_relationship = Column(String(50), nullable=True)  # Self, Spouse, Child, Other
    
    # Coverage dates
    effective_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True)
    
    # Plan details
    plan_type = Column(String(50), nullable=True)  # HMO, PPO, EPO, POS, Medicaid, Medicare
    copay_amount = Column(Numeric(10, 2), nullable=True)
    deductible = Column(Numeric(10, 2), nullable=True)
    deductible_met = Column(Numeric(10, 2), nullable=True)
    out_of_pocket_max = Column(Numeric(10, 2), nullable=True)
    out_of_pocket_met = Column(Numeric(10, 2), nullable=True)
    
    # Verification
    verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by = Column(String(255), nullable=True)
    eligibility_status = Column(String(50), nullable=True)  # Active, Inactive, Unknown
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "insurance_id": str(self.insurance_id),
            "patient_context_id": str(self.patient_context_id),
            "coverage_type": self.coverage_type,
            "payer_name": self.payer_name,
            "payer_id": self.payer_id,
            "policy_number": self.policy_number,
            "group_number": self.group_number,
            "group_name": self.group_name,
            "subscriber_name": self.subscriber_name,
            "subscriber_relationship": self.subscriber_relationship,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "termination_date": self.termination_date.isoformat() if self.termination_date else None,
            "plan_type": self.plan_type,
            "copay_amount": float(self.copay_amount) if self.copay_amount else None,
            "deductible": float(self.deductible) if self.deductible else None,
            "deductible_met": float(self.deductible_met) if self.deductible_met else None,
            "verified": self.verified,
            "eligibility_status": self.eligibility_status,
            "is_active": self.is_active,
        }


class Charge(Base):
    """
    Individual charge/line item for services rendered.
    """
    
    __tablename__ = "charge"
    
    charge_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Service details
    service_date = Column(Date, nullable=False)
    cpt_code = Column(String(20), nullable=True)
    hcpcs_code = Column(String(20), nullable=True)
    description = Column(String(500), nullable=False)
    
    # Modifiers
    modifier_1 = Column(String(10), nullable=True)
    modifier_2 = Column(String(10), nullable=True)
    modifier_3 = Column(String(10), nullable=True)
    modifier_4 = Column(String(10), nullable=True)
    
    # Diagnosis pointers (1-based index to claim diagnoses)
    diagnosis_pointers = Column(JSONB, nullable=True)  # [1, 2]
    
    # Quantities and amounts
    units = Column(Numeric(10, 2), default=1, nullable=False)
    unit_charge = Column(Numeric(10, 2), nullable=False)
    total_charge = Column(Numeric(10, 2), nullable=False)
    
    # Adjustments and balances
    allowed_amount = Column(Numeric(10, 2), nullable=True)
    adjustment_amount = Column(Numeric(10, 2), default=0, nullable=False)
    paid_amount = Column(Numeric(10, 2), default=0, nullable=False)
    patient_responsibility = Column(Numeric(10, 2), nullable=True)
    balance = Column(Numeric(10, 2), nullable=True)
    
    # Provider info
    rendering_provider_id = Column(UUID(as_uuid=True), nullable=True)
    rendering_provider_name = Column(String(255), nullable=True)
    
    # Facility
    place_of_service = Column(String(10), nullable=True)  # 11 = Office, 21 = Hospital, etc.
    facility_name = Column(String(255), nullable=True)
    
    # Status
    status = Column(String(50), default="pending", nullable=False)  # pending, billed, paid, write_off
    
    # Link to claim
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claim.claim_id"), nullable=True)
    
    # Timestamps
    posted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    claim = relationship("Claim", back_populates="charges")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "charge_id": str(self.charge_id),
            "patient_context_id": str(self.patient_context_id),
            "service_date": self.service_date.isoformat() if self.service_date else None,
            "cpt_code": self.cpt_code,
            "description": self.description,
            "units": float(self.units) if self.units else None,
            "unit_charge": float(self.unit_charge) if self.unit_charge else None,
            "total_charge": float(self.total_charge) if self.total_charge else None,
            "allowed_amount": float(self.allowed_amount) if self.allowed_amount else None,
            "adjustment_amount": float(self.adjustment_amount) if self.adjustment_amount else None,
            "paid_amount": float(self.paid_amount) if self.paid_amount else None,
            "patient_responsibility": float(self.patient_responsibility) if self.patient_responsibility else None,
            "balance": float(self.balance) if self.balance else None,
            "rendering_provider_name": self.rendering_provider_name,
            "status": self.status,
            "claim_id": str(self.claim_id) if self.claim_id else None,
        }


class Claim(Base):
    """
    Insurance claim record.
    """
    
    __tablename__ = "claim"
    
    claim_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Claim identification
    claim_number = Column(String(50), nullable=True)  # Internal claim number
    payer_claim_number = Column(String(100), nullable=True)  # Payer's claim ID
    
    # Insurance info
    insurance_id = Column(UUID(as_uuid=True), ForeignKey("patient_insurance.insurance_id"), nullable=True)
    payer_name = Column(String(255), nullable=True)
    
    # Dates
    service_date_from = Column(Date, nullable=True)
    service_date_to = Column(Date, nullable=True)
    
    # Diagnoses (ICD-10)
    diagnosis_codes = Column(JSONB, nullable=True)  # ["Z00.00", "J06.9", "R05.9"]
    
    # Amounts
    total_charges = Column(Numeric(10, 2), default=0, nullable=False)
    allowed_amount = Column(Numeric(10, 2), nullable=True)
    paid_amount = Column(Numeric(10, 2), default=0, nullable=False)
    adjustment_amount = Column(Numeric(10, 2), default=0, nullable=False)
    patient_responsibility = Column(Numeric(10, 2), nullable=True)
    
    # Claim type
    claim_type = Column(String(20), nullable=True)  # Professional, Institutional
    claim_frequency = Column(String(10), nullable=True)  # 1=Original, 7=Replacement, 8=Void
    
    # Providers
    billing_provider_npi = Column(String(20), nullable=True)
    billing_provider_name = Column(String(255), nullable=True)
    rendering_provider_npi = Column(String(20), nullable=True)
    rendering_provider_name = Column(String(255), nullable=True)
    
    # Facility
    facility_name = Column(String(255), nullable=True)
    place_of_service = Column(String(10), nullable=True)
    
    # Status and workflow
    status = Column(String(50), default="draft", nullable=False)
    
    # Submission details
    submitted_at = Column(DateTime, nullable=True)
    submission_method = Column(String(50), nullable=True)  # Electronic, Paper
    clearinghouse = Column(String(100), nullable=True)
    
    # Response tracking
    acknowledged_at = Column(DateTime, nullable=True)
    adjudicated_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    
    # Denial info
    denial_reason = Column(String(500), nullable=True)
    denial_codes = Column(JSONB, nullable=True)
    
    # Appeal info
    appeal_deadline = Column(Date, nullable=True)
    appealed_at = Column(DateTime, nullable=True)
    appeal_status = Column(String(50), nullable=True)
    
    # Notes
    internal_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    insurance = relationship("PatientInsurance")
    charges = relationship("Charge", back_populates="claim")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "claim_id": str(self.claim_id),
            "patient_context_id": str(self.patient_context_id),
            "claim_number": self.claim_number,
            "payer_claim_number": self.payer_claim_number,
            "payer_name": self.payer_name,
            "service_date_from": self.service_date_from.isoformat() if self.service_date_from else None,
            "service_date_to": self.service_date_to.isoformat() if self.service_date_to else None,
            "diagnosis_codes": self.diagnosis_codes,
            "total_charges": float(self.total_charges) if self.total_charges else None,
            "allowed_amount": float(self.allowed_amount) if self.allowed_amount else None,
            "paid_amount": float(self.paid_amount) if self.paid_amount else None,
            "adjustment_amount": float(self.adjustment_amount) if self.adjustment_amount else None,
            "patient_responsibility": float(self.patient_responsibility) if self.patient_responsibility else None,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "denial_reason": self.denial_reason,
        }


class Payment(Base):
    """
    Payment record (from insurance or patient).
    """
    
    __tablename__ = "payment"
    
    payment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=True  # Null for insurance payments
    )
    
    # Payment source
    payment_source = Column(String(50), nullable=False)  # patient, insurance
    payer_name = Column(String(255), nullable=True)
    
    # Payment details
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    
    # Payment method
    payment_method = Column(String(50), nullable=True)  # Cash, Check, Credit Card, EFT, ERA
    check_number = Column(String(50), nullable=True)
    reference_number = Column(String(100), nullable=True)
    
    # ERA info (for insurance payments)
    era_check_number = Column(String(50), nullable=True)
    era_check_date = Column(Date, nullable=True)
    
    # Link to claim (for insurance payments)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claim.claim_id"), nullable=True)
    
    # Status
    status = Column(String(50), default="posted", nullable=False)  # pending, posted, voided
    
    # Notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    posted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    posted_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    claim = relationship("Claim")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "payment_id": str(self.payment_id),
            "patient_context_id": str(self.patient_context_id) if self.patient_context_id else None,
            "payment_source": self.payment_source,
            "payer_name": self.payer_name,
            "payment_date": self.payment_date.isoformat() if self.payment_date else None,
            "amount": float(self.amount) if self.amount else None,
            "payment_method": self.payment_method,
            "check_number": self.check_number,
            "reference_number": self.reference_number,
            "claim_id": str(self.claim_id) if self.claim_id else None,
            "status": self.status,
            "notes": self.notes,
        }


class PatientStatement(Base):
    """
    Patient statement record.
    """
    
    __tablename__ = "patient_statement"
    
    statement_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Statement details
    statement_number = Column(String(50), nullable=True)
    statement_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    
    # Period covered
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    
    # Amounts
    previous_balance = Column(Numeric(10, 2), default=0, nullable=False)
    new_charges = Column(Numeric(10, 2), default=0, nullable=False)
    payments_received = Column(Numeric(10, 2), default=0, nullable=False)
    adjustments = Column(Numeric(10, 2), default=0, nullable=False)
    balance_due = Column(Numeric(10, 2), nullable=False)
    
    # Aging
    current = Column(Numeric(10, 2), default=0, nullable=False)
    days_30 = Column(Numeric(10, 2), default=0, nullable=False)
    days_60 = Column(Numeric(10, 2), default=0, nullable=False)
    days_90 = Column(Numeric(10, 2), default=0, nullable=False)
    days_120_plus = Column(Numeric(10, 2), default=0, nullable=False)
    
    # Delivery
    delivery_method = Column(String(50), nullable=True)  # Print, Email, Portal
    sent_at = Column(DateTime, nullable=True)
    
    # Status
    status = Column(String(50), default="generated", nullable=False)  # generated, sent, viewed, paid
    
    # Message
    custom_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "statement_id": str(self.statement_id),
            "patient_context_id": str(self.patient_context_id),
            "statement_number": self.statement_number,
            "statement_date": self.statement_date.isoformat() if self.statement_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "previous_balance": float(self.previous_balance) if self.previous_balance else 0,
            "new_charges": float(self.new_charges) if self.new_charges else 0,
            "payments_received": float(self.payments_received) if self.payments_received else 0,
            "adjustments": float(self.adjustments) if self.adjustments else 0,
            "balance_due": float(self.balance_due) if self.balance_due else 0,
            "current": float(self.current) if self.current else 0,
            "days_30": float(self.days_30) if self.days_30 else 0,
            "days_60": float(self.days_60) if self.days_60 else 0,
            "days_90": float(self.days_90) if self.days_90 else 0,
            "days_120_plus": float(self.days_120_plus) if self.days_120_plus else 0,
            "status": self.status,
        }
