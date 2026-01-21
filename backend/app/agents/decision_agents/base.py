"""
Base Decision Agent - Template for all decision agents.

All decision agents inherit from this base and override specific methods.
This ensures a consistent interface and behavior across all agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import logging


# =============================================================================
# Enums for standardized decision values
# =============================================================================

class ProceedIndicator(str, Enum):
    """Proceed indicator colors (PRD §10.2).
    
    6 status colors:
    - GREEN: Ready / Good to go (>= 85% probability)
    - YELLOW: Caution / Review needed (60-84% probability)
    - RED: Critical issue / Action required (< 60% probability)
    - BLUE: System error (technical failure)
    - GREY: Not processed (no data available)
    - PURPLE: Policy override (admin forced status)
    """
    GREY = "grey"        # Not processed / no data
    GREEN = "green"      # Ready / Good to go
    YELLOW = "yellow"    # Caution / Review needed
    BLUE = "blue"        # System error
    RED = "red"          # Critical issue / Action required
    PURPLE = "purple"    # Policy override


class ExecutionMode(str, Enum):
    """Execution mode (PRD §10.2)."""
    AGENTIC = "agentic"          # System-driven
    COPILOT = "copilot"          # Collaborative
    USER_DRIVEN = "user_driven"  # Manual


class OutcomeStatus(str, Enum):
    """Outcome status (PRD §6.4)."""
    ACKNOWLEDGED = "acknowledged"
    UNACKNOWLEDGED = "unacknowledged"
    DISMISSED = "dismissed"
    INVALIDATED = "invalidated"
    PENDING = "pending"


# =============================================================================
# Data classes for context and results
# =============================================================================

@dataclass
class DecisionContext:
    """
    Context passed to all decision agents.
    
    Contains everything an agent might need to make a decision.
    Agents access only what they need.
    """
    
    # Required identifiers
    tenant_id: str
    
    # Optional identifiers
    patient_key: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    invocation_id: Optional[str] = None
    
    # Patient data
    patient_snapshot: Optional[Dict[str, Any]] = None
    patient_context: Optional[Dict[str, Any]] = None
    
    # Payment probability data (for ProceedDecisionAgent)
    payment_probability: Optional[Dict[str, Any]] = None
    
    # Task data (for TaskingDecisionAgent, ExecutionModeAgent)
    task_instances: List[Dict[str, Any]] = field(default_factory=list)
    
    # User preferences (for ExecutionModeAgent)
    user_preference: Optional[Dict[str, Any]] = None
    
    # System state
    latest_system_response: Optional[Dict[str, Any]] = None
    latest_submission: Optional[Dict[str, Any]] = None
    submission_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # Policy (loaded separately)
    policy_config: Optional[Dict[str, Any]] = None
    
    # Request-specific data
    request_data: Optional[Dict[str, Any]] = None
    
    # Timestamps
    request_time: datetime = field(default_factory=datetime.utcnow)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from context by key."""
        return getattr(self, key, default)


@dataclass
class DecisionResult:
    """
    Standardized result from any decision agent.
    """
    
    # The primary decision value
    decision: Any
    
    # Confidence score (0.0 to 1.0)
    confidence: float = 1.0
    
    # Human-readable reasoning (for audit/debug)
    reasoning: str = ""
    
    # Agent that made this decision
    agent_name: str = ""
    
    # Timestamp
    computed_at: datetime = field(default_factory=datetime.utcnow)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Warnings/notes
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision": self.decision.value if isinstance(self.decision, Enum) else self.decision,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "agent_name": self.agent_name,
            "computed_at": self.computed_at.isoformat(),
            "metadata": self.metadata,
            "warnings": self.warnings,
        }


# =============================================================================
# Base Decision Agent
# =============================================================================

class BaseDecisionAgent(ABC):
    """
    Base class for all decision agents.
    
    Decision agents:
    - COMPUTE values based on context
    - DO NOT write to databases (that's for modules)
    - Return standardized DecisionResult
    
    Subclasses must implement:
    - name: Agent identifier
    - compute(): The decision logic
    
    Subclasses may override:
    - validate_context(): Add specific validation
    - get_default_decision(): Default when computation fails
    - pre_compute(): Hook before computation
    - post_compute(): Hook after computation
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"agent.{self.name}")
    
    # -------------------------------------------------------------------------
    # Abstract methods (MUST implement)
    # -------------------------------------------------------------------------
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique agent name for logging and audit."""
        pass
    
    @abstractmethod
    def _compute_decision(self, context: DecisionContext) -> Any:
        """
        Core decision logic. Implement in subclass.
        
        Returns the decision value (will be wrapped in DecisionResult).
        """
        pass
    
    # -------------------------------------------------------------------------
    # Template method (DO NOT override)
    # -------------------------------------------------------------------------
    
    def compute(self, context: DecisionContext) -> DecisionResult:
        """
        Main entry point. Executes the decision pipeline.
        
        Pipeline:
        1. Validate context
        2. Pre-compute hook
        3. Compute decision
        4. Post-compute hook
        5. Return result
        
        DO NOT override this method. Override the hooks instead.
        """
        try:
            # Step 1: Validate
            if not self.validate_context(context):
                self.logger.warning(f"Invalid context for {self.name}")
                return self._make_result(
                    self.get_default_decision(),
                    confidence=0.0,
                    reasoning="Invalid context"
                )
            
            # Step 2: Pre-compute hook
            context = self.pre_compute(context)
            
            # Step 3: Compute
            decision = self._compute_decision(context)
            reasoning = self.get_reasoning(context, decision)
            confidence = self.get_confidence(context, decision)
            
            # Step 4: Post-compute hook
            result = self._make_result(decision, confidence, reasoning)
            result = self.post_compute(context, result)
            
            self.logger.info(f"{self.name} computed: {decision} (confidence={confidence})")
            return result
            
        except Exception as e:
            self.logger.error(f"{self.name} computation error: {e}")
            return self._make_result(
                self.get_default_decision(),
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                warnings=[str(e)]
            )
    
    # -------------------------------------------------------------------------
    # Hooks (MAY override)
    # -------------------------------------------------------------------------
    
    def validate_context(self, context: DecisionContext) -> bool:
        """
        Validate that required context is present.
        Override to add specific requirements.
        """
        return context.tenant_id is not None
    
    def get_default_decision(self) -> Any:
        """
        Return default decision when computation fails.
        Override in subclass.
        """
        return None
    
    def get_reasoning(self, context: DecisionContext, decision: Any) -> str:
        """
        Generate human-readable reasoning for the decision.
        Override to provide meaningful explanations.
        """
        return f"{self.name} computed {decision}"
    
    def get_confidence(self, context: DecisionContext, decision: Any) -> float:
        """
        Calculate confidence score for the decision.
        Override for sophisticated confidence calculation.
        """
        return 1.0
    
    def pre_compute(self, context: DecisionContext) -> DecisionContext:
        """
        Hook called before computation.
        Can modify/enrich context.
        """
        return context
    
    def post_compute(self, context: DecisionContext, result: DecisionResult) -> DecisionResult:
        """
        Hook called after computation.
        Can modify/enrich result.
        """
        return result
    
    # -------------------------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------------------------
    
    def _make_result(
        self,
        decision: Any,
        confidence: float = 1.0,
        reasoning: str = "",
        warnings: List[str] = None
    ) -> DecisionResult:
        """Create a DecisionResult with agent name populated."""
        return DecisionResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            agent_name=self.name,
            warnings=warnings or []
        )
