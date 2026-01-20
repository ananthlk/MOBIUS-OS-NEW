"""
Clinical orders models for the Unified EMR.

These tables support:
1. Lab orders (CBC, BMP, lipid panel, etc.)
2. Imaging orders (X-ray, CT, MRI, ultrasound)
3. Medication orders / prescriptions
4. Referral orders
5. Procedure orders
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.db.postgres import Base


class OrderStatus(enum.Enum):
    """Status of an order."""
    DRAFT = "draft"
    PENDING = "pending"
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DISCONTINUED = "discontinued"


class OrderPriority(enum.Enum):
    """Priority level for orders."""
    ROUTINE = "routine"
    URGENT = "urgent"
    STAT = "stat"
    ASAP = "asap"


class ClinicalOrder(Base):
    """
    Base clinical order record.
    
    Represents any type of clinical order (lab, imaging, medication, referral, procedure).
    """
    
    __tablename__ = "clinical_order"
    
    order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    
    # Order type: lab, imaging, medication, referral, procedure
    order_type = Column(String(50), nullable=False)
    
    # Order details
    order_name = Column(String(255), nullable=False)  # e.g., "CBC with Differential", "Chest X-Ray"
    order_code = Column(String(50), nullable=True)  # CPT, LOINC, or internal code
    order_description = Column(Text, nullable=True)
    
    # Status and priority
    status = Column(String(50), default="pending", nullable=False)
    priority = Column(String(20), default="routine", nullable=False)
    
    # Ordering provider
    ordering_provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider.provider_id"),
        nullable=True
    )
    ordering_provider_name = Column(String(255), nullable=True)
    
    # Performing provider/facility (for referrals, imaging)
    performing_provider_id = Column(UUID(as_uuid=True), nullable=True)
    performing_facility = Column(String(255), nullable=True)
    
    # Clinical information
    diagnosis_codes = Column(JSONB, nullable=True)  # ["Z00.00", "R10.9"]
    clinical_notes = Column(Text, nullable=True)
    
    # Scheduling
    scheduled_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    
    # Results
    result_date = Column(DateTime, nullable=True)
    result_status = Column(String(50), nullable=True)  # normal, abnormal, critical
    result_summary = Column(Text, nullable=True)
    result_details = Column(JSONB, nullable=True)
    
    # Timestamps
    ordered_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    ordering_provider = relationship("Provider", foreign_keys=[ordering_provider_id])
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "order_id": str(self.order_id),
            "patient_context_id": str(self.patient_context_id),
            "order_type": self.order_type,
            "order_name": self.order_name,
            "order_code": self.order_code,
            "order_description": self.order_description,
            "status": self.status,
            "priority": self.priority,
            "ordering_provider_name": self.ordering_provider_name,
            "performing_facility": self.performing_facility,
            "diagnosis_codes": self.diagnosis_codes,
            "clinical_notes": self.clinical_notes,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "result_date": self.result_date.isoformat() if self.result_date else None,
            "result_status": self.result_status,
            "result_summary": self.result_summary,
            "ordered_at": self.ordered_at.isoformat() if self.ordered_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class LabOrder(Base):
    """
    Lab-specific order details.
    
    Extends ClinicalOrder with lab-specific fields.
    """
    
    __tablename__ = "lab_order"
    
    lab_order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical_order.order_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Lab-specific details
    specimen_type = Column(String(100), nullable=True)  # Blood, Urine, Stool, etc.
    collection_method = Column(String(100), nullable=True)
    fasting_required = Column(Boolean, default=False, nullable=False)
    
    # Collection info
    collected_at = Column(DateTime, nullable=True)
    collected_by = Column(String(255), nullable=True)
    
    # Lab facility
    lab_name = Column(String(255), nullable=True)
    lab_accession = Column(String(100), nullable=True)  # Lab's internal ID
    
    # Results
    results = Column(JSONB, nullable=True)  # Detailed results array
    reference_ranges = Column(JSONB, nullable=True)
    
    # Relationships
    clinical_order = relationship("ClinicalOrder")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "lab_order_id": str(self.lab_order_id),
            "order_id": str(self.order_id),
            "specimen_type": self.specimen_type,
            "collection_method": self.collection_method,
            "fasting_required": self.fasting_required,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "collected_by": self.collected_by,
            "lab_name": self.lab_name,
            "lab_accession": self.lab_accession,
            "results": self.results,
            "reference_ranges": self.reference_ranges,
        }


class ImagingOrder(Base):
    """
    Imaging-specific order details.
    """
    
    __tablename__ = "imaging_order"
    
    imaging_order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical_order.order_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Imaging-specific details
    modality = Column(String(50), nullable=True)  # X-Ray, CT, MRI, Ultrasound, PET
    body_part = Column(String(100), nullable=True)
    laterality = Column(String(20), nullable=True)  # Left, Right, Bilateral
    contrast = Column(Boolean, default=False, nullable=False)
    contrast_type = Column(String(100), nullable=True)
    
    # Scheduling
    appointment_id = Column(UUID(as_uuid=True), nullable=True)
    performed_at = Column(DateTime, nullable=True)
    
    # Radiology info
    radiologist_name = Column(String(255), nullable=True)
    study_accession = Column(String(100), nullable=True)
    
    # Report
    report_status = Column(String(50), nullable=True)  # Preliminary, Final
    report_text = Column(Text, nullable=True)
    impression = Column(Text, nullable=True)
    
    # Relationships
    clinical_order = relationship("ClinicalOrder")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "imaging_order_id": str(self.imaging_order_id),
            "order_id": str(self.order_id),
            "modality": self.modality,
            "body_part": self.body_part,
            "laterality": self.laterality,
            "contrast": self.contrast,
            "contrast_type": self.contrast_type,
            "performed_at": self.performed_at.isoformat() if self.performed_at else None,
            "radiologist_name": self.radiologist_name,
            "report_status": self.report_status,
            "report_text": self.report_text,
            "impression": self.impression,
        }


class MedicationOrder(Base):
    """
    Medication order / prescription details.
    """
    
    __tablename__ = "medication_order"
    
    medication_order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical_order.order_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Medication details
    medication_name = Column(String(255), nullable=False)
    generic_name = Column(String(255), nullable=True)
    ndc = Column(String(20), nullable=True)  # National Drug Code
    rxnorm_code = Column(String(20), nullable=True)
    
    # Dosing
    dose = Column(String(100), nullable=True)  # e.g., "10mg"
    dose_unit = Column(String(50), nullable=True)
    route = Column(String(50), nullable=True)  # Oral, IV, IM, SC, etc.
    frequency = Column(String(100), nullable=True)  # e.g., "BID", "Q8H"
    duration = Column(String(100), nullable=True)  # e.g., "7 days"
    quantity = Column(Integer, nullable=True)
    refills = Column(Integer, default=0, nullable=False)
    
    # Prescription details
    daw = Column(Boolean, default=False, nullable=False)  # Dispense as Written
    instructions = Column(Text, nullable=True)  # SIG instructions
    pharmacy_name = Column(String(255), nullable=True)
    pharmacy_npi = Column(String(20), nullable=True)
    
    # Status
    dispense_status = Column(String(50), nullable=True)  # New, Refill, Filled, Picked Up
    filled_at = Column(DateTime, nullable=True)
    
    # Timestamps
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    # Relationships
    clinical_order = relationship("ClinicalOrder")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "medication_order_id": str(self.medication_order_id),
            "order_id": str(self.order_id),
            "medication_name": self.medication_name,
            "generic_name": self.generic_name,
            "ndc": self.ndc,
            "dose": self.dose,
            "dose_unit": self.dose_unit,
            "route": self.route,
            "frequency": self.frequency,
            "duration": self.duration,
            "quantity": self.quantity,
            "refills": self.refills,
            "instructions": self.instructions,
            "pharmacy_name": self.pharmacy_name,
            "dispense_status": self.dispense_status,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
        }


class ReferralOrder(Base):
    """
    Referral order details.
    """
    
    __tablename__ = "referral_order"
    
    referral_order_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clinical_order.order_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Referral details
    specialty = Column(String(100), nullable=True)
    referred_to_provider = Column(String(255), nullable=True)
    referred_to_facility = Column(String(255), nullable=True)
    referred_to_phone = Column(String(50), nullable=True)
    referred_to_fax = Column(String(50), nullable=True)
    
    # Clinical info
    reason_for_referral = Column(Text, nullable=True)
    clinical_summary = Column(Text, nullable=True)
    
    # Authorization
    auth_required = Column(Boolean, default=False, nullable=False)
    auth_number = Column(String(100), nullable=True)
    auth_status = Column(String(50), nullable=True)  # Pending, Approved, Denied
    auth_expiry = Column(Date, nullable=True)
    visits_authorized = Column(Integer, nullable=True)
    visits_used = Column(Integer, default=0, nullable=False)
    
    # Appointment info
    appointment_date = Column(Date, nullable=True)
    appointment_notes = Column(Text, nullable=True)
    
    # Consultation report
    consultation_received = Column(Boolean, default=False, nullable=False)
    consultation_date = Column(Date, nullable=True)
    consultation_notes = Column(Text, nullable=True)
    
    # Relationships
    clinical_order = relationship("ClinicalOrder")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "referral_order_id": str(self.referral_order_id),
            "order_id": str(self.order_id),
            "specialty": self.specialty,
            "referred_to_provider": self.referred_to_provider,
            "referred_to_facility": self.referred_to_facility,
            "reason_for_referral": self.reason_for_referral,
            "auth_required": self.auth_required,
            "auth_number": self.auth_number,
            "auth_status": self.auth_status,
            "visits_authorized": self.visits_authorized,
            "visits_used": self.visits_used,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "consultation_received": self.consultation_received,
        }
