"""
Sidecar State Service

Computes the full sidecar state response for the UI.
Aggregates data from multiple sources:
- PaymentProbability -> care_readiness
- ResolutionPlan/PlanStep -> bottlenecks
- Milestone -> milestones
- UserAlert -> alerts
- UserOwnedTask -> user_owned_tasks
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import (
    PatientContext,
    PaymentProbability,
    ResolutionPlan,
    PlanStep,
    UserAlert,
    UserOwnedTask,
    Milestone,
    MilestoneHistory,
    AppUser,
    UserRemedy,
)
from app.models.resolution import StepStatus, PlanStatus


# =============================================================================
# Care Readiness Computation
# =============================================================================

def _map_probability_to_status(prob: Optional[float]) -> str:
    """Map probability value to factor status."""
    if prob is None:
        return "pending"
    if prob >= 0.85:
        return "complete"
    if prob >= 0.5:
        return "in_progress"
    return "blocked"


def compute_care_readiness(probability: Optional[PaymentProbability]) -> Dict[str, Any]:
    """
    Compute care readiness from PaymentProbability.
    
    Returns:
        {
            "position": 0-100 (where marker sits on gradient),
            "direction": "improving" | "declining" | "stable",
            "factors": {
                "visit_confirmed": {"status": "complete" | "in_progress" | "blocked" | "pending"},
                "eligibility_verified": {...},
                "authorization_secured": {...},
                "documentation_ready": {...},
            }
        }
    """
    if not probability:
        return {
            "position": 50,
            "direction": "stable",
            "factors": {
                "visit_confirmed": {"status": "pending"},
                "eligibility_verified": {"status": "pending"},
                "authorization_secured": {"status": "pending"},
                "documentation_ready": {"status": "pending"},
            }
        }
    
    factors = {
        "visit_confirmed": {
            "status": _map_probability_to_status(probability.prob_appointment_attendance),
        },
        "eligibility_verified": {
            "status": _map_probability_to_status(probability.prob_eligibility),
        },
        "authorization_secured": {
            "status": _map_probability_to_status(probability.prob_coverage),
        },
        "documentation_ready": {
            "status": _map_probability_to_status(probability.prob_no_errors),
        },
    }
    
    # Position = overall probability * 100
    position = int((probability.overall_probability or 0.5) * 100)
    
    # Direction (placeholder - would need historical data)
    direction = "stable"
    
    return {
        "position": position,
        "direction": direction,
        "factors": factors,
    }


# =============================================================================
# Factor-based Structure (NEW - for simplified Sidecar)
# =============================================================================

# Factor definitions in sequence order
FACTOR_DEFINITIONS = [
    {"type": "attendance", "label": "ATTENDANCE", "order": 1, "prob_field": "prob_appointment_attendance"},
    {"type": "eligibility", "label": "ELIGIBILITY", "order": 2, "prob_field": "prob_eligibility"},
    {"type": "coverage", "label": "COVERAGE", "order": 3, "prob_field": "prob_coverage"},
    {"type": "clean_claim", "label": "CLEAN CLAIM", "order": 4, "prob_field": "prob_no_errors"},
    {"type": "errors", "label": "ERRORS", "order": 5, "prob_field": "prob_no_errors"},
]


def _compute_factor_status(prob_value: Optional[float], has_unresolved_steps: bool) -> str:
    """Compute status for a factor based on probability and step state."""
    if prob_value is not None and prob_value >= 0.85 and not has_unresolved_steps:
        return "resolved"
    elif has_unresolved_steps:
        return "blocked"
    elif prob_value is not None and prob_value < 0.85:
        return "blocked"
    else:
        return "waiting"


def _get_status_label(status: str, prob_value: Optional[float]) -> str:
    """Get human-readable status label."""
    if status == "resolved":
        return "Confirmed"
    elif status == "blocked":
        return "Blocked"
    else:
        return "Waiting"


def _compute_mode_recommendation(steps: List[PlanStep]) -> Dict[str, Any]:
    """Compute recommended mode based on step capabilities."""
    if not steps:
        return {"mode": "mobius", "confidence": 0.5, "reason": "No steps defined"}
    
    system_capable_count = sum(1 for s in steps if s.can_system_answer)
    total_steps = len(steps)
    
    if system_capable_count == total_steps:
        return {
            "mode": "mobius",
            "confidence": 0.95,
            "reason": "All steps can be automated"
        }
    elif system_capable_count > 0:
        return {
            "mode": "together",
            "confidence": 0.8,
            "reason": f"{system_capable_count} of {total_steps} steps can be automated"
        }
    else:
        return {
            "mode": "manual",
            "confidence": 0.7,
            "reason": "Steps require human action"
        }


def _step_to_factor_step(step: PlanStep) -> Dict[str, Any]:
    """Convert PlanStep to factor step format for new UI."""
    # Determine if it's user's turn (current step assigned to user)
    is_user_turn = (
        step.status in [StepStatus.CURRENT, StepStatus.PENDING] and
        step.assignee_type == "user"
    )
    
    # Map status to display status
    if step.status == StepStatus.RESOLVED:
        display_status = "done"
    elif step.status == StepStatus.CURRENT:
        display_status = "current"
    elif step.status == StepStatus.ANSWERED:
        display_status = "answered"
    elif step.status == StepStatus.SKIPPED:
        display_status = "skipped"
    else:
        display_status = "pending"
    
    # Map answer options for the modal
    answer_options = []
    answer_labels_map = {}  # code -> label for lookup
    if step.answer_options:
        for opt in step.answer_options:
            code = opt.get("code", "")
            label = opt.get("label", "")
            answer_options.append({
                "code": code,
                "label": label,
            })
            answer_labels_map[code] = label
    
    # Get the selected answer (most recent)
    selected_answer = None
    selected_answer_label = None
    if step.answers and len(step.answers) > 0:
        latest_answer = step.answers[0]  # Most recent due to ordering
        selected_answer = latest_answer.answer_code
        # Map code to label
        selected_answer_label = answer_labels_map.get(selected_answer, selected_answer)
    
    return {
        "step_id": str(step.step_id),
        "label": step.question_text,
        "status": display_status,
        "can_system_handle": step.can_system_answer,
        "assignee_type": step.assignee_type or "user",
        "assignee_icon": "🤖" if step.assignee_type == "mobius" else "👤",
        "is_user_turn": is_user_turn,
        "rationale": step.rationale,
        "answer_options": answer_options,  # For result capture modal
        "selected_answer": selected_answer,  # The answer code user selected
        "selected_answer_label": selected_answer_label,  # Human-readable label
    }


def build_factors_array(
    db: Session,
    plan: Optional[ResolutionPlan],
    probability: Optional[PaymentProbability],
    user_activities: List[str] = None,
    attention_status: str = None,
    lowest_factor: str = None,
    factor_overrides: Dict[str, str] = None,
    patient_context_id: UUID = None
) -> List[Dict[str, Any]]:
    """
    Build the factors array for the new simplified Sidecar UI.
    
    Returns 5 factors in sequence order with their steps, mode, and status.
    
    Args:
        attention_status: Patient-level user override status from patient_context ('resolved', 'unresolved', None)
        lowest_factor: The bottleneck factor from probability (e.g., 'eligibility')
        factor_overrides: Per-factor user overrides from patient_context.factor_overrides
                         Format: {"eligibility": "resolved", "errors": "resolved", ...}
        patient_context_id: Patient context ID for querying user remedies
    """
    factors = []
    factor_overrides = factor_overrides or {}
    
    # Get user remedies grouped by factor_type
    remedies_by_factor = {}
    if patient_context_id:
        remedies = db.query(UserRemedy).filter(
            UserRemedy.patient_context_id == patient_context_id
        ).order_by(UserRemedy.created_at.desc()).all()
        
        for remedy in remedies:
            if remedy.factor_type not in remedies_by_factor:
                remedies_by_factor[remedy.factor_type] = []
            remedies_by_factor[remedy.factor_type].append({
                "remedy_id": str(remedy.remedy_id),
                "remedy_text": remedy.remedy_text,
                "outcome": remedy.outcome,
                "outcome_notes": remedy.outcome_notes,
                "created_at": remedy.created_at.isoformat() if remedy.created_at else None,
            })
    
    # Get all steps grouped by factor_type
    steps_by_factor = {}
    if plan:
        all_steps = db.query(PlanStep).filter(
            PlanStep.plan_id == plan.plan_id
        ).order_by(PlanStep.step_order).all()
        
        for step in all_steps:
            factor_type = step.factor_type or "general"
            if factor_type not in steps_by_factor:
                steps_by_factor[factor_type] = []
            steps_by_factor[factor_type].append(step)
    
    # Build each factor
    for factor_def in FACTOR_DEFINITIONS:
        factor_type = factor_def["type"]
        
        # Get probability value for this factor
        prob_value = None
        if probability:
            prob_value = getattr(probability, factor_def["prob_field"], None)
        
        # Get steps for this factor
        factor_steps = steps_by_factor.get(factor_type, [])
        
        # Check for unresolved steps
        unresolved_steps = [
            s for s in factor_steps 
            if s.status not in [StepStatus.RESOLVED, StepStatus.SKIPPED]
        ]
        has_unresolved = len(unresolved_steps) > 0
        
        # Compute status
        status = _compute_factor_status(prob_value, has_unresolved)
        status_label = _get_status_label(status, prob_value)
        
        # Check for per-factor user override first (L2 level)
        user_override = None  # None = no override, "resolved" or "unresolved" = user override
        factor_override_status = factor_overrides.get(factor_type)
        if factor_override_status == 'resolved':
            # User has marked THIS specific factor as resolved
            status = "resolved"
            status_label = "User Resolved"
            user_override = "resolved"
        elif factor_override_status == 'unresolved':
            # User has marked THIS specific factor as unresolved (needs attention)
            status = "blocked"
            status_label = "User Flagged"
            user_override = "unresolved"
        elif attention_status == 'resolved' and lowest_factor and factor_type == lowest_factor:
            # Legacy: patient-level override applies to bottleneck factor
            status = "resolved"
            status_label = "User Resolved"
            user_override = "resolved"
        
        # Get mode from plan if set
        mode = None
        if plan and plan.factor_modes:
            mode = plan.factor_modes.get(factor_type)
        
        # Compute recommendation
        recommendation = _compute_mode_recommendation(factor_steps)
        
        # Build steps array
        steps_array = [_step_to_factor_step(s) for s in factor_steps]
        
        # Count evidence
        evidence_count = 0
        for step in factor_steps:
            if step.evidence_ids:
                evidence_count += len(step.evidence_ids)
        
        # Get remedies for this factor
        factor_remedies = remedies_by_factor.get(factor_type, [])
        
        factor = {
            "factor_type": factor_type,
            "label": factor_def["label"],
            "order": factor_def["order"],
            "status": status,
            "status_label": status_label,
            "is_focus": False,  # Set later by determine_focus
            "recommendation": recommendation,
            "mode": mode,
            "steps": steps_array,
            "evidence_count": evidence_count,
            "user_override": user_override,  # Flag to show this was user-overridden
            "remedies": factor_remedies,  # User-added remedies for learning
        }
        
        factors.append(factor)
    
    # Determine focus (skip if user already resolved the bottleneck)
    if attention_status != 'resolved':
        determine_focus(factors, user_activities)
    
    return factors


def determine_focus(factors: List[Dict[str, Any]], user_activities: List[str] = None):
    """
    Determine which factor should be the user's focus.
    
    Logic:
    1. First blocked factor matching user's activities = focus
    2. Fallback: first blocked factor
    """
    # Map factor types to activities
    factor_activity_map = {
        "attendance": ["schedule_appointments", "patient_outreach", "check_in_patients"],
        "eligibility": ["verify_eligibility", "check_in_patients"],
        "coverage": ["prior_authorization"],
        "clean_claim": ["submit_claims"],
        "errors": ["submit_claims", "rework_denials"],
    }
    
    # First pass: find blocked factor matching user's activities
    if user_activities:
        for factor in factors:
            if factor["status"] == "blocked":
                factor_activities = factor_activity_map.get(factor["factor_type"], [])
                if any(ua in factor_activities for ua in user_activities):
                    factor["is_focus"] = True
                    factor["focus_for_roles"] = factor_activities
                    return
    
    # Fallback: first blocked factor
    for factor in factors:
        if factor["status"] == "blocked":
            factor["is_focus"] = True
            return


# =============================================================================
# Bottlenecks (from PlanStep) - LEGACY, kept for backwards compatibility
# =============================================================================

def get_bottlenecks(
    db: Session,
    plan: Optional[ResolutionPlan],
    patient_name: str = "Patient"
) -> List[Dict[str, Any]]:
    """
    Get unresolved bottlenecks from resolution plan steps.
    
    Bottlenecks are steps that are NOT resolved/skipped - they need attention.
    This includes: pending, current, and answered (but not yet resolved).
    Includes selected_answer if user has already answered.
    
    Returns top 2 bottlenecks with highest probability impact.
    """
    if not plan:
        return []
    
    # Get all unresolved steps (pending, current, answered)
    # Resolved and skipped steps go to history
    steps = db.query(PlanStep).filter(
        PlanStep.plan_id == plan.plan_id,
        PlanStep.status.in_([StepStatus.PENDING, StepStatus.CURRENT, StepStatus.ANSWERED])
    ).order_by(PlanStep.step_order).all()
    
    bottlenecks = []
    for step in steps:
        bottleneck = _step_to_bottleneck(step, db)
        bottlenecks.append(bottleneck)
    
    # Sort by probability impact (highest first) and return top 2
    bottlenecks.sort(key=lambda b: b.get("probability_impact", 0.0), reverse=True)
    return bottlenecks[:2]  # Return max top 2


def get_resolved_steps(
    db: Session,
    plan: Optional[ResolutionPlan]
) -> List[Dict[str, Any]]:
    """
    Get resolved/completed steps for history display in More Info.
    
    These are steps marked as resolved by batch job or user confirmation.
    """
    if not plan:
        return []
    
    # Get resolved and skipped steps
    steps = db.query(PlanStep).filter(
        PlanStep.plan_id == plan.plan_id,
        PlanStep.status.in_([StepStatus.RESOLVED, StepStatus.SKIPPED])
    ).order_by(PlanStep.step_order).all()
    
    resolved = []
    for step in steps:
        item = _step_to_bottleneck(step, db)
        item["resolved_at"] = step.resolved_at.isoformat() if step.resolved_at else None
        resolved.append(item)
    
    return resolved


def _step_to_bottleneck(step: PlanStep, db: Session) -> Dict[str, Any]:
    """Convert a PlanStep to bottleneck dict format."""
    from app.models.probability import TaskTemplate
    
    # Map answer options
    answer_options = []
    if step.answer_options:
        for opt in step.answer_options:
            answer_options.append({
                "id": opt.get("code", ""),
                "label": opt.get("label", ""),
                "description": opt.get("description"),
            })
    
    # Get the most recent answer for this step (if any)
    selected_answer = None
    if step.answers and len(step.answers) > 0:
        latest_answer = step.answers[0]  # Most recent due to ordering
        selected_answer = latest_answer.answer_code
    
    # Determine Mobius capability
    mobius_can_handle = step.can_system_answer
    mobius_mode = "agentic" if step.can_system_answer else None
    mobius_action = None
    if step.system_suggestion:
        mobius_action = step.system_suggestion.get("source", "System can assist")
    
    # Get probability impact from linked TaskTemplate (if exists)
    probability_impact = 0.0
    if step.template_id:
        template = db.query(TaskTemplate).filter(
            TaskTemplate.template_id == step.template_id
        ).first()
        if template and template.expected_probability_lift:
            probability_impact = template.expected_probability_lift
    
    return {
        "id": str(step.step_id),
        "milestone_id": step.factor_type or "general",
        "question_text": step.question_text,
        "answer_options": answer_options,
        "selected_answer": selected_answer,
        "status": step.status,
        "description": step.description,
        "mobius_can_handle": mobius_can_handle,
        "mobius_mode": mobius_mode,
        "mobius_action": mobius_action,
        "probability_impact": probability_impact,  # For sorting by impact
        "sources": {},
    }


# =============================================================================
# Milestones
# =============================================================================

def get_milestones(
    db: Session,
    patient_context_id: UUID,
    patient_name: str = "Patient"
) -> List[Dict[str, Any]]:
    """
    Get milestones for a patient.
    
    Returns milestone progress with substeps and history.
    """
    milestones = db.query(Milestone).filter(
        Milestone.patient_context_id == patient_context_id
    ).order_by(Milestone.milestone_order).all()
    
    return [m.to_dict() for m in milestones]


def ensure_milestones_exist(
    db: Session,
    patient_context_id: UUID,
    tenant_id: UUID,
    patient_name: str = "Patient"
) -> List[Milestone]:
    """
    Ensure the 4 standard milestones exist for a patient.
    Creates them if they don't exist.
    """
    existing = db.query(Milestone).filter(
        Milestone.patient_context_id == patient_context_id
    ).all()
    
    existing_types = {m.milestone_type for m in existing}
    
    milestone_templates = [
        ("visit", f"{patient_name}'s visit confirmed", 0),
        ("eligibility", f"{patient_name}'s insurance verified", 1),
        ("authorization", f"{patient_name}'s authorization secured", 2),
        ("documentation", f"{patient_name}'s documentation ready", 3),
    ]
    
    for m_type, label, order in milestone_templates:
        if m_type not in existing_types:
            milestone = Milestone(
                patient_context_id=patient_context_id,
                tenant_id=tenant_id,
                milestone_type=m_type,
                label=label,
                label_template="{{possessive}} " + label.split("'s ", 1)[-1] if "'s " in label else label,
                milestone_order=order,
                status="pending",
            )
            db.add(milestone)
            existing.append(milestone)
    
    db.commit()
    return existing


# =============================================================================
# Knowledge Context
# =============================================================================

def get_knowledge_context(
    db: Session,
    patient_context: Optional[PatientContext]
) -> Dict[str, Any]:
    """
    Get knowledge context for chat.
    
    Returns payer info, policy excerpts, and relevant history.
    Currently returns placeholder data - would integrate with payer APIs.
    """
    # Placeholder - would fetch from payer data
    return {
        "payer": {
            "name": "",
            "phone": None,
            "portal_url": None,
            "avg_response_time": None,
        },
        "policy_excerpts": [],
        "relevant_history": [],
    }


# =============================================================================
# Alerts
# =============================================================================

def get_user_alerts(
    db: Session,
    user_id: UUID,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get alerts for a user (across all patients).
    """
    alerts = db.query(UserAlert).filter(
        UserAlert.user_id == user_id,
        UserAlert.dismissed == False
    ).order_by(UserAlert.created_at.desc()).limit(limit).all()
    
    return [a.to_dict() for a in alerts]


