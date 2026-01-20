"""
Messaging models for the Unified EMR.

These tables support:
1. Patient portal messages
2. Internal staff messages
3. Message threads
4. Message attachments
5. Task/action items from messages
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.db.postgres import Base


class MessageCategory(enum.Enum):
    """Category of message."""
    GENERAL = "general"
    CLINICAL = "clinical"
    PRESCRIPTION = "prescription"
    APPOINTMENT = "appointment"
    BILLING = "billing"
    REFERRAL = "referral"
    LAB_RESULTS = "lab_results"
    ADMIN = "admin"


class MessageThread(Base):
    """
    Message thread/conversation container.
    """
    
    __tablename__ = "message_thread"
    
    thread_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Associated patient (if patient-related)
    patient_context_id = Column(
        UUID(as_uuid=True),
        ForeignKey("patient_context.patient_context_id"),
        nullable=True
    )
    
    # Thread metadata
    subject = Column(String(500), nullable=False)
    category = Column(String(50), default="general", nullable=False)
    
    # Thread type: patient_portal, internal, system
    thread_type = Column(String(50), default="internal", nullable=False)
    
    # Priority
    priority = Column(String(20), default="normal", nullable=False)  # low, normal, high, urgent
    
    # Status
    status = Column(String(50), default="open", nullable=False)  # open, closed, archived
    
    # Assignment
    assigned_to_id = Column(UUID(as_uuid=True), nullable=True)
    assigned_to_name = Column(String(255), nullable=True)
    assigned_pool = Column(String(100), nullable=True)  # e.g., "Nursing", "Front Desk", "Billing"
    
    # Counts
    message_count = Column(Integer, default=0, nullable=False)
    unread_count = Column(Integer, default=0, nullable=False)
    
    # Last activity
    last_message_at = Column(DateTime, nullable=True)
    last_message_preview = Column(String(200), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    patient_context = relationship("PatientContext")
    messages = relationship("Message", back_populates="thread", order_by="Message.sent_at")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "thread_id": str(self.thread_id),
            "patient_context_id": str(self.patient_context_id) if self.patient_context_id else None,
            "subject": self.subject,
            "category": self.category,
            "thread_type": self.thread_type,
            "priority": self.priority,
            "status": self.status,
            "assigned_to_name": self.assigned_to_name,
            "assigned_pool": self.assigned_pool,
            "message_count": self.message_count,
            "unread_count": self.unread_count,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "last_message_preview": self.last_message_preview,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Message(Base):
    """
    Individual message within a thread.
    """
    
    __tablename__ = "message"
    
    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message_thread.thread_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Sender info
    sender_type = Column(String(50), nullable=False)  # patient, provider, staff, system
    sender_id = Column(UUID(as_uuid=True), nullable=True)
    sender_name = Column(String(255), nullable=False)
    
    # Message content
    body = Column(Text, nullable=False)
    body_html = Column(Text, nullable=True)  # Optional HTML version
    
    # Reply info
    reply_to_id = Column(UUID(as_uuid=True), ForeignKey("message.message_id"), nullable=True)
    
    # Read status (per recipient tracking would need separate table, this is simplified)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    
    # Attachments
    has_attachments = Column(Boolean, default=False, nullable=False)
    attachment_count = Column(Integer, default=0, nullable=False)
    
    # Message flags
    is_urgent = Column(Boolean, default=False, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)  # Provider-only visibility
    requires_response = Column(Boolean, default=False, nullable=False)
    
    # Auto-generated message info
    is_system_message = Column(Boolean, default=False, nullable=False)
    system_message_type = Column(String(50), nullable=True)  # appointment_reminder, lab_result, etc.
    
    # Timestamps
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    thread = relationship("MessageThread", back_populates="messages")
    tenant = relationship("Tenant")
    reply_to = relationship("Message", remote_side=[message_id])
    attachments = relationship("MessageAttachment", back_populates="message")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "message_id": str(self.message_id),
            "thread_id": str(self.thread_id),
            "sender_type": self.sender_type,
            "sender_name": self.sender_name,
            "body": self.body,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            "is_urgent": self.is_urgent,
            "is_private": self.is_private,
            "requires_response": self.requires_response,
            "is_system_message": self.is_system_message,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }


class MessageAttachment(Base):
    """
    File attachment on a message.
    """
    
    __tablename__ = "message_attachment"
    
    attachment_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message.message_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # File info
    filename = Column(String(255), nullable=False)
    file_type = Column(String(100), nullable=True)  # MIME type
    file_size = Column(Integer, nullable=True)  # bytes
    
    # Storage
    storage_path = Column(String(500), nullable=True)
    storage_bucket = Column(String(100), nullable=True)
    
    # Document type
    document_type = Column(String(50), nullable=True)  # image, pdf, lab_result, form, etc.
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    message = relationship("Message", back_populates="attachments")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "attachment_id": str(self.attachment_id),
            "message_id": str(self.message_id),
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "document_type": self.document_type,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class MessageRecipient(Base):
    """
    Recipient tracking for messages (for accurate read status per recipient).
    """
    
    __tablename__ = "message_recipient"
    
    recipient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message.message_id"),
        nullable=False
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Recipient info
    recipient_type = Column(String(50), nullable=False)  # patient, provider, staff, pool
    recipient_id_ref = Column(UUID(as_uuid=True), nullable=True)
    recipient_name = Column(String(255), nullable=True)
    recipient_pool = Column(String(100), nullable=True)  # For pool recipients
    
    # Recipient type
    recipient_role = Column(String(20), default="to", nullable=False)  # to, cc, bcc
    
    # Status
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    
    # Folder
    folder = Column(String(50), default="inbox", nullable=False)  # inbox, archive, deleted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    message = relationship("Message")
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "recipient_id": str(self.recipient_id),
            "message_id": str(self.message_id),
            "recipient_type": self.recipient_type,
            "recipient_name": self.recipient_name,
            "recipient_role": self.recipient_role,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "folder": self.folder,
        }


class MessageTemplate(Base):
    """
    Reusable message templates.
    """
    
    __tablename__ = "message_template"
    
    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False
    )
    
    # Template details
    name = Column(String(255), nullable=False)
    category = Column(String(50), nullable=True)
    
    # Content
    subject_template = Column(String(500), nullable=True)
    body_template = Column(Text, nullable=False)
    
    # Variables available
    available_variables = Column(JSONB, nullable=True)  # ["patient_name", "appointment_date"]
    
    # Usage
    is_active = Column(Boolean, default=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)  # System templates can't be deleted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "template_id": str(self.template_id),
            "name": self.name,
            "category": self.category,
            "subject_template": self.subject_template,
            "body_template": self.body_template,
            "available_variables": self.available_variables,
            "is_active": self.is_active,
            "is_system": self.is_system,
        }
