"""
PatientDataAgent - Manages patient data in the database.

Responsibilities:
- Create/update patient contexts and snapshots
- Seed sample data for development/testing
- Query patient data for decision agents
"""

import uuid
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session as DbSession

from app.db.postgres import get_db_session
from app.models.patient import PatientContext, PatientSnapshot
from app.models.patient_ids import PatientId
from app.models.tenant import Tenant, AppUser, Role


class PatientDataAgent:
    """
    Agent for managing patient data operations.
    
    This is a MODULE (not a decision agent) - it handles data operations,
    not decision-making.
    """
    
    def __init__(self, db_session: Optional[DbSession] = None):
        self._explicit_db = db_session  # Only set if explicitly passed
        self.logger = logging.getLogger("agent.PatientDataAgent")
    
    @property
    def db(self) -> DbSession:
        # Always get a fresh session from the scoped session factory
        # unless an explicit session was passed to the constructor.
        # This ensures we don't hold onto stale/invalid sessions.
        if self._explicit_db is not None:
            return self._explicit_db
        return get_db_session()
    
    # -------------------------------------------------------------------------
    # Read Operations
    # -------------------------------------------------------------------------
    
    def get_patient_context(
        self, tenant_id: uuid.UUID, patient_key: str
    ) -> Optional[PatientContext]:
        """Get patient context by tenant + patient_key.
        
        Also resolves by MRN if patient_key looks like an MRN (e.g., MRN-12345678).
        """
        # First try direct patient_key lookup
        context = (
            self.db.query(PatientContext)
            .filter(
                PatientContext.tenant_id == tenant_id,
                PatientContext.patient_key == patient_key,
            )
            .first()
        )
        
        if context:
            return context
        
        # If not found and key looks like an MRN, try resolving via patient_ids
        if patient_key.upper().startswith("MRN-") or patient_key.upper().startswith("MRN"):
            patient_id_record = (
                self.db.query(PatientId)
                .filter(
                    PatientId.id_type == "mrn",
                    PatientId.id_value == patient_key,
                )
                .first()
            )
            
            if patient_id_record:
                context = (
                    self.db.query(PatientContext)
                    .filter(
                        PatientContext.tenant_id == tenant_id,
                        PatientContext.patient_context_id == patient_id_record.patient_context_id,
                    )
                    .first()
                )
                if context:
                    self.logger.debug(f"Resolved MRN {patient_key} to patient_key {context.patient_key}")
                    return context
        
        return None
    
    def get_latest_snapshot(
        self, patient_context_id: uuid.UUID
    ) -> Optional[PatientSnapshot]:
        """Get the latest patient snapshot for a context."""
        return (
            self.db.query(PatientSnapshot)
            .filter(PatientSnapshot.patient_context_id == patient_context_id)
            .order_by(PatientSnapshot.snapshot_version.desc())
            .first()
        )
    
    def get_patient_snapshot_by_key(
        self, tenant_id: uuid.UUID, patient_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get patient snapshot as a dictionary (for decision agents).
        
        Returns None if patient not found.
        """
        context = self.get_patient_context(tenant_id, patient_key)
        if not context:
            return None
        
        snapshot = self.get_latest_snapshot(context.patient_context_id)
        if not snapshot:
            return None
        
        return snapshot.to_dict()
    
    def search_patients(
        self, tenant_id: uuid.UUID, query: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search patients by name or ID.
        
        Returns list of patient summaries for search results.
        """
        # Get all patient contexts for tenant
        contexts = (
            self.db.query(PatientContext)
            .filter(PatientContext.tenant_id == tenant_id)
            .all()
        )
        
        results = []
        query_lower = query.lower()
        
        for ctx in contexts:
            snapshot = self.get_latest_snapshot(ctx.patient_context_id)
            if not snapshot:
                continue
            
            # Check if query matches name or patient_key
            name_match = snapshot.display_name and query_lower in snapshot.display_name.lower()
            key_match = query_lower in ctx.patient_key.lower()
            
            if name_match or key_match:
                results.append({
                    "patient_key": ctx.patient_key,
                    "name": snapshot.display_name,
                    "id": ctx.patient_key,
                    "id_masked": snapshot.id_masked,
                })
            
            if len(results) >= limit:
                break
        
        return results
    
    # -------------------------------------------------------------------------
    # Write Operations
    # -------------------------------------------------------------------------
    
    def create_or_update_patient(
        self,
        tenant_id: uuid.UUID,
        patient_key: str,
        display_name: str,
        id_label: str = "MRN",
        id_masked: Optional[str] = None,
        dob: Optional[date] = None,
        verified: bool = False,
        data_complete: bool = False,
        critical_alert: bool = False,
        needs_review: bool = False,
        warnings: Optional[List[str]] = None,
        additional_info_available: bool = False,
        extended_data: Optional[Dict] = None,
        source: str = "api",
        created_by: Optional[str] = None,
    ) -> PatientSnapshot:
        """
        Create or update a patient with a new snapshot.
        
        If patient_context exists, creates a new snapshot version.
        If not, creates both context and snapshot.
        """
        # Get or create patient context
        context = self.get_patient_context(tenant_id, patient_key)
        
        if not context:
            context = PatientContext(
                tenant_id=tenant_id,
                patient_key=patient_key,
            )
            self.db.add(context)
            self.db.flush()  # Get the ID
            self.logger.info(f"Created new patient context: {patient_key}")
        
        # Determine snapshot version
        latest = self.get_latest_snapshot(context.patient_context_id)
        next_version = (latest.snapshot_version + 1) if latest else 1
        
        # Generate masked ID if not provided
        if not id_masked:
            id_masked = f"****{patient_key[-4:]}" if len(patient_key) >= 4 else f"****{patient_key}"
        
        # Create new snapshot
        snapshot = PatientSnapshot(
            patient_context_id=context.patient_context_id,
            snapshot_version=next_version,
            display_name=display_name,
            id_label=id_label,
            id_masked=id_masked,
            dob=dob,
            verified=verified,
            data_complete=data_complete,
            critical_alert=critical_alert,
            needs_review=needs_review,
            additional_info_available=additional_info_available,
            warnings=warnings,
            extended_data=extended_data,
            source=source,
            created_by=created_by,
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        
        self.logger.info(f"Created snapshot v{next_version} for patient: {patient_key}")
        return snapshot
    
    # -------------------------------------------------------------------------
    # Seed Data
    # -------------------------------------------------------------------------
    
    def seed_sample_patients(self, tenant_id: uuid.UUID) -> List[PatientSnapshot]:
        """
        Seed sample patient data for development/testing.
        
        Creates the standard test patients used in the system.
        """
        sample_patients = [
            {
                "patient_key": "1234567890",
                "display_name": "Jane Doe",
                "id_label": "MRN",
                "verified": True,
                "data_complete": True,
                "critical_alert": False,
                "needs_review": False,
                "warnings": None,
            },
            {
                "patient_key": "9876543210",
                "display_name": "John Smith",
                "id_label": "MRN",
                "verified": True,
                "data_complete": True,
                "critical_alert": False,
                "needs_review": False,
                "warnings": ["Insurance verification pending", "Allergies need update"],
            },
            {
                "patient_key": "1234500000",
                "display_name": "Janet Doe",
                "id_label": "MRN",
                "verified": False,
                "data_complete": False,
                "critical_alert": False,
                "needs_review": True,
                "warnings": None,
            },
            {
                "patient_key": "5551200001",
                "display_name": "Jimmy Dean",
                "id_label": "MRN",
                "verified": False,
                "data_complete": False,
                "critical_alert": True,
                "needs_review": True,
                "warnings": ["Critical: Drug interaction alert"],
            },
            {
                "patient_key": "7778889999",
                "display_name": "Sarah Johnson",
                "id_label": "MRN",
                "verified": True,
                "data_complete": True,
                "critical_alert": False,
                "needs_review": False,
                "additional_info_available": True,
                "warnings": None,
            },
        ]
        
        created_snapshots = []
        
        for patient_data in sample_patients:
            try:
                snapshot = self.create_or_update_patient(
                    tenant_id=tenant_id,
                    source="seed",
                    created_by="PatientDataAgent.seed",
                    **patient_data,
                )
                created_snapshots.append(snapshot)
            except Exception as e:
                self.logger.error(f"Failed to create patient {patient_data['patient_key']}: {e}")
        
        self.logger.info(f"Seeded {len(created_snapshots)} patients for tenant {tenant_id}")
        return created_snapshots
    
    def ensure_default_tenant(self) -> Tenant:
        """
        Ensure a default tenant exists for development.
        
        Returns the default tenant.
        """
        default_tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        
        tenant = self.db.query(Tenant).filter(Tenant.tenant_id == default_tenant_id).first()
        
        if not tenant:
            tenant = Tenant(
                tenant_id=default_tenant_id,
                name="Default Tenant",
            )
            self.db.add(tenant)
            self.db.commit()
            self.db.refresh(tenant)
            self.logger.info("Created default tenant")
        
        return tenant
    
    def ensure_default_user(self, tenant_id: uuid.UUID) -> AppUser:
        """
        Ensure a default user exists for development.
        
        Returns the default user.
        """
        default_user_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
        
        user = self.db.query(AppUser).filter(AppUser.user_id == default_user_id).first()
        
        if not user:
            # First ensure we have a default role
            default_role = self.db.query(Role).filter(Role.name == "default").first()
            if not default_role:
                default_role = Role(name="default")
                self.db.add(default_role)
                self.db.flush()
            
            user = AppUser(
                user_id=default_user_id,
                tenant_id=tenant_id,
                role_id=default_role.role_id,
                email="dev@mobius.local",
                display_name="Development User",
                status="active",
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            self.logger.info("Created default user")
        
        return user
