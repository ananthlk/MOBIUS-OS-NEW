"""
Crosswalk Service for Patient ID Resolution.

Encapsulates the logic for resolving external patient identifiers
(MRN, insurance ID, etc.) to internal Mobius patient_context_id UUIDs.

Supports multiple resolution strategies:
1. Direct lookup in patient_ids table
2. Fallback to patient_key match in patient_context table
3. Fuzzy matching (configurable)
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from app.db.postgres import get_db_session
from app.models.patient_ids import PatientId
from app.models.patient import PatientContext, PatientSnapshot
from app.models.detection_config import DetectionConfig


@dataclass
class CrosswalkResult:
    """Result of a crosswalk resolution attempt."""
    found: bool
    patient_context_id: Optional[uuid.UUID] = None
    patient_key: Optional[str] = None
    display_name: Optional[str] = None
    id_masked: Optional[str] = None
    resolution_method: Optional[str] = None  # 'patient_ids', 'patient_key', 'fuzzy'
    all_ids: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "found": self.found,
            "patient_context_id": str(self.patient_context_id) if self.patient_context_id else None,
            "patient_key": self.patient_key,
            "display_name": self.display_name,
            "id_masked": self.id_masked,
            "resolution_method": self.resolution_method,
            "all_ids": self.all_ids,
        }


class CrosswalkService:
    """
    Service for resolving patient identifiers to internal Mobius IDs.
    
    Usage:
        service = CrosswalkService()
        result = service.resolve_patient(
            id_type="mrn",
            id_value="MRN-00123456",
            tenant_id=uuid.UUID("...")
        )
        if result.found:
            print(f"Found patient: {result.display_name}")
    """
    
    def __init__(self, db_session: Optional[DbSession] = None):
        self._db = db_session
        self.logger = logging.getLogger("service.CrosswalkService")
    
    @property
    def db(self) -> DbSession:
        if self._db is None:
            self._db = get_db_session()
        return self._db
    
    def resolve_patient(
        self,
        id_type: str,
        id_value: str,
        tenant_id: uuid.UUID,
        source_hint: Optional[str] = None
    ) -> CrosswalkResult:
        """
        Resolve a patient identifier to internal Mobius patient context.
        
        Resolution strategies (in order):
        1. Direct lookup in patient_ids table by id_type + id_value
        2. Fallback to patient_key match in patient_context table
        3. Partial/fuzzy matching (if enabled)
        
        Args:
            id_type: Type of identifier ('mrn', 'insurance', 'patient_key', etc.)
            id_value: The identifier value
            tenant_id: Tenant to search within
            source_hint: Optional hint about the source system (e.g., 'epic', 'cerner')
        
        Returns:
            CrosswalkResult with found=True if patient was found, False otherwise
        """
        self.logger.debug(f"Resolving patient: type={id_type}, value={id_value}, tenant={tenant_id}")
        
        # Strategy 1: Direct lookup in patient_ids table
        result = self._resolve_via_patient_ids(id_type, id_value, tenant_id, source_hint)
        if result.found:
            return result
        
        # Strategy 2: Try matching against patient_key directly
        if id_type in ('patient_key', 'unknown'):
            result = self._resolve_via_patient_key(id_value, tenant_id)
            if result.found:
                return result
        
        # Strategy 3: Try normalized MRN format
        if id_type == 'mrn':
            result = self._resolve_via_mrn_variants(id_value, tenant_id)
            if result.found:
                return result
        
        # Not found
        return CrosswalkResult(found=False)
    
    def _resolve_via_patient_ids(
        self,
        id_type: str,
        id_value: str,
        tenant_id: uuid.UUID,
        source_hint: Optional[str] = None
    ) -> CrosswalkResult:
        """Look up patient via patient_ids table."""
        query = self.db.query(PatientId).filter(
            PatientId.id_type == id_type,
            PatientId.id_value == id_value,
        )
        
        # Optionally filter by source system
        if source_hint:
            # Try with source hint first
            patient_id = query.filter(PatientId.source_system == source_hint).first()
            if not patient_id:
                # Fall back to any source
                patient_id = query.first()
        else:
            patient_id = query.first()
        
        if not patient_id:
            return CrosswalkResult(found=False)
        
        # Verify tenant match
        context = self.db.query(PatientContext).filter(
            PatientContext.patient_context_id == patient_id.patient_context_id,
            PatientContext.tenant_id == tenant_id,
        ).first()
        
        if not context:
            return CrosswalkResult(found=False)
        
        return self._build_result(context, 'patient_ids')
    
    def _resolve_via_patient_key(
        self,
        patient_key: str,
        tenant_id: uuid.UUID
    ) -> CrosswalkResult:
        """Look up patient via patient_context.patient_key."""
        context = self.db.query(PatientContext).filter(
            PatientContext.tenant_id == tenant_id,
            PatientContext.patient_key == patient_key,
        ).first()
        
        if not context:
            return CrosswalkResult(found=False)
        
        return self._build_result(context, 'patient_key')
    
    def _resolve_via_mrn_variants(
        self,
        id_value: str,
        tenant_id: uuid.UUID
    ) -> CrosswalkResult:
        """Try common MRN format variations."""
        # Normalize: remove common prefixes, leading zeros, etc.
        normalized_variants = [
            id_value,
            id_value.upper(),
            id_value.lower(),
        ]
        
        # Remove common prefixes
        prefixes = ['MRN-', 'MRN', 'PT-', 'PT', 'PAT-', 'PAT']
        for prefix in prefixes:
            if id_value.upper().startswith(prefix):
                normalized_variants.append(id_value[len(prefix):])
            # Also try adding the prefix
            normalized_variants.append(f"{prefix}{id_value}")
        
        # Remove leading zeros
        stripped = id_value.lstrip('0')
        if stripped != id_value:
            normalized_variants.append(stripped)
        
        # Try patient_key matching with variants
        for variant in set(normalized_variants):
            context = self.db.query(PatientContext).filter(
                PatientContext.tenant_id == tenant_id,
                PatientContext.patient_key == variant,
            ).first()
            
            if context:
                return self._build_result(context, 'fuzzy')
        
        return CrosswalkResult(found=False)
    
    def _build_result(
        self,
        context: PatientContext,
        resolution_method: str
    ) -> CrosswalkResult:
        """Build a CrosswalkResult from a PatientContext."""
        # Get latest snapshot for display info
        snapshot = self.db.query(PatientSnapshot).filter(
            PatientSnapshot.patient_context_id == context.patient_context_id
        ).order_by(PatientSnapshot.snapshot_version.desc()).first()
        
        # Get all IDs for this patient
        all_ids = self.db.query(PatientId).filter(
            PatientId.patient_context_id == context.patient_context_id
        ).all()
        
        return CrosswalkResult(
            found=True,
            patient_context_id=context.patient_context_id,
            patient_key=context.patient_key,
            display_name=snapshot.display_name if snapshot else None,
            id_masked=snapshot.id_masked if snapshot else None,
            resolution_method=resolution_method,
            all_ids=[pid.to_dict() for pid in all_ids] if all_ids else None,
        )
    
    def get_detection_configs(
        self,
        tenant_id: uuid.UUID,
        domain: Optional[str] = None
    ) -> List[DetectionConfig]:
        """
        Get detection configurations for a tenant, optionally filtered by domain.
        
        Returns configurations ordered by priority (highest first).
        """
        query = self.db.query(DetectionConfig).filter(
            DetectionConfig.tenant_id == tenant_id,
            DetectionConfig.enabled == True,
        ).order_by(DetectionConfig.priority.desc())
        
        configs = query.all()
        
        if domain:
            # Filter to only matching domains
            configs = [c for c in configs if c.matches_domain(domain)]
        
        return configs
    
    def get_merged_patterns(
        self,
        tenant_id: uuid.UUID,
        domain: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get merged pattern configuration for a domain.
        
        Merges all matching configurations in priority order.
        Returns None if no custom configurations exist.
        """
        configs = self.get_detection_configs(tenant_id, domain)
        
        if not configs:
            return None
        
        # Merge patterns from all matching configs (higher priority first)
        merged = {
            "dataAttributes": [],
            "urlPatterns": [],
            "textPatterns": [],
        }
        
        for config in configs:
            patterns = config.patterns_json or {}
            
            for key in merged:
                if key in patterns and isinstance(patterns[key], list):
                    merged[key].extend(patterns[key])
        
        return merged if any(merged.values()) else None


# Singleton instance for convenience
_crosswalk_service: Optional[CrosswalkService] = None


def get_crosswalk_service() -> CrosswalkService:
    """Get the singleton CrosswalkService instance."""
    global _crosswalk_service
    if _crosswalk_service is None:
        _crosswalk_service = CrosswalkService()
    return _crosswalk_service
