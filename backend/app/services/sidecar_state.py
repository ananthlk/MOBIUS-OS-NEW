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
# Bottlenecks (from PlanStep)
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
        bottleneck = _step_to_bottleneck(step)
        bottlenecks.append(bottleneck)
    
    return bottlenecks


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
        item = _step_to_bottleneck(step)
        item["resolved_at"] = step.resolved_at.isoformat() if step.resolved_at else None
        resolved.append(item)
    
    return resolved


def _step_to_bottleneck(step: PlanStep) -> Dict[str, Any]:
    """Convert a PlanStep to bottleneck dict format."""
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
    
    bottlenecks = get_bottlenecks(db, plan, patient_name)
    resolved_steps = get_resolved_steps(db, plan)
    
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
    
    return {
        "ok": True,
        "session_id": session_id,
        "surface": "sidecar",
        "record": record,
        "care_readiness": care_readiness,
        "bottlenecks": bottlenecks,
        "resolved_steps": resolved_steps,  # For "More info" section
        "milestones": milestones,
        "knowledge_context": knowledge_context,
        "alerts": alerts,
        "user_owned_tasks": user_owned_tasks,
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
