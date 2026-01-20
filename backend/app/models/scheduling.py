"""
Provider scheduling and time slot models for the Unified EMR.

These tables support:
1. Provider availability templates (weekly schedules)
2. Individual bookable time slots
3. Schedule exceptions (blocked time, holidays)
"""

import uuid
from datetime import datetime, date, time
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Date, Time, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.db.postgres import Base


class SlotStatus(enum.Enum):
    """Status of a time slot."""
    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"
    HELD = "held"  # Temporarily held during booking


class Provider(Base):
    """
    Healthcare provider record.
    
    Represents doctors, nurses, therapists, and other
    providers who can be scheduled for appointments.
    """
    
    __tablename__ = "provider"
    
    provider_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Provider identification
    provider_name = Column(String(255), nullable=False)
    credentials = Column(String(100), nullable=True)  # MD, DO, NP, PA, LCSW, etc.
    specialty = Column(String(100), nullable=True)
    department = Column(String(100), nullable=True)
    
    # Contact info
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    
    # NPI (National Provider Identifier)
    npi = Column(String(20), nullable=True)
    
    # Scheduling settings
    default_slot_duration = Column(Integer, default=30, nullable=False)  # minutes
    max_patients_per_day = Column(Integer, nullable=True)
    accepts_new_patients = Column(Boolean, default=True, nullable=False)
    
    # Location(s)
    primary_location = Column(String(255), nullable=True)
    locations = Column(JSONB, nullable=True)  # ["Main Campus", "East Wing"]
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Avatar/photo
    photo_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tenant = relationship("Tenant")
    schedules = relationship("ProviderSchedule", back_populates="provider")
    time_slots = relationship("TimeSlot", back_populates="provider")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "provider_id": str(self.provider_id),
            "provider_name": self.provider_name,
            "credentials": self.credentials,
            "specialty": self.specialty,
            "department": self.department,
            "npi": self.npi,
            "default_slot_duration": self.default_slot_duration,
            "accepts_new_patients": self.accepts_new_patients,
            "primary_location": self.primary_location,
            "locations": self.locations,
            "is_active": self.is_active,
            "photo_url": self.photo_url,
        }


class ProviderSchedule(Base):
    """
    Provider weekly availability template.
    
    Defines the recurring weekly schedule for a provider,
    e.g., "Mondays 8am-5pm at Main Campus".
    """
    
    __tablename__ = "provider_schedule"
    
    schedule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider.provider_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Day of week (0=Monday, 6=Sunday, matching Python's weekday())
    day_of_week = Column(Integer, nullable=False)
    
    # Time range
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Slot configuration
    slot_duration_minutes = Column(Integer, default=30, nullable=False)
    
    # Location for this schedule block
    location = Column(String(255), nullable=True)
    room = Column(String(50), nullable=True)
    
    # Appointment types allowed (null = all types)
    allowed_appointment_types = Column(JSONB, nullable=True)  # ["follow_up", "new_patient"]
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Effective date range (for seasonal schedules)
    effective_from = Column(Date, nullable=True)
    effective_until = Column(Date, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    provider = relationship("Provider", back_populates="schedules")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "schedule_id": str(self.schedule_id),
            "provider_id": str(self.provider_id),
            "day_of_week": self.day_of_week,
            "day_name": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][self.day_of_week],
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "slot_duration_minutes": self.slot_duration_minutes,
            "location": self.location,
            "room": self.room,
            "allowed_appointment_types": self.allowed_appointment_types,
            "is_active": self.is_active,
        }


class TimeSlot(Base):
    """
    Individual bookable time slot.
    
    Generated from ProviderSchedule templates, these represent
    actual bookable slots on specific dates.
    """
    
    __tablename__ = "time_slot"
    
    slot_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider.provider_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Date and time
    slot_date = Column(Date, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    
    # Duration in minutes
    duration_minutes = Column(Integer, default=30, nullable=False)
    
    # Status
    status = Column(String(20), default="available", nullable=False)
    
    # If booked, link to appointment
    appointment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("appointment.appointment_id"),
        nullable=True
    )
    
    # Location
    location = Column(String(255), nullable=True)
    room = Column(String(50), nullable=True)
    
    # Blocking info (if status is 'blocked')
    block_reason = Column(String(255), nullable=True)
    blocked_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Hold info (if status is 'held')
    held_until = Column(DateTime, nullable=True)
    held_by_session = Column(String(100), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    provider = relationship("Provider", back_populates="time_slots")
    tenant = relationship("Tenant")
    appointment = relationship("Appointment")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "slot_id": str(self.slot_id),
            "provider_id": str(self.provider_id),
            "slot_date": self.slot_date.isoformat() if self.slot_date else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "appointment_id": str(self.appointment_id) if self.appointment_id else None,
            "location": self.location,
            "room": self.room,
            "block_reason": self.block_reason,
        }


class ScheduleException(Base):
    """
    Schedule exceptions (time off, holidays, blocked time).
    
    Overrides the regular ProviderSchedule for specific dates/times.
    """
    
    __tablename__ = "schedule_exception"
    
    exception_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider_id = Column(
        UUID(as_uuid=True),
        ForeignKey("provider.provider_id"),
        nullable=True  # Null = applies to all providers (e.g., holiday)
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Exception type
    exception_type = Column(String(50), nullable=False)  # "time_off", "holiday", "meeting", "blocked"
    
    # Date range
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    
    # Time range (null = all day)
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    
    # Description
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # Recurring (for regular meetings, etc.)
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_pattern = Column(JSONB, nullable=True)  # {"frequency": "weekly", "days": [1, 3]}
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by = Column(UUID(as_uuid=True), nullable=True)
    
    # Relationships
    provider = relationship("Provider")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "exception_id": str(self.exception_id),
            "provider_id": str(self.provider_id) if self.provider_id else None,
            "exception_type": self.exception_type,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "title": self.title,
            "description": self.description,
            "is_recurring": self.is_recurring,
        }
