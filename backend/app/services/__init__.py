"""
Backend services for Mobius OS.

- SharedPatientStateCore: shared read/write operations for patient state
- EventLogService: append-only audit events
- ProjectionService: realtime Firestore projection updates
- AuthService: authentication and session management
- UserContextService: user profile hydration
- PersonalizationService: user-specific personalization
"""

from .patient_state import PatientStateService
from .event_log import EventLogService
from .projection import ProjectionService
from .auth_service import AuthService, get_auth_service
from .user_context import UserContextService, UserProfile, get_user_context_service
from .personalization import PersonalizationService, get_personalization_service

__all__ = [
    "PatientStateService",
    "EventLogService",
    "ProjectionService",
    # User Awareness Sprint
    "AuthService",
    "get_auth_service",
    "UserContextService",
    "UserProfile",
    "get_user_context_service",
    "PersonalizationService",
    "get_personalization_service",
]
