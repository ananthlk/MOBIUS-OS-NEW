"""
Tenant, Role, User, Application, and Policy models (PRD §13.2.1-5).
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class Tenant(Base):
    """Tenant table (PRD §13.2.1)."""

    __tablename__ = "tenant"

    tenant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    users = relationship("AppUser", back_populates="tenant")
    policies = relationship("PolicyConfig", back_populates="tenant")


class Role(Base):
    """Role table (PRD §13.2.2)."""

    __tablename__ = "role"

    role_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    users = relationship("AppUser", back_populates="role")


class AppUser(Base):
    """Application user table (PRD §13.2.3)."""

    __tablename__ = "app_user"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), nullable=False
    )
    role_id = Column(UUID(as_uuid=True), ForeignKey("role.role_id"), nullable=True)
    email = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    status = Column(String(50), default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    role = relationship("Role", back_populates="users")


class Application(Base):
    """Application table (PRD §13.2.4)."""

    __tablename__ = "application"

    application_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PolicyConfig(Base):
    """Policy configuration table (PRD §13.2.5)."""

    __tablename__ = "policy_config"

    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenant.tenant_id"), primary_key=True
    )
    version = Column(String(50), primary_key=True)
    allowlist_rules_json = Column(JSONB, nullable=True)
    ui_variants_json = Column(JSONB, nullable=True)
    timeout_rules_json = Column(JSONB, nullable=True)
    notification_rules_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    tenant = relationship("Tenant", back_populates="policies")
