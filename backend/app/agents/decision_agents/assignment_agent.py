"""
AssignmentDecisionAgent - Decides when/whom to assign for offline continuation.

Computes: assignment needed, assignee, priority, notification channel
Based on: outcome status, policy rules, user availability
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
    OutcomeStatus,
)


@dataclass
class AssignmentDecision:
    """Structured assignment decision."""
    
    # Whether assignment is needed
    create_assignment: bool = False
    
    # Assignment details (if create_assignment is True)
    assignee_user_id: Optional[str] = None
    assignee_role: Optional[str] = None  # Fallback if no specific user
    priority: str = "normal"  # "urgent", "high", "normal", "low"
    reason: str = ""
    
    # Notification
    notify: bool = False
    notification_channels: List[str] = field(default_factory=list)
    
    # Metadata
    due_by_minutes: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "create_assignment": self.create_assignment,
            "assignee_user_id": self.assignee_user_id,
            "assignee_role": self.assignee_role,
            "priority": self.priority,
            "reason": self.reason,
            "notify": self.notify,
            "notification_channels": self.notification_channels,
            "due_by_minutes": self.due_by_minutes,
            "tags": self.tags,
        }


class AssignmentDecisionAgent(BaseDecisionAgent):
    """
    Decides whether to create an assignment for offline continuation.
    
    Triggers:
    - Unacknowledged response past threshold
    - Critical alert not addressed
    - Policy-driven assignment rules
    
    Determines:
    - Who should receive the assignment
    - Priority level
    - Notification channels
    """
    
    @property
    def name(self) -> str:
        return "AssignmentDecisionAgent"
    
    def get_default_decision(self) -> AssignmentDecision:
        return AssignmentDecision()
    
    def validate_context(self, context: DecisionContext) -> bool:
        return context.tenant_id is not None
    
    def _compute_decision(self, context: DecisionContext) -> AssignmentDecision:
        """
        Compute whether assignment is needed and details.
        
        Phase 1: Simple rules based on outcome and policy.
        Future: ML-based routing, workload balancing.
        """
        decision = AssignmentDecision()
        
        # Get current outcome (from context or compute)
        response = context.latest_system_response
        submission = context.latest_submission
        
        if not response:
            return decision  # No response = no assignment needed
        
        # Check if already acknowledged
        if submission:
            submission_response_id = submission.get("system_response_id")
            response_id = response.get("id")
            if submission_response_id == response_id and not submission.get("dismissed"):
                return decision  # Already acknowledged
        
        # Check snapshot for critical alerts
        snapshot = context.patient_snapshot or {}
        
        # Critical alert = urgent assignment
        if snapshot.get("critical_alert"):
            decision.create_assignment = True
            decision.priority = "urgent"
            decision.reason = "Critical alert requires attention"
            decision.notify = True
            decision.notification_channels = ["in_app", "email"]
            decision.due_by_minutes = 15
            decision.tags = ["critical"]
        
        # Check policy for assignment rules
        if context.policy_config:
            policy = context.policy_config
            
            # Policy might force assignment creation
            if policy.get("auto_assign_unacknowledged"):
                # Check timeout
                unack_timeout = policy.get("unack_timeout_minutes", 30)
                # In real implementation, check response time vs now
                # For Phase 1, assume timeout logic is handled elsewhere
                decision.create_assignment = True
                decision.priority = "normal"
                decision.reason = "Unacknowledged response past threshold"
            
            # Default assignee from policy
            if decision.create_assignment:
                decision.assignee_role = policy.get("default_assignee_role", "supervisor")
                decision.notification_channels = policy.get("notification_channels", ["in_app"])
                decision.notify = policy.get("enable_notifications", True)
        
        return decision
    
    def get_reasoning(self, context: DecisionContext, decision: AssignmentDecision) -> str:
        if not decision.create_assignment:
            return "No assignment needed"
        return f"Assignment created: {decision.reason} (priority: {decision.priority})"
    
    def get_confidence(self, context: DecisionContext, decision: AssignmentDecision) -> float:
        if decision.priority == "urgent":
            return 1.0  # Critical = definite
        if context.policy_config:
            return 0.9  # Policy-driven
        return 0.7  # Inferred
