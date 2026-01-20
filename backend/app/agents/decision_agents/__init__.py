"""
Decision Agents Module.

All decision agents inherit from BaseDecisionAgent and follow
the same template pattern for consistent behavior.

Usage:
    from app.agents.decision_agents import DecisionOrchestrator
    
    orchestrator = DecisionOrchestrator()
    result = orchestrator.compute_all(context)
"""

# Base classes and enums
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
    ProceedIndicator,
    ExecutionMode,
    OutcomeStatus,
)

# Individual agents
from .proceed_agent import ProceedDecisionAgent
from .tasking_agent import TaskingDecisionAgent, TaskingDecision
from .execution_mode_agent import ExecutionModeDecisionAgent
from .outcome_agent import OutcomeComputationAgent
from .policy_agent import PolicyDecisionAgent, PolicyDecision
from .assignment_agent import AssignmentDecisionAgent, AssignmentDecision

# Orchestrator
from .orchestrator import DecisionOrchestrator, SystemResponse

__all__ = [
    # Base
    "BaseDecisionAgent",
    "DecisionContext",
    "DecisionResult",
    # Enums
    "ProceedIndicator",
    "ExecutionMode",
    "OutcomeStatus",
    # Agents
    "ProceedDecisionAgent",
    "TaskingDecisionAgent",
    "TaskingDecision",
    "ExecutionModeDecisionAgent",
    "OutcomeComputationAgent",
    "PolicyDecisionAgent",
    "PolicyDecision",
    "AssignmentDecisionAgent",
    "AssignmentDecision",
    # Orchestrator
    "DecisionOrchestrator",
    "SystemResponse",
]