def get_unread_alert_count(db: Session, user_id: UUID) -> int:
    """Get count of unread alerts for a user."""
    return db.query(UserAlert).filter(
        UserAlert.user_id == user_id,
        UserAlert.read == False,
        UserAlert.dismissed == False
    ).count()


def mark_alerts_read(db: Session, user_id: UUID, alert_ids: Optional[List[UUID]] = None) -> int:
    """Mark alerts as read. If alert_ids is None, marks all unread alerts."""
    query = db.query(UserAlert).filter(
        UserAlert.user_id == user_id,
        UserAlert.read == False
    )
    
    if alert_ids:
        query = query.filter(UserAlert.alert_id.in_(alert_ids))
    
    count = query.update({"read": True, "read_at": datetime.utcnow()})
    db.commit()
    return count


# =============================================================================
# User Owned Tasks
# =============================================================================

def get_user_owned_tasks(
    db: Session,
    user_id: UUID,
    patient_context_id: Optional[UUID] = None
) -> List[Dict[str, Any]]:
    """
    Get tasks owned by user.
    
    If patient_context_id provided, filter to that patient.
    """
    query = db.query(UserOwnedTask).filter(
        UserOwnedTask.user_id == user_id,
        UserOwnedTask.status == "active"
    )
    
    if patient_context_id:
        query = query.filter(UserOwnedTask.patient_context_id == patient_context_id)
    
    tasks = query.order_by(UserOwnedTask.assigned_at.desc()).all()
    return [t.to_dict() for t in tasks]


