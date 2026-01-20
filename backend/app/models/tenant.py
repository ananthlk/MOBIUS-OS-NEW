"""
Tenant, Role, User, Application, and Policy models (PRD §13.2.1-5).

Extended for User Awareness Sprint:
- AppUser: Added name, timezone, onboarding fields
- AuthProviderLink: Links external auth to Mobius accounts
- UserSession: Active user sessions
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
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
    """Application user table (PRD §13.2.3).
    
    Extended for User Awareness Sprint with:
    - password_hash: For email/password authentication
    - first_name, preferred_name: For personalized greetings
    - timezone, locale: For time-aware greetings
    - onboarding_completed_at: Track first-login completion
    - avatar_url: User avatar
    """

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
    
    # User Awareness fields
    password_hash = Column(String(255), nullable=True)  # For email/password auth
    first_name = Column(String(100), nullable=True)
    preferred_name = Column(String(100), nullable=True)  # What they want to be called
    timezone = Column(String(50), default="America/New_York", nullable=True)
    locale = Column(String(10), default="en-US", nullable=True)
    onboarding_completed_at = Column(DateTime, nullable=True)
    avatar_url = Column(String(500), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    role = relationship("Role", back_populates="users")
    auth_providers = relationship("AuthProviderLink", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    activities = relationship("UserActivity", back_populates="user", cascade="all, delete-orphan")
    preference = relationship("UserPreference", back_populates="user", uselist=False)
    
    @property
    def greeting_name(self) -> str:
        """Get the name to use in greetings (preferred_name > first_name > display_name)."""
        return self.preferred_name or self.first_name or self.display_name or "there"
    
    @property
    def is_onboarded(self) -> bool:
        """Check if user has completed onboarding."""
        return self.onboarding_completed_at is not None


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


# =============================================================================
# User Awareness Sprint - Auth Models
# =============================================================================

class AuthProviderLink(Base):
    """Links external auth providers to Mobius accounts.
    
    Supports multiple auth methods (OAuth, email, SSO) linking to the same user.
    """
    
    __tablename__ = "auth_provider_link"
    
    link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False
    )
    provider = Column(String(50), nullable=False)  # 'email', 'google', 'microsoft', 'okta'
    provider_user_id = Column(String(255), nullable=True)  # External ID from provider
    email = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("AppUser", back_populates="auth_providers")


class UserSession(Base):
    """Active user sessions for token management.
    
    Stores session info for JWT refresh token validation.
    """
    
    __tablename__ = "user_session"
    
    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("app_user.user_id", ondelete="CASCADE"),
        nullable=False
    )
    refresh_token_hash = Column(String(255), nullable=True)
    device_info = Column(JSONB, nullable=True)  # Browser, OS info
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("AppUser", back_populates="sessions")
    
    @property
    def is_valid(self) -> bool:
        """Check if session is still valid (not expired or revoked)."""
        if self.revoked_at:
            return False
        return datetime.utcnow() < self.expires_at
