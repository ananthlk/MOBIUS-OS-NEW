"""
ExecutionModeDecisionAgent - Decides the execution mode.

Computes: agentic / copilot / user_driven
Based on: task attributes (system capability, success rates, oversight needs)

Modes:
- AGENTIC: System has full authority (can do all tasks, high success rate, no oversight needed)
- COPILOT: System assists with supervision (can do tasks but low success rate OR needs oversight)
- USER_DRIVEN: System passive (cannot do tasks OR high-value tasks OR blocking tasks)
"""

from typing import Any, Dict, List, Optional
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
    ExecutionMode,
)


class ExecutionModeDecisionAgent(BaseDecisionAgent):
    """
    Decides the execution mode based on task attributes.
    
    Logic (task-driven):
    - AGENTIC: System CAN do all tasks + high success rate + no oversight needed
    - COPILOT: System CAN do tasks BUT (low success rate OR human-in-loop OR user wants oversight)
    - USER_DRIVEN: System CANNOT do task OR high-value tasks OR many tasks system can't handle
    """
    
    @property
    def name(self) -> str:
        return "ExecutionModeDecisionAgent"
    
    def get_default_decision(self) -> ExecutionMode:
        return ExecutionMode.COPILOT
    
    def validate_context(self, context: DecisionContext) -> bool:
        return context.tenant_id is not None
    
    def _compute_decision(self, context: DecisionContext) -> ExecutionMode:
        """
        Compute execution mode based on task attributes.
        
        Decision tree:
        1. Policy override? Use it.
        2. No pending tasks? AGENTIC (nothing to do).
        3. System cannot do tasks + (many OR high-value)? USER_DRIVEN.
        4. Has blocking tasks? USER_DRIVEN.
        5. Low success rate OR human-in-loop OR oversight required? COPILOT.
        6. Otherwise? AGENTIC.
        """
        # Check policy for forced mode
        if context.policy_config:
            forced_mode = context.policy_config.get("execution_mode")
            if forced_mode:
                try:
                    return ExecutionMode(forced_mode)
                except ValueError:
                    pass  # Invalid mode, continue with logic
            
            # Policy feature flags
            if context.policy_config.get("user_driven_only"):
                return ExecutionMode.USER_DRIVEN
        
        # Get task instances
        tasks = context.task_instances or []
        
        # No tasks = agentic (nothing blocking)
        if not tasks:
            return ExecutionMode.AGENTIC
        
        # Filter to pending tasks only
        pending = [t for t in tasks if t.get("status") == "pending"]
        
        if not pending:
            return ExecutionMode.AGENTIC
        
        # Categorize tasks
        system_cannot_do = []
        high_value_tasks = []
        blocking_tasks = []
        low_success_tasks = []
        needs_human_tasks = []
        needs_oversight_tasks = []
        
        for task in pending:
            template = task.get("template", {})
            
            # System cannot do this task
            if not template.get("can_system_execute", False):
                system_cannot_do.append(task)
            
            # High value task
            if template.get("value_tier") == "high":
                high_value_tasks.append(task)
            
            # Blocking task (from task_step or template)
            # Check if any step is blocking or template itself is blocking
            if task.get("is_blocking") or template.get("is_blocking"):
                blocking_tasks.append(task)
            
            # Low success rate
            success_rate = template.get("historical_success_rate")
            threshold = template.get("success_rate_threshold", 0.8)
            if success_rate is not None and success_rate < threshold:
                low_success_tasks.append(task)
            
            # Requires human in loop
            if template.get("requires_human_in_loop", False):
                needs_human_tasks.append(task)
            
            # Always requires oversight
            if template.get("always_requires_oversight", False):
                needs_oversight_tasks.append(task)
        
        # Check user preference for oversight
        user_wants_oversight = False
        if context.user_preference:
            user_wants_oversight = context.user_preference.get("always_require_oversight", False)
        
        # Decision logic
        
        # USER_DRIVEN: Has blocking tasks
        if blocking_tasks:
            return ExecutionMode.USER_DRIVEN
        
        # USER_DRIVEN: System cannot do AND (many tasks OR high-value)
        if system_cannot_do:
            if len(system_cannot_do) >= 2 or high_value_tasks:
                return ExecutionMode.USER_DRIVEN
        
        # COPILOT: Low success rate OR human-in-loop OR oversight required OR user preference
        if low_success_tasks or needs_human_tasks or needs_oversight_tasks or user_wants_oversight:
            return ExecutionMode.COPILOT
        
        # COPILOT: Has some tasks system can't do (but not many/high-value)
        if system_cannot_do:
            return ExecutionMode.COPILOT
        
        # AGENTIC: System can do all tasks with good success rate, no oversight needed
        return ExecutionMode.AGENTIC
    
    def get_reasoning(self, context: DecisionContext, decision: ExecutionMode) -> str:
        """Generate explanation for the execution mode decision."""
        reasons = {
            ExecutionMode.AGENTIC: "System can proceed automatically",
            ExecutionMode.COPILOT: "System ready - awaiting your approval",
            ExecutionMode.USER_DRIVEN: "Action required before proceeding",
        }
        return reasons.get(decision, "Unknown mode")
    
    def get_confidence(self, context: DecisionContext, decision: ExecutionMode) -> float:
        """Calculate confidence based on task data availability."""
        # Policy-driven = high confidence
        if context.policy_config and context.policy_config.get("execution_mode"):
            return 1.0
        
        # No tasks = high confidence (nothing to evaluate)
        if not context.task_instances:
            return 0.9
        
        # Task-driven = moderate-high confidence
        return 0.85
