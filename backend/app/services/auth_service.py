"""
Authentication Service for User Awareness Sprint.

Handles:
- Email/password authentication
- JWT token generation and validation
- Session management
- OAuth token exchange (Google, Microsoft)
- User lookup and creation
"""

import uuid
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
import jwt
import bcrypt

from app.db.postgres import get_db_session
from app.models.tenant import AppUser, AuthProviderLink, UserSession, Tenant
from app.models.activity import Activity, UserActivity
from app.models.probability import UserPreference


# JWT Configuration
JWT_SECRET = "mobius-os-secret-key-change-in-production"  # TODO: Use environment variable
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7


class AuthService:
    """Service for handling user authentication."""
    
    def __init__(self):
        self.jwt_secret = JWT_SECRET
        self.jwt_algorithm = JWT_ALGORITHM
    
    # =========================================================================
    # Password Hashing
    # =========================================================================
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    # =========================================================================
    # JWT Token Management
    # =========================================================================
    
    def create_access_token(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
        """Create a short-lived access token."""
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "tenant_id": str(tenant_id),
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def create_refresh_token(self, user_id: uuid.UUID, session_id: uuid.UUID) -> str:
        """Create a long-lived refresh token."""
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),
            "session_id": str(session_id),
            "exp": expire,
            "type": "refresh",
        }
        return jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
    
    def decode_token(self, token: str) -> Optional[dict]:
        """Decode and validate a JWT token."""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def hash_refresh_token(self, refresh_token: str) -> str:
        """Hash refresh token for storage."""
        return hashlib.sha256(refresh_token.encode()).hexdigest()
    
    # =========================================================================
    # User Lookup
    # =========================================================================
    
    def get_user_by_email(self, email: str, tenant_id: uuid.UUID) -> Optional[AppUser]:
        """Find user by email within a tenant."""
        with get_db_session() as session:
            user = session.query(AppUser).filter(
                AppUser.email == email,
                AppUser.tenant_id == tenant_id,
                AppUser.status == "active"
            ).first()
            if user:
                session.expunge(user)
            return user
    
    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[AppUser]:
        """Find user by ID."""
        with get_db_session() as session:
            user = session.query(AppUser).filter(
                AppUser.user_id == user_id,
                AppUser.status == "active"
            ).first()
            if user:
                session.expunge(user)
            return user
    
    def get_user_by_provider(self, provider: str, provider_user_id: str) -> Optional[AppUser]:
        """Find user by OAuth provider ID."""
        with get_db_session() as session:
            link = session.query(AuthProviderLink).filter(
                AuthProviderLink.provider == provider,
                AuthProviderLink.provider_user_id == provider_user_id
            ).first()
            if link:
                user = session.query(AppUser).filter(
                    AppUser.user_id == link.user_id,
                    AppUser.status == "active"
                ).first()
                if user:
                    session.expunge(user)
                return user
            return None
    
    # =========================================================================
    # User Registration
    # =========================================================================
    
    def register_user(
        self,
        tenant_id: uuid.UUID,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        first_name: Optional[str] = None,
    ) -> Tuple[AppUser, str]:
        """Register a new user with email/password.
        
        Returns:
            Tuple of (user, error_message). Error is None on success.
        """
        with get_db_session() as session:
            # Check if email already exists
            existing = session.query(AppUser).filter(
                AppUser.email == email,
                AppUser.tenant_id == tenant_id
            ).first()
            if existing:
                return None, "Email already registered"
            
            # Create user
            user = AppUser(
                tenant_id=tenant_id,
                email=email,
                password_hash=self.hash_password(password),
                display_name=display_name or email.split('@')[0],
                first_name=first_name,
                status="active",
            )
            session.add(user)
            session.flush()  # Flush to get the user_id
            
            # Create auth provider link for email
            link = AuthProviderLink(
                user_id=user.user_id,
                provider="email",
                email=email,
            )
            session.add(link)
            
            session.commit()
            session.refresh(user)
            session.expunge(user)
            
            return user, None
    
    def create_user_from_oauth(
        self,
        tenant_id: uuid.UUID,
        provider: str,
        provider_user_id: str,
        email: str,
        display_name: Optional[str] = None,
        first_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> AppUser:
        """Create a new user from OAuth provider data."""
        with get_db_session() as session:
            # Check if user exists with this email
            existing = session.query(AppUser).filter(
                AppUser.email == email,
                AppUser.tenant_id == tenant_id
            ).first()
            
            if existing:
                # Link provider to existing user
                link = AuthProviderLink(
                    user_id=existing.user_id,
                    provider=provider,
                    provider_user_id=provider_user_id,
                    email=email,
                )
                session.add(link)
                session.commit()
                session.expunge(existing)
                return existing
            
            # Create new user
            user = AppUser(
                tenant_id=tenant_id,
                email=email,
                display_name=display_name or email.split('@')[0],
                first_name=first_name,
                avatar_url=avatar_url,
                status="active",
            )
            session.add(user)
            session.flush()
            
            # Create auth provider link
            link = AuthProviderLink(
                user_id=user.user_id,
                provider=provider,
                provider_user_id=provider_user_id,
                email=email,
            )
            session.add(link)
            
            session.commit()
            session.refresh(user)
            session.expunge(user)
            
            return user
    
    # =========================================================================
    # Authentication
    # =========================================================================
    
    def authenticate_email(
        self,
        email: str,
        password: str,
        tenant_id: uuid.UUID,
        device_info: Optional[dict] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """Authenticate user with email/password.
        
        Returns:
            Tuple of (auth_response, error_message)
        """
        with get_db_session() as session:
            user = session.query(AppUser).filter(
                AppUser.email == email,
                AppUser.tenant_id == tenant_id,
                AppUser.status == "active"
            ).first()
            
            if not user:
                return None, "Invalid email or password"
            
            if not user.password_hash:
                return None, "Account uses OAuth login"
            
            if not self.verify_password(password, user.password_hash):
                return None, "Invalid email or password"
            
            # Create session
            user_session = UserSession(
                user_id=user.user_id,
                device_info=device_info,
                expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
            )
            session.add(user_session)
            session.flush()
            
            # Generate tokens
            access_token = self.create_access_token(user.user_id, user.tenant_id)
            refresh_token = self.create_refresh_token(user.user_id, user_session.session_id)
            
            # Store refresh token hash
            user_session.refresh_token_hash = self.hash_refresh_token(refresh_token)
            
            # Update last login
            user.last_login_at = datetime.utcnow()
            
            session.commit()
            
            # Load user activities
            activities = []
            user_activities = session.query(UserActivity).filter(
                UserActivity.user_id == user.user_id
            ).all()
            
            for ua in user_activities:
                activity = session.query(Activity).filter(
                    Activity.activity_id == ua.activity_id
                ).first()
                if activity:
                    activities.append({
                        "activity_code": activity.activity_code,
                        "label": activity.label,
                        "is_primary": ua.is_primary,
                    })
            
            # Load user preference
            preference = session.query(UserPreference).filter(
                UserPreference.user_id == user.user_id
            ).first()
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                "user": {
                    "user_id": str(user.user_id),
                    "tenant_id": str(user.tenant_id),
                    "email": user.email,
                    "display_name": user.display_name,
                    "first_name": user.first_name,
                    "preferred_name": user.preferred_name,
                    "is_onboarded": user.is_onboarded,
                    "activities": activities,
                    "preference": {
                        "tone": preference.tone if preference else "professional",
                        "greeting_enabled": preference.greeting_enabled if preference else True,
                        "autonomy_routine_tasks": preference.autonomy_routine_tasks if preference else "confirm_first",
                        "autonomy_sensitive_tasks": preference.autonomy_sensitive_tasks if preference else "confirm_first",
                    } if preference else None,
                }
            }, None
    
    def refresh_access_token(self, refresh_token: str) -> Tuple[Optional[dict], Optional[str]]:
        """Refresh an access token using a refresh token.
        
        Returns:
            Tuple of (auth_response, error_message)
        """
        payload = self.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None, "Invalid refresh token"
        
        session_id = payload.get("session_id")
        user_id = payload.get("sub")
        
        if not session_id or not user_id:
            return None, "Invalid refresh token"
        
        with get_db_session() as session:
            user_session = session.query(UserSession).filter(
                UserSession.session_id == uuid.UUID(session_id),
                UserSession.user_id == uuid.UUID(user_id),
                UserSession.revoked_at.is_(None),
            ).first()
            
            if not user_session or not user_session.is_valid:
                return None, "Session expired or revoked"
            
            # Verify refresh token hash
            if user_session.refresh_token_hash != self.hash_refresh_token(refresh_token):
                return None, "Invalid refresh token"
            
            user = session.query(AppUser).filter(
                AppUser.user_id == uuid.UUID(user_id),
                AppUser.status == "active"
            ).first()
            
            if not user:
                return None, "User not found"
            
            # Generate new access token
            access_token = self.create_access_token(user.user_id, user.tenant_id)
            
            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            }, None
    
    def logout(self, refresh_token: str) -> bool:
        """Invalidate a session (logout)."""
        payload = self.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return False
        
        session_id = payload.get("session_id")
        if not session_id:
            return False
        
        with get_db_session() as session:
            user_session = session.query(UserSession).filter(
                UserSession.session_id == uuid.UUID(session_id)
            ).first()
            
            if user_session:
                user_session.revoked_at = datetime.utcnow()
                session.commit()
                return True
            
            return False
    
    # =========================================================================
    # User Context Validation
    # =========================================================================
    
    def validate_access_token(self, access_token: str) -> Optional[AppUser]:
        """Validate an access token and return the user."""
        payload = self.decode_token(access_token)
        if not payload or payload.get("type") != "access":
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        return self.get_user_by_id(uuid.UUID(user_id))
    
    def get_or_create_default_tenant(self) -> Tenant:
        """Get or create the default tenant for development."""
        with get_db_session() as session:
            tenant = session.query(Tenant).filter(
                Tenant.tenant_id == uuid.UUID("00000000-0000-0000-0000-000000000001")
            ).first()
            
            if not tenant:
                tenant = Tenant(
                    tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                    name="Default Tenant",
                )
                session.add(tenant)
                session.commit()
                session.refresh(tenant)
            
            session.expunge(tenant)
            return tenant


# Singleton instance
_auth_service = None

def get_auth_service() -> AuthService:
    """Get the singleton auth service instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service


def get_user_from_token(db, token: str) -> Optional[AppUser]:
    """
    Get user from access token. 
    
    Convenience function for route handlers that already have a db session.
    
    Args:
        db: SQLAlchemy session (unused, but matches pattern)
        token: JWT access token
        
    Returns:
        AppUser if valid token, None otherwise
    """
    auth_service = get_auth_service()
    return auth_service.validate_access_token(token)
