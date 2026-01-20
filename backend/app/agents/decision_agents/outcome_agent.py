"""
OutcomeComputationAgent - Computes derived outcomes.

Computes: Acknowledged / Unacknowledged / Dismissed / Invalidated / Pending
Based on: system responses, user submissions, time thresholds
"""

from datetime import datetime, timedelta
from typing import Any, Optional
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
    OutcomeStatus,
)


class OutcomeComputationAgent(BaseDecisionAgent):
    """
    Computes the outcome status for a patient context.
    
    Outcomes are derived from the relationship between:
    - System Response (what the system presented)
    - User Submission (what the user acknowledged)
    - Time (how long since response without acknowledgement)
    
    This agent COMPUTES outcomes; it does NOT store them.
    """
    
    # Default timeout before marking as unacknowledged (can be overridden by policy)
    DEFAULT_UNACK_TIMEOUT_MINUTES = 30
    
    @property
    def name(self) -> str:
        return "OutcomeComputationAgent"
    
    def get_default_decision(self) -> OutcomeStatus:
        return OutcomeStatus.PENDING
    
    def validate_context(self, context: DecisionContext) -> bool:
        return context.tenant_id is not None
    
    def _compute_decision(self, context: DecisionContext) -> OutcomeStatus:
        """
        Compute outcome based on response/submission state.
        
        Logic:
        - No response → PENDING
        - Response + valid submission → ACKNOWLEDGED
        - Response + no submission + within timeout → PENDING
        - Response + no submission + past timeout → UNACKNOWLEDGED
        - Response + dismissal submission → DISMISSED
        - Response invalidated by new response → INVALIDATED
        """
        response = context.latest_system_response
        submission = context.latest_submission
        
        # No response yet = pending
        if not response:
            return OutcomeStatus.PENDING
        
        response_id = response.get("id")
        response_time = response.get("computed_at")
        
        # Check if submission exists and references this response
        if submission:
            submission_response_id = submission.get("system_response_id")
            
            # Submission references a different (older) response = this response not acked
            if submission_response_id and submission_response_id != response_id:
                # The submission was for a previous response
                # This response needs its own ack
                pass
            else:
                # Submission matches this response
                # Check submission type
                if submission.get("dismissed"):
                    return OutcomeStatus.DISMISSED
                
                # Valid acknowledgement
                return OutcomeStatus.ACKNOWLEDGED
        
        # No submission - check timeout
        timeout_minutes = self.DEFAULT_UNACK_TIMEOUT_MINUTES
        if context.policy_config:
            timeout_minutes = context.policy_config.get(
                "unack_timeout_minutes", 
                self.DEFAULT_UNACK_TIMEOUT_MINUTES
            )
        
        # Calculate time since response
        if response_time:
            if isinstance(response_time, str):
                response_time = datetime.fromisoformat(response_time.replace("Z", "+00:00"))
            
            elapsed = datetime.utcnow() - response_time.replace(tzinfo=None)
            
            if elapsed > timedelta(minutes=timeout_minutes):
                return OutcomeStatus.UNACKNOWLEDGED
        
        # Within timeout, still pending
        return OutcomeStatus.PENDING
    
    def get_reasoning(self, context: DecisionContext, decision: OutcomeStatus) -> str:
        reasons = {
            OutcomeStatus.ACKNOWLEDGED: "User submitted valid acknowledgement",
            OutcomeStatus.UNACKNOWLEDGED: "Response not acknowledged within timeout",
            OutcomeStatus.DISMISSED: "User explicitly dismissed the response",
            OutcomeStatus.INVALIDATED: "Response superseded by newer response",
            OutcomeStatus.PENDING: "Awaiting user action",
        }
        return reasons.get(decision, "Unknown outcome")
    
    def get_confidence(self, context: DecisionContext, decision: OutcomeStatus) -> float:
        # Explicit actions = high confidence
        if decision in [OutcomeStatus.ACKNOWLEDGED, OutcomeStatus.DISMISSED]:
            return 1.0
        # Time-based = moderate confidence
        if decision == OutcomeStatus.UNACKNOWLEDGED:
            return 0.9
        # Pending = waiting
        return 0.7
