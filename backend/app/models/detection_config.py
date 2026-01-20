"""
Detection Configuration Model for Patient Context Detection.

Stores tenant-configurable detection patterns for identifying patient
identifiers on webpages. Allows customization per domain/EMR system.

Patterns include:
- Data attribute patterns (e.g., data-patient-mrn)
- URL patterns (e.g., ?mrn=123, /patient/456)
- DOM text patterns (e.g., "MRN: 12345")
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.postgres import Base


class DetectionConfig(Base):
    """
    Tenant-configurable detection patterns for patient context detection.
    
    Each configuration can specify patterns for a specific domain or EMR system.
    Multiple configurations can exist per tenant, with priority determining
    which patterns are applied first.
    """

    __tablename__ = "detection_config"

    config_id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant.tenant_id"),
        nullable=False,
    )
    
    # Configuration name for easy identification
    name = Column(String(255), nullable=False)
    
    # Domain pattern to match (e.g., "*.epic.com", "emr.hospital.org")
    # Supports wildcards: * matches any subdomain
    domain_pattern = Column(String(255), nullable=False)
    
    # EMR system hint (e.g., "epic", "cerner", "athena", "custom")
    emr_system = Column(String(50), nullable=True)
    
    # Pattern definitions stored as JSON
    # Structure:
    # {
    #   "dataAttributes": [
    #     { "attr": "data-custom-mrn", "type": "mrn", "source": "custom" }
    #   ],
    #   "urlPatterns": [
    #     { "regex": "/chart/([0-9]+)", "type": "mrn" }
    #   ],
    #   "textPatterns": [
    #     { "regex": "Chart\\s*#[:\\s]*([A-Z0-9]+)", "type": "mrn" }
    #   ]
    # }
    patterns_json = Column(JSONB, nullable=False, default={})
    
    # Priority for pattern matching (higher = checked first)
    priority = Column(Integer, nullable=False, default=0)
    
    # Whether this configuration is active
    enabled = Column(Boolean, nullable=False, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Optional description/notes
    description = Column(String(1000), nullable=True)
    
    # Relationships
    tenant = relationship("Tenant", backref="detection_configs")
    
    __table_args__ = (
        # Index for fast lookups by tenant and domain
        Index('idx_detection_config_tenant', 'tenant_id'),
        Index('idx_detection_config_domain', 'domain_pattern'),
        Index('idx_detection_config_tenant_priority', 'tenant_id', 'priority'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "config_id": str(self.config_id),
            "tenant_id": str(self.tenant_id),
            "name": self.name,
            "domain_pattern": self.domain_pattern,
            "emr_system": self.emr_system,
            "patterns": self.patterns_json,
            "priority": self.priority,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "description": self.description,
        }
    
    def matches_domain(self, domain: str) -> bool:
        """
        Check if this configuration matches the given domain.
        
        Supports wildcard patterns:
        - "*.example.com" matches "sub.example.com", "deep.sub.example.com"
        - "example.com" matches only "example.com"
        """
        if not domain:
            return False
        
        pattern = self.domain_pattern.lower()
        domain = domain.lower()
        
        if pattern.startswith('*.'):
            # Wildcard pattern - match any subdomain
            suffix = pattern[2:]  # Remove "*."
            return domain == suffix or domain.endswith('.' + suffix)
        else:
            # Exact match
            return domain == pattern
    
    def __repr__(self):
        return f"<DetectionConfig {self.name} ({self.domain_pattern})>"
