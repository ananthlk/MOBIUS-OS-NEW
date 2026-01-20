"""
DecisionOrchestrator - Runs all decision agents and produces SystemResponse.

This is the main entry point for computing all decisions for a patient context.
It runs agents in the correct order and aggregates their results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from .base import DecisionContext, DecisionResult, ProceedIndicator, ExecutionMode, OutcomeStatus
from .proceed_agent import ProceedDecisionAgent
from .tasking_agent import TaskingDecisionAgent, TaskingDecision
from .execution_mode_agent import ExecutionModeDecisionAgent
from .outcome_agent import OutcomeComputationAgent
from .policy_agent import PolicyDecisionAgent, PolicyDecision
from .assignment_agent import AssignmentDecisionAgent, AssignmentDecision


@dataclass
class SystemResponse:
    """
    Aggregated system response from all decision agents.
    
    This is what gets stored in the system_response table
    and projected to Firestore for UI consumption.
    """
    
    # Core decisions
    proceed_indicator: ProceedIndicator
    execution_mode: ExecutionMode
    tasking: TaskingDecision
    outcome: OutcomeStatus
    policy: PolicyDecision
    assignment: Optional[AssignmentDecision]
    
    # Metadata
    computed_at: datetime = field(default_factory=datetime.utcnow)
    agent_versions: Dict[str, str] = field(default_factory=dict)
    
    # Individual agent results (for audit/debug)
    agent_results: Dict[str, DecisionResult] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "proceed_indicator": self.proceed_indicator.value,
            "execution_mode": self.execution_mode.value,
            "tasking": self.tasking.to_dict() if self.tasking else None,
            "tasking_summary": self.tasking.summary if self.tasking else "No tasks",
            "outcome": self.outcome.value,
            "policy": self.policy.to_dict() if self.policy else None,
            "assignment": self.assignment.to_dict() if self.assignment else None,
            "computed_at": self.computed_at.isoformat(),
            "agent_versions": self.agent_versions,
        }
    
    def to_mini_payload(self) -> Dict[str, Any]:
        """Convert to minimal payload for Mini surface."""
        tasking_text = self.tasking.summary if self.tasking else "No tasks"
        
        # Get actionable summary from ProceedDecisionAgent reasoning
        proceed_result = self.agent_results.get("ProceedDecisionAgent")
        proceed_text = proceed_result.reasoning if proceed_result else self._proceed_text()
        
        return {
            "proceed": {
                "indicator": self.proceed_indicator.value,
                "color": self.proceed_indicator.value,
                "text": proceed_text,
            },
            "tasking": {
                "text": tasking_text,
                "summary": tasking_text,  # Keep for backwards compatibility
                "needs_ack": self.tasking.needs_acknowledgement if self.tasking else False,
                "color": self._tasking_color(),
                "mode": self.execution_mode.value,  # agentic, copilot, user_driven
                "mode_text": self._mode_display_text(),  # Human-readable mode
            },
            "mode": self.execution_mode.value if self.policy and self.policy.show_execution_mode else None,
            "computed_at": self.computed_at.isoformat(),
        }
    
    def _mode_display_text(self) -> str:
        """Human-readable execution mode text for Mini."""
        mode_texts = {
            ExecutionMode.AGENTIC: "Automatic",
            ExecutionMode.COPILOT: "Needs approval",
            ExecutionMode.USER_DRIVEN: "Manual required",
        }
        return mode_texts.get(self.execution_mode, "")
    
    def to_sidecar_payload(self) -> Dict[str, Any]:
        """Convert to rich payload for Sidecar surface."""
        # Get actionable summary from ProceedDecisionAgent reasoning
        proceed_result = self.agent_results.get("ProceedDecisionAgent")
        proceed_text = proceed_result.reasoning if proceed_result else self._proceed_text()
        
        # Get mode reasoning from ExecutionModeAgent
        mode_result = self.agent_results.get("ExecutionModeDecisionAgent")
        mode_text = mode_result.reasoning if mode_result else None
        
        return {
            "proceed_indicator": self.proceed_indicator.value,
            "proceed_text": proceed_text,
            "execution_mode": self.execution_mode.value,
            "execution_mode_text": mode_text,
            "tasking": self.tasking.to_dict() if self.tasking else None,
            "outcome": self.outcome.value,
            "policy": self.policy.to_dict() if self.policy else None,
            "assignment": self.assignment.to_dict() if self.assignment and self.assignment.create_assignment else None,
            "computed_at": self.computed_at.isoformat(),
        }
    
    def _proceed_text(self) -> str:
        """Human-readable proceed text."""
        texts = {
            ProceedIndicator.GREY: "Not assessed",
            ProceedIndicator.GREEN: "Proceed",
            ProceedIndicator.YELLOW: "Review needed",
            ProceedIndicator.BLUE: "Info available",
            ProceedIndicator.RED: "Stop - Issue detected",
        }
        return texts.get(self.proceed_indicator, "Unknown")
    
    def _tasking_color(self) -> str:
        """Color for tasking based on priority."""
        if not self.tasking:
            return "grey"
        colors = {
            "high": "yellow",
            "medium": "blue",
            "low": "grey",
            "none": "grey",
        }
        return colors.get(self.tasking.priority, "grey")


class DecisionOrchestrator:
    """
    Orchestrates all decision agents to produce a complete SystemResponse.
    
    Agent execution order:
    1. PolicyDecisionAgent (provides config for other agents)
    2. ProceedDecisionAgent
    3. ExecutionModeDecisionAgent
    4. TaskingDecisionAgent
    5. OutcomeComputationAgent
    6. AssignmentDecisionAgent (may depend on outcome)
    """
    
    def __init__(self):
        self.logger = logging.getLogger("orchestrator")
        
        # Initialize all agents
        self.policy_agent = PolicyDecisionAgent()
        self.proceed_agent = ProceedDecisionAgent()
        self.mode_agent = ExecutionModeDecisionAgent()
        self.tasking_agent = TaskingDecisionAgent()
        self.outcome_agent = OutcomeComputationAgent()
        self.assignment_agent = AssignmentDecisionAgent()
        
        self.agents = [
            self.policy_agent,
            self.proceed_agent,
            self.mode_agent,
            self.tasking_agent,
            self.outcome_agent,
            self.assignment_agent,
        ]
    
    def compute_all(self, context: DecisionContext) -> SystemResponse:
        """
        Run all decision agents and aggregate results.
        
        Args:
            context: DecisionContext with all available data
            
        Returns:
            SystemResponse with all computed decisions
        """
        results: Dict[str, DecisionResult] = {}
        
        # Step 1: Policy first (enriches context for other agents)
        policy_result = self.policy_agent.compute(context)
        results[self.policy_agent.name] = policy_result
        policy: PolicyDecision = policy_result.decision
        
        # Enrich context with policy for other agents
        context.policy_config = policy.to_dict()
        
        # Step 2: Proceed indicator
        proceed_result = self.proceed_agent.compute(context)
        results[self.proceed_agent.name] = proceed_result
        proceed: ProceedIndicator = proceed_result.decision
        
        # Step 3: Execution mode
        mode_result = self.mode_agent.compute(context)
        results[self.mode_agent.name] = mode_result
        mode: ExecutionMode = mode_result.decision
        
        # Step 4: Tasking
        tasking_result = self.tasking_agent.compute(context)
        results[self.tasking_agent.name] = tasking_result
        tasking: TaskingDecision = tasking_result.decision
        
        # Step 5: Outcome
        outcome_result = self.outcome_agent.compute(context)
        results[self.outcome_agent.name] = outcome_result
        outcome: OutcomeStatus = outcome_result.decision
        
        # Step 6: Assignment (may use outcome)
        assignment_result = self.assignment_agent.compute(context)
        results[self.assignment_agent.name] = assignment_result
        assignment: AssignmentDecision = assignment_result.decision
        
        # Build aggregated response
        response = SystemResponse(
            proceed_indicator=proceed,
            execution_mode=mode,
            tasking=tasking,
            outcome=outcome,
            policy=policy,
            assignment=assignment if assignment.create_assignment else None,
            agent_versions={agent.name: "1.0" for agent in self.agents},
            agent_results=results,
        )
        
        self.logger.info(
            f"Computed SystemResponse: proceed={proceed.value}, "
            f"mode={mode.value}, outcome={outcome.value}"
        )
        
        return response
    
    def compute_for_mini(self, context: DecisionContext) -> Dict[str, Any]:
        """Compute and return Mini-optimized payload."""
        response = self.compute_all(context)
        return response.to_mini_payload()
    
    def compute_for_sidecar(self, context: DecisionContext) -> Dict[str, Any]:
        """Compute and return Sidecar-optimized payload."""
        response = self.compute_all(context)
        return response.to_sidecar_payload()
