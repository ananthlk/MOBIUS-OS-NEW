"""
ProceedDecisionAgent - Decides the proceed indicator color.

Computes: grey / green / yellow / blue / red
Based on: payment probability data (populated by batch job)

Thresholds:
- GREEN: >= 85% payment probability
- YELLOW: 60-84% payment probability
- RED: < 60% payment probability
- GREY: No probability data available
- BLUE: Additional information available (override)
"""

from typing import Any, Optional
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
    ProceedIndicator,
)


# Short actionable summaries for Mini display (LLM-ready for future)
ACTIONABLE_SUMMARIES = {
    "eligibility": {
        "low": "Verify eligibility",
        "medium": "Check eligibility",
        "high": "Eligible",
    },
    "coverage": {
        "low": "Verify coverage",
        "medium": "Check coverage",
        "high": "Covered",
    },
    "attendance": {
        "low": "Confirm appointment",
        "medium": "Confirm attendance",
        "high": "Confirmed",
    },
    "errors": {
        "low": "Review billing",
        "medium": "Check billing",
        "high": "No issues",
    },
}


class ProceedDecisionAgent(BaseDecisionAgent):
    """
    Decides the proceed indicator based on payment probability.
    
    Logic:
    - GREEN: >= 85% payment probability
    - YELLOW: 60-84% payment probability  
    - RED: < 60% payment probability
    - GREY: No probability data
    - BLUE: Additional info available (policy override)
    """
    
    @property
    def name(self) -> str:
        return "ProceedDecisionAgent"
    
    def get_default_decision(self) -> ProceedIndicator:
        return ProceedIndicator.GREY
    
    def validate_context(self, context: DecisionContext) -> bool:
        """Require tenant_id; patient_key is optional (returns grey if missing)."""
        return context.tenant_id is not None
    
    def _compute_decision(self, context: DecisionContext) -> ProceedIndicator:
        """
        Compute proceed indicator based on payment probability.
        
        Thresholds:
        - GREEN: >= 85%
        - YELLOW: 60-84%
        - RED: < 60%
        """
        # No patient = grey
        if not context.patient_key:
            return ProceedIndicator.GREY
        
        # Check policy overrides first
        if context.policy_config:
            forced = context.policy_config.get("force_proceed_indicator")
            if forced:
                return ProceedIndicator(forced)
        
        # Check for additional info available (blue override from snapshot)
        if context.patient_snapshot:
            if context.patient_snapshot.get("additional_info_available"):
                return ProceedIndicator.BLUE
        
        # Get payment probability
        prob = context.payment_probability
        
        if not prob:
            # Fallback to snapshot-based logic if no probability data
            return self._fallback_snapshot_logic(context)
        
        overall = prob.get("overall_probability", 0)
        
        # Apply thresholds
        if overall >= 0.85:
            return ProceedIndicator.GREEN
        elif overall >= 0.60:
            return ProceedIndicator.YELLOW
        else:
            return ProceedIndicator.RED
    
    def _fallback_snapshot_logic(self, context: DecisionContext) -> ProceedIndicator:
        """
        Fallback to original snapshot-based logic when no probability data.
        Used during transition period before batch job populates probability table.
        """
        if not context.patient_snapshot:
            return ProceedIndicator.GREY
        
        snapshot = context.patient_snapshot
        
        # Check for critical flags (red)
        if snapshot.get("critical_alert"):
            return ProceedIndicator.RED
        
        # Check for warnings (yellow)
        if snapshot.get("warnings") or snapshot.get("needs_review"):
            return ProceedIndicator.YELLOW
        
        # All clear = green
        if snapshot.get("verified") or snapshot.get("data_complete"):
            return ProceedIndicator.GREEN
        
        return ProceedIndicator.GREY
    
    def get_reasoning(self, context: DecisionContext, decision: ProceedIndicator) -> str:
        """
        Generate short actionable summary for the proceed decision.
        
        Uses payment probability's lowest_factor to provide actionable guidance.
        """
        prob = context.payment_probability
        
        if not prob:
            # Short fallback reasons
            fallback_reasons = {
                ProceedIndicator.GREY: "Awaiting data",
                ProceedIndicator.GREEN: "Ready",
                ProceedIndicator.YELLOW: "Review needed",
                ProceedIndicator.BLUE: "Info available",
                ProceedIndicator.RED: "Issue detected",
            }
            return fallback_reasons.get(decision, "Unknown")
        
        overall = prob.get("overall_probability", 0)
        
        # Green = ready with percentage
        if decision == ProceedIndicator.GREEN:
            return f"Ready ({int(overall * 100)}%)"
        
        # For yellow/red, use lowest factor to provide actionable message
        lowest_factor = prob.get("lowest_factor", "eligibility")
        
        # Get the factor's probability to determine severity
        factor_key = f"prob_{lowest_factor}"
        factor_prob = prob.get(factor_key, 0.5)
        
        # Determine level: low (<50%), medium (50-79%), high (>=80%)
        if factor_prob < 0.50:
            level = "low"
        elif factor_prob < 0.80:
            level = "medium"
        else:
            level = "high"
        
        # Get actionable message
        factor_messages = ACTIONABLE_SUMMARIES.get(lowest_factor, {})
        message = factor_messages.get(level)
        
        if not message:
            # Short fallback
            return "Review required"
        
        return message
    
    def get_confidence(self, context: DecisionContext, decision: ProceedIndicator) -> float:
        """
        Calculate confidence based on payment probability confidence.
        """
        prob = context.payment_probability
        
        if prob:
            return prob.get("confidence", 0.7)
        
        # Fallback confidence calculation
        if not context.patient_snapshot:
            return 0.5
        
        snapshot = context.patient_snapshot
        score = 0.6
        
        if snapshot.get("verified"):
            score += 0.2
        if snapshot.get("data_complete"):
            score += 0.2
        
        return min(score, 1.0)