def create_user_owned_task(
    db: Session,
    user_id: UUID,
    tenant_id: UUID,
    plan_step_id: UUID,
    plan_id: UUID,
    patient_context_id: UUID,
    question_text: str,
    patient_name: str,
    patient_key: str,
    initial_note: Optional[str] = None
) -> UserOwnedTask:
    """Create a new user-owned task."""
    task = UserOwnedTask(
        user_id=user_id,
        tenant_id=tenant_id,
        plan_step_id=plan_step_id,
        plan_id=plan_id,
        patient_context_id=patient_context_id,
        question_text=question_text,
        patient_name=patient_name,
        patient_key=patient_key,
        initial_note=initial_note,
        status="active",
    )
    db.add(task)
    db.commit()
    return task


# =============================================================================
# Full Sidecar State Builder
# =============================================================================

def build_sidecar_state(
    db: Session,
    user_id: UUID,
    patient_context: Optional[PatientContext],
    session_id: str
) -> Dict[str, Any]:
    """
    Build the full sidecar state response.
    
    This is the main entry point for GET /api/v1/sidecar/state
    """
    patient_context_id = patient_context.patient_context_id if patient_context else None
    
    # Refresh patient_context to get fresh attention_status, resolved_until, and factor_overrides
    attention_status = None
    resolved_until = None
    factor_overrides = {}
    is_resolved = False
    if patient_context:
        db.refresh(patient_context)  # Force fresh read from database
        attention_status = patient_context.attention_status
        resolved_until = patient_context.resolved_until
        factor_overrides = patient_context.factor_overrides or {}
        # Check if patient is currently resolved (suppression active)
        if attention_status == "resolved" and resolved_until:
            is_resolved = datetime.utcnow() < resolved_until
    
    # Get patient name from the latest snapshot
    patient_name = "Patient"
    if patient_context and patient_context.snapshots:
        # Get the latest snapshot (highest version)
        latest_snapshot = max(patient_context.snapshots, key=lambda s: s.snapshot_version)
        patient_name = latest_snapshot.display_name or "Patient"
    
    patient_key = None
    
    # Build record context
    record = {
        "type": "patient",
        "id": str(patient_context_id) if patient_context_id else "",
        "displayName": patient_name,
        "shortName": patient_name.split()[0] if patient_name else "Patient",
        "possessive": f"{patient_name.split()[0]}'s" if patient_name else "Patient's",
    }
    
    # Get payment probability for care readiness
    probability = None
    if patient_context_id:
        probability = db.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == patient_context_id
        ).order_by(PaymentProbability.computed_at.desc()).first()
    
    care_readiness = compute_care_readiness(probability)
    
    # Get resolution plan and bottlenecks
    plan = None
    if patient_context_id:
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == patient_context_id,
            ResolutionPlan.status == PlanStatus.ACTIVE
        ).first()
    
    # Suppress active bottlenecks if patient is resolved, but keep resolved_steps for history
    if is_resolved:
        bottlenecks = []  # Suppress active bottlenecks
    else:
        bottlenecks = get_bottlenecks(db, plan, patient_name)
    
    resolved_steps = get_resolved_steps(db, plan)  # Always show history
    
    # Get milestones
    milestones = []
    if patient_context_id:
        # Ensure milestones exist
        tenant_id = patient_context.tenant_id if patient_context else None
        if tenant_id:
            ensure_milestones_exist(db, patient_context_id, tenant_id, patient_name)
        milestones = get_milestones(db, patient_context_id, patient_name)
    
    # Get knowledge context
    knowledge_context = get_knowledge_context(db, patient_context)
    
    # Get alerts
    alerts = get_user_alerts(db, user_id)
    
    # Get user-owned tasks
    user_owned_tasks = []
    if patient_context_id:
        user_owned_tasks = get_user_owned_tasks(db, user_id, patient_context_id)
    
    # Build new factors array for simplified Sidecar
    # Get user activities for focus determination
    user_activities = []
    try:
        from app.models.activity import UserActivity
        activities = db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).all()
        user_activities = [ua.activity.activity_code for ua in activities if ua.activity]
    except Exception:
        pass
    
    # Get lowest_factor (bottleneck) from probability for user override handling
    lowest_factor = probability.lowest_factor if probability else None
    
    factors = build_factors_array(
        db, plan, probability, user_activities,
        attention_status=attention_status,
        lowest_factor=lowest_factor,
        factor_overrides=factor_overrides,
        patient_context_id=patient_context_id
    )
    
    return {
        "ok": True,
        "session_id": session_id,
        "surface": "sidecar",
        "record": record,
        "care_readiness": care_readiness,
        # New: factors array for simplified Sidecar
        "factors": factors,
        # Legacy: bottlenecks (kept for backwards compatibility)
        "bottlenecks": bottlenecks,
        "resolved_steps": resolved_steps,  # For "More info" section
        "milestones": milestones,
        "knowledge_context": knowledge_context,
        "alerts": alerts,
        "user_owned_tasks": user_owned_tasks,
        "attention_status": attention_status,  # Include in response for frontend
        "factor_overrides": factor_overrides,  # Per-factor user overrides
        "resolved_until": resolved_until.isoformat() if resolved_until else None,  # Include for frontend display
        "computed_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Alert Creation Helpers (for batch job use)
# =============================================================================

def create_win_alert(
    db: Session,
    user_id: UUID,
    patient_context_id: UUID,
    patient_name: str,
    patient_key: str,
    title: str,
    subtitle: Optional[str] = None,
    milestone_id: Optional[UUID] = None
) -> UserAlert:
    """Create a 'win' alert (celebration)."""
    alert = UserAlert(
        user_id=user_id,
        alert_type="win",
        priority="normal",
        title=title,
        subtitle=subtitle,
        patient_context_id=patient_context_id,
        patient_name=patient_name,
        patient_key=patient_key,
        action_type="open_sidecar",
        related_milestone_id=milestone_id,
    )
    db.add(alert)
    db.commit()
    return alert


def create_reminder_alert(
    db: Session,
    user_id: UUID,
    patient_context_id: UUID,
    patient_name: str,
    patient_key: str,
    title: str,
    subtitle: Optional[str] = None,
    step_id: Optional[UUID] = None
) -> UserAlert:
    """Create a 'reminder' alert."""
    alert = UserAlert(
        user_id=user_id,
        alert_type="reminder",
        priority="normal",
        title=title,
        subtitle=subtitle,
        patient_context_id=patient_context_id,
        patient_name=patient_name,
        patient_key=patient_key,
        action_type="open_sidecar",
        related_step_id=step_id,
    )
    db.add(alert)
    db.commit()
    return alert
