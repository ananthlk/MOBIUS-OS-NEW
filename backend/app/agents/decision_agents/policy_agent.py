"""
PolicyDecisionAgent - Decides UI/behavior based on tenant policy.

Computes: show/hide rules, UI variants, feature flags
Based on: tenant config, user role, application context
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
)


@dataclass
class PolicyDecision:
    """Structured policy decision for UI/behavior."""
    
    # Visibility
    show_mini: bool = True
    show_sidecar: bool = True
    show_proceed_indicator: bool = True
    show_tasking: bool = True
    show_execution_mode: bool = False  # Often hidden in Mini
    
    # Feature flags
    allow_override_proceed: bool = True
    allow_override_tasking: bool = True
    require_note_for_override: bool = True
    
    # Timeouts
    unack_timeout_minutes: int = 30
    session_timeout_minutes: int = 60
    
    # UI variants
    theme: str = "default"
    compact_mode: bool = False
    
    # Notification settings
    enable_notifications: bool = True
    notification_channels: List[str] = field(default_factory=lambda: ["in_app"])
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "show_mini": self.show_mini,
            "show_sidecar": self.show_sidecar,
            "show_proceed_indicator": self.show_proceed_indicator,
            "show_tasking": self.show_tasking,
            "show_execution_mode": self.show_execution_mode,
            "allow_override_proceed": self.allow_override_proceed,
            "allow_override_tasking": self.allow_override_tasking,
            "require_note_for_override": self.require_note_for_override,
            "unack_timeout_minutes": self.unack_timeout_minutes,
            "session_timeout_minutes": self.session_timeout_minutes,
            "theme": self.theme,
            "compact_mode": self.compact_mode,
            "enable_notifications": self.enable_notifications,
            "notification_channels": self.notification_channels,
        }


class PolicyDecisionAgent(BaseDecisionAgent):
    """
    Decides policy-driven configuration for the current context.
    
    Evaluates:
    - Tenant-level settings
    - Role-based overrides
    - Application-specific rules
    - Site/location rules (if applicable)
    
    Returns a PolicyDecision that UI and other agents can use.
    """
    
    @property
    def name(self) -> str:
        return "PolicyDecisionAgent"
    
    def get_default_decision(self) -> PolicyDecision:
        return PolicyDecision()
    
    def validate_context(self, context: DecisionContext) -> bool:
        return context.tenant_id is not None
    
    def _compute_decision(self, context: DecisionContext) -> PolicyDecision:
        """
        Compute policy settings based on tenant config and context.
        
        Phase 1: Load from policy_config if available, else defaults.
        Future: Complex rule evaluation with role/app/site overrides.
        """
        policy = PolicyDecision()
        
        # If no policy config loaded, return defaults
        if not context.policy_config:
            return policy
        
        config = context.policy_config
        
        # Visibility settings
        policy.show_mini = config.get("show_mini", policy.show_mini)
        policy.show_sidecar = config.get("show_sidecar", policy.show_sidecar)
        policy.show_proceed_indicator = config.get("show_proceed_indicator", policy.show_proceed_indicator)
        policy.show_tasking = config.get("show_tasking", policy.show_tasking)
        policy.show_execution_mode = config.get("show_execution_mode", policy.show_execution_mode)
        
        # Override permissions
        policy.allow_override_proceed = config.get("allow_override_proceed", policy.allow_override_proceed)
        policy.allow_override_tasking = config.get("allow_override_tasking", policy.allow_override_tasking)
        policy.require_note_for_override = config.get("require_note_for_override", policy.require_note_for_override)
        
        # Timeouts
        policy.unack_timeout_minutes = config.get("unack_timeout_minutes", policy.unack_timeout_minutes)
        policy.session_timeout_minutes = config.get("session_timeout_minutes", policy.session_timeout_minutes)
        
        # UI
        policy.theme = config.get("theme", policy.theme)
        policy.compact_mode = config.get("compact_mode", policy.compact_mode)
        
        # Notifications
        policy.enable_notifications = config.get("enable_notifications", policy.enable_notifications)
        policy.notification_channels = config.get("notification_channels", policy.notification_channels)
        
        # Role-based overrides (if user_id and role info available)
        if context.user_id:
            role_overrides = config.get("role_overrides", {})
            # In Phase 1, role would need to be looked up; for now, skip
        
        return policy
    
    def get_reasoning(self, context: DecisionContext, decision: PolicyDecision) -> str:
        if context.policy_config:
            return f"Policy loaded for tenant {context.tenant_id}"
        return f"Using default policy for tenant {context.tenant_id}"
    
    def get_confidence(self, context: DecisionContext, decision: PolicyDecision) -> float:
        if context.policy_config:
            return 1.0  # Explicit policy
        return 0.8  # Defaults
