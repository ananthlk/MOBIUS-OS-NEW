"""
TaskingDecisionAgent - Decides tasking summary and flags.

Computes: tasking summary text, needs_acknowledgement flag
Based on: task_instances from database (populated by batch job)

Summary styles for Mini (does not list tasks, indicates mode):
- "System can proceed automatically" - all tasks agentic
- "System processing" - system tasks in progress
- "X action(s) need attention" - user tasks pending
- "Awaiting updates" - patient tasks or external
- "No actions required" - no pending tasks
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from .base import (
    BaseDecisionAgent,
    DecisionContext,
    DecisionResult,
)


@dataclass
class TaskingDecision:
    """Structured tasking decision."""
    summary: str
    tasks: List[str]
    needs_acknowledgement: bool
    priority: str  # "high", "medium", "low", "none"
    
    # Additional details for Sidecar
    user_task_count: int = 0
    system_task_count: int = 0
    patient_task_count: int = 0
    blocking_task_count: int = 0
    
    def to_dict(self):
        return {
            "summary": self.summary,
            "tasks": self.tasks,
            "needs_acknowledgement": self.needs_acknowledgement,
            "priority": self.priority,
            "user_task_count": self.user_task_count,
            "system_task_count": self.system_task_count,
            "patient_task_count": self.patient_task_count,
            "blocking_task_count": self.blocking_task_count,
        }


class TaskingDecisionAgent(BaseDecisionAgent):
    """
    Decides the tasking summary based on task_instances.
    
    Reads tasks from context.task_instances and provides:
    - Summary text for Mini (mode indicator, not task list)
    - Task list for Sidecar
    - Priority and acknowledgement flags
    """
    
    @property
    def name(self) -> str:
        return "TaskingDecisionAgent"
    
    def get_default_decision(self) -> TaskingDecision:
        return TaskingDecision(
            summary="No actions required",
            tasks=[],
            needs_acknowledgement=False,
            priority="none"
        )
    
    def validate_context(self, context: DecisionContext) -> bool:
        return context.tenant_id is not None
    
    def _compute_decision(self, context: DecisionContext) -> TaskingDecision:
        """
        Compute tasking based on task_instances from database.
        
        Falls back to snapshot-based logic if no task_instances.
        """
        tasks_data = context.task_instances or []
        
        # If no task instances, try fallback to snapshot-based logic
        if not tasks_data:
            return self._fallback_snapshot_logic(context)
        
        # Filter to pending tasks
        pending = [t for t in tasks_data if t.get("status") == "pending"]
        
        if not pending:
            return self.get_default_decision()
        
        # Categorize by assigned actor type
        user_tasks = []
        system_tasks = []
        patient_tasks = []
        blocking_tasks = []
        
        task_names = []
        
        for task in pending:
            template = task.get("template", {})
            task_name = template.get("task_name", "Unknown task")
            task_names.append(task_name)
            
            assigned_to = task.get("assigned_to_type", "user")
            
            if assigned_to == "user" or assigned_to == "role":
                user_tasks.append(task)
            elif assigned_to == "system":
                system_tasks.append(task)
            elif assigned_to == "patient":
                patient_tasks.append(task)
            
            # Check if blocking
            if task.get("is_blocking") or template.get("is_blocking"):
                blocking_tasks.append(task)
        
        # Determine priority based on blocking status and assignment
        if blocking_tasks:
            priority = "high"
        elif user_tasks:
            priority = "medium"
        else:
            priority = "low"
        
        # Build Mini summary (mode indicator, not task list)
        summary = self._build_summary(
            pending=pending,
            user_tasks=user_tasks,
            system_tasks=system_tasks,
            patient_tasks=patient_tasks
        )
        
        # Needs acknowledgement if user tasks exist
        needs_ack = len(user_tasks) > 0
        
        return TaskingDecision(
            summary=summary,
            tasks=task_names,
            needs_acknowledgement=needs_ack,
            priority=priority,
            user_task_count=len(user_tasks),
            system_task_count=len(system_tasks),
            patient_task_count=len(patient_tasks),
            blocking_task_count=len(blocking_tasks),
        )
    
    def _build_summary(
        self,
        pending: List[Dict],
        user_tasks: List[Dict],
        system_tasks: List[Dict],
        patient_tasks: List[Dict]
    ) -> str:
        """
        Build Mini summary based on task breakdown.
        
        Summary indicates mode/status, not specific tasks.
        """
        if not pending:
            return "No actions required"
        
        # All tasks are system tasks = system processing
        if system_tasks and not user_tasks and not patient_tasks:
            return "System processing"
        
        # All tasks can be done by system with no user tasks
        all_can_be_agentic = all(
            t.get("template", {}).get("can_system_execute", False) 
            for t in pending
        )
        if all_can_be_agentic and not user_tasks:
            return "System can proceed automatically"
        
        # User tasks need attention
        if user_tasks:
            count = len(user_tasks)
            return f"{count} action{'s' if count > 1 else ''} need{'s' if count == 1 else ''} attention"
        
        # Patient tasks or other external
        if patient_tasks:
            return "Awaiting patient response"
        
        return "Awaiting updates"
    
    def _fallback_snapshot_logic(self, context: DecisionContext) -> TaskingDecision:
        """
        Fallback to snapshot-based task inference when no task_instances.
        Used during transition before batch job populates task tables.
        """
        tasks = []
        needs_ack = False
        priority = "none"
        
        if not context.patient_key:
            return self.get_default_decision()
        
        snapshot = context.patient_snapshot or {}
        
        # Check for pending verifications
        if not snapshot.get("verified"):
            tasks.append("Verify patient identity")
            needs_ack = True
            priority = "medium"
        
        # Check for incomplete data
        if not snapshot.get("data_complete"):
            tasks.append("Complete patient data")
            priority = "medium" if priority == "none" else priority
        
        # Check for warnings
        if snapshot.get("warnings"):
            tasks.append("Review warnings")
            needs_ack = True
            priority = "high"
        
        # Check for critical alerts
        if snapshot.get("critical_alert"):
            tasks.append("Address critical alert")
            needs_ack = True
            priority = "high"
        
        # Check policy for forced tasks
        if context.policy_config:
            forced_tasks = context.policy_config.get("required_tasks", [])
            tasks.extend(forced_tasks)
            if forced_tasks:
                needs_ack = True
        
        # Build summary
        if not tasks:
            summary = "No actions required"
        elif len(tasks) == 1:
            summary = tasks[0]
        else:
            summary = f"{len(tasks)} actions need attention"
        
        return TaskingDecision(
            summary=summary,
            tasks=tasks,
            needs_acknowledgement=needs_ack,
            priority=priority
        )
    
    def get_reasoning(self, context: DecisionContext, decision: TaskingDecision) -> str:
        if not decision.tasks:
            return "No tasks identified for this patient context"
        
        parts = []
        if decision.user_task_count:
            parts.append(f"{decision.user_task_count} user task(s)")
        if decision.system_task_count:
            parts.append(f"{decision.system_task_count} system task(s)")
        if decision.patient_task_count:
            parts.append(f"{decision.patient_task_count} patient task(s)")
        
        if parts:
            return f"Identified {len(decision.tasks)} task(s): {', '.join(parts)}"
        return f"Identified {len(decision.tasks)} task(s)"
    
    def get_confidence(self, context: DecisionContext, decision: TaskingDecision) -> float:
        # Higher confidence with task_instances data
        if context.task_instances:
            return 0.9
        # Lower confidence with fallback logic
        if context.patient_snapshot:
            return 0.7
        return 0.5
