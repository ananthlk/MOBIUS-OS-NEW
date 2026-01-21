"""
Resolution Plan API endpoints.

Provides endpoints for:
- Fetching resolution plans for patients
- Submitting answers to steps
- Adding notes and steps
- Reassigning steps
- Resolving and escalating plans
"""

import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import and_

from app.db.postgres import get_db_session
from app.models import PatientContext, AppUser
from app.models.resolution import (
    ResolutionPlan,
    PlanStep,
    StepAnswer,
    PlanNote,
    PlanModification,
    PlanStatus,
    StepStatus,
    AnswerMode,
)
from app.models.activity import UserActivity


bp = Blueprint("resolution", __name__, url_prefix="/api/v1/resolution")


def get_current_user_id():
    """Get current user ID from request headers or session."""
    # TODO: Integrate with auth service
    user_id = request.headers.get("X-User-Id")
    if user_id:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    return None


def get_user_activities(db, user_id: uuid.UUID) -> list:
    """Get activity codes for a user."""
    if not user_id:
        return []
    
    activities = db.query(UserActivity).filter(
        UserActivity.user_id == user_id
    ).all()
    
    return [ua.activity.activity_code for ua in activities if ua.activity]


def count_actions_for_user(steps: list, user_activities: list) -> int:
    """Count steps the user can act on based on their activities."""
    count = 0
    for step in steps:
        if step.status not in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
            step_activities = step.assignable_activities or []
            if any(a in user_activities for a in step_activities):
                count += 1
    return count


def format_step_for_response(step: PlanStep, user_activities: list = None) -> dict:
    """Format a step for API response."""
    can_act = False
    if user_activities and step.assignable_activities:
        can_act = any(a in user_activities for a in step.assignable_activities)
    
    return {
        "step_id": str(step.step_id),
        "step_code": step.step_code,
        "step_order": step.step_order,
        "step_type": step.step_type,
        "input_type": step.input_type,
        "question_text": step.question_text,
        "description": step.description,
        "answer_options": step.answer_options,
        "form_fields": step.form_fields,
        "can_system_answer": step.can_system_answer,
        "system_suggestion": step.system_suggestion,
        "assignable_activities": step.assignable_activities,
        "assigned_to_user_id": str(step.assigned_to_user_id) if step.assigned_to_user_id else None,
        "status": step.status,
        "factor_type": step.factor_type,
        "is_branch": step.is_branch,
        "can_act": can_act,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
    }


def format_plan_for_response(plan: ResolutionPlan, user_activities: list = None) -> dict:
    """Format a plan for API response."""
    # Group steps by factor
    factors = {}
    for step in plan.steps:
        factor = step.factor_type or "general"
        if factor not in factors:
            factors[factor] = {
                "type": factor,
                "status": "ready",  # Will be updated below
                "progress": {"done": 0, "total": 0},
                "steps": []
            }
        
        factors[factor]["steps"].append(format_step_for_response(step, user_activities))
        factors[factor]["progress"]["total"] += 1
        
        if step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
            factors[factor]["progress"]["done"] += 1
        elif step.status == StepStatus.CURRENT:
            factors[factor]["status"] = "needs_action"
    
    # Determine factor status
    for factor_data in factors.values():
        if factor_data["progress"]["done"] == factor_data["progress"]["total"]:
            factor_data["status"] = "ready"
        elif any(s["status"] == StepStatus.CURRENT for s in factor_data["steps"]):
            factor_data["status"] = "needs_action"
        else:
            factor_data["status"] = "pending"
    
    # Get current step
    current_step = None
    if plan.current_step_id:
        for step in plan.steps:
            if step.step_id == plan.current_step_id:
                current_step = format_step_for_response(step, user_activities)
                break
    
    # Count actions for user
    actions_for_user = count_actions_for_user(plan.steps, user_activities) if user_activities else 0
    
    return {
        "plan_id": str(plan.plan_id),
        "patient_context_id": str(plan.patient_context_id),
        "gap_types": plan.gap_types,
        "status": plan.status,
        "factors": list(factors.values()),
        "current_step": current_step,
        "actions_for_user": actions_for_user,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
        "resolved_at": plan.resolved_at.isoformat() if plan.resolved_at else None,
        "resolution_type": plan.resolution_type,
    }


# =============================================================================
# GET Endpoints
# =============================================================================

@bp.route("/plan/patient/<patient_id>", methods=["GET"])
def get_plan_for_patient(patient_id: str):
    """
    Get active resolution plan for a patient.
    
    Returns the plan with all steps, formatted for UI consumption.
    """
    try:
        patient_uuid = uuid.UUID(patient_id)
    except ValueError:
        return jsonify({"error": "Invalid patient_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    user_activities = get_user_activities(db, user_id) if user_id else []
    
    # Get active plan for patient
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.patient_context_id == patient_uuid,
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).first()
    
    if not plan:
        return jsonify({
            "plan": None,
            "message": "No active resolution plan",
            "actions_for_user": 0,
        })
    
    # Get patient info
    patient = db.query(PatientContext).filter(
        PatientContext.patient_context_id == patient_uuid
    ).first()
    
    response = {
        "patient": {
            "patient_context_id": str(patient.patient_context_id),
            "patient_key": patient.patient_key,
        } if patient else None,
        "plan": format_plan_for_response(plan, user_activities),
        "notes": [note.to_dict() for note in plan.notes[:10]],  # Latest 10 notes
    }
    
    return jsonify(response)


@bp.route("/plan/<plan_id>", methods=["GET"])
def get_plan_details(plan_id: str):
    """
    Get full plan details by plan ID.
    """
    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError:
        return jsonify({"error": "Invalid plan_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    user_activities = get_user_activities(db, user_id) if user_id else []
    
    plan = db.query(ResolutionPlan).filter(
        ResolutionPlan.plan_id == plan_uuid
    ).first()
    
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    
    return jsonify({
        "plan": format_plan_for_response(plan, user_activities),
        "notes": [note.to_dict() for note in plan.notes],
        "modifications": [mod.to_dict() for mod in plan.modifications[:20]],
    })


@bp.route("/my-tasks", methods=["GET"])
def get_my_tasks():
    """
    Get steps assigned to the current user or matching their activities.
    """
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    user_activities = get_user_activities(db, user_id)
    
    # Get all active plans
    plans = db.query(ResolutionPlan).filter(
        ResolutionPlan.status == PlanStatus.ACTIVE
    ).all()
    
    tasks = []
    for plan in plans:
        patient = plan.patient_context
        for step in plan.steps:
            if step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
                continue
            
            # Check if user can act on this step
            step_activities = step.assignable_activities or []
            if any(a in user_activities for a in step_activities):
                tasks.append({
                    "step": format_step_for_response(step, user_activities),
                    "plan_id": str(plan.plan_id),
                    "patient": {
                        "patient_context_id": str(patient.patient_context_id),
                        "patient_key": patient.patient_key,
                    } if patient else None,
                    "gap_type": plan.gap_types[0] if plan.gap_types else None,
                })
    
    return jsonify({
        "tasks": tasks,
        "total": len(tasks),
    })


# =============================================================================
# POST Endpoints - Actions
# =============================================================================

@bp.route("/answer", methods=["POST"])
def submit_answer():
    """
    Submit an answer to a step.
    
    Request body:
    {
        "step_id": "uuid",
        "answer_code": "yes",
        "answer_details": {...},  // Optional, for form data
        "answer_mode": "user_driven"  // Optional
    }
    """
    data = request.json or {}
    step_id = data.get("step_id")
    answer_code = data.get("answer_code")
    answer_details = data.get("answer_details")
    answer_mode = data.get("answer_mode", AnswerMode.USER_DRIVEN)
    
    if not step_id or not answer_code:
        return jsonify({"error": "step_id and answer_code are required"}), 400
    
    try:
        step_uuid = uuid.UUID(step_id)
    except ValueError:
        return jsonify({"error": "Invalid step_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    # Get the step
    step = db.query(PlanStep).filter(PlanStep.step_id == step_uuid).first()
    if not step:
        return jsonify({"error": "Step not found"}), 404
    
    # Get the plan
    plan = step.plan
    
    # Create answer record
    answer = StepAnswer(
        step_id=step.step_id,
        answer_code=answer_code,
        answer_details=answer_details,
        answered_by=user_id,
        answer_mode=answer_mode,
    )
    db.add(answer)
    
    # Update step status
    step.status = StepStatus.COMPLETED
    step.completed_at = datetime.utcnow()
    
    # Find and set next step
    next_step_code = None
    if step.answer_options:
        for option in step.answer_options:
            if option.get("code") == answer_code:
                next_step_code = option.get("next_step_code")
                break
    
    if next_step_code:
        # Find the next step by code
        next_step = db.query(PlanStep).filter(
            PlanStep.plan_id == plan.plan_id,
            PlanStep.step_code == next_step_code
        ).first()
        
        if next_step:
            next_step.status = StepStatus.CURRENT
            plan.current_step_id = next_step.step_id
    else:
        # Find next pending step by order
        next_step = db.query(PlanStep).filter(
            PlanStep.plan_id == plan.plan_id,
            PlanStep.status == StepStatus.PENDING
        ).order_by(PlanStep.step_order).first()
        
        if next_step:
            next_step.status = StepStatus.CURRENT
            plan.current_step_id = next_step.step_id
        else:
            # All steps completed - check if plan should be resolved
            plan.current_step_id = None
    
    # Update plan timestamp
    plan.updated_at = datetime.utcnow()
    
    # Log modification
    if user_id:
        mod = PlanModification(
            plan_id=plan.plan_id,
            user_id=user_id,
            action="answer_step",
            details={"step_id": str(step.step_id), "answer_code": answer_code},
        )
        db.add(mod)
    
    db.commit()
    
    # Get updated user activities for response
    user_activities = get_user_activities(db, user_id) if user_id else []
    
    return jsonify({
        "success": True,
        "step_id": str(step.step_id),
        "answer_code": answer_code,
        "plan": format_plan_for_response(plan, user_activities),
    })


@bp.route("/note", methods=["POST"])
def add_note():
    """
    Add a note to a plan.
    
    Request body:
    {
        "plan_id": "uuid",
        "note_text": "...",
        "related_factor": "eligibility"  // Optional
    }
    """
    data = request.json or {}
    plan_id = data.get("plan_id")
    note_text = data.get("note_text")
    related_factor = data.get("related_factor")
    
    if not plan_id or not note_text:
        return jsonify({"error": "plan_id and note_text are required"}), 400
    
    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError:
        return jsonify({"error": "Invalid plan_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    plan = db.query(ResolutionPlan).filter(ResolutionPlan.plan_id == plan_uuid).first()
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    
    note = PlanNote(
        plan_id=plan.plan_id,
        user_id=user_id,
        note_text=note_text,
        related_factor=related_factor,
    )
    db.add(note)
    
    # Log modification
    mod = PlanModification(
        plan_id=plan.plan_id,
        user_id=user_id,
        action="add_note",
        details={"note_text": note_text[:100], "related_factor": related_factor},
    )
    db.add(mod)
    
    plan.updated_at = datetime.utcnow()
    db.commit()
    
    return jsonify({
        "success": True,
        "note": note.to_dict(),
    })


@bp.route("/step", methods=["POST"])
def add_step():
    """
    Add a custom step to a plan.
    
    Request body:
    {
        "plan_id": "uuid",
        "step_code": "custom_step",
        "question_text": "...",
        "factor_type": "eligibility",
        "answer_options": [...]
    }
    """
    data = request.json or {}
    plan_id = data.get("plan_id")
    step_code = data.get("step_code")
    question_text = data.get("question_text")
    
    if not plan_id or not step_code or not question_text:
        return jsonify({"error": "plan_id, step_code, and question_text are required"}), 400
    
    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError:
        return jsonify({"error": "Invalid plan_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    plan = db.query(ResolutionPlan).filter(ResolutionPlan.plan_id == plan_uuid).first()
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    
    # Get max step order
    max_order = db.query(PlanStep).filter(
        PlanStep.plan_id == plan.plan_id
    ).count()
    
    step = PlanStep(
        plan_id=plan.plan_id,
        step_order=max_order + 1,
        step_code=step_code,
        step_type=data.get("step_type", "question"),
        input_type=data.get("input_type", "single_choice"),
        question_text=question_text,
        description=data.get("description"),
        answer_options=data.get("answer_options"),
        factor_type=data.get("factor_type"),
        assignable_activities=data.get("assignable_activities"),
        status=StepStatus.PENDING,
    )
    db.add(step)
    
    # Log modification
    mod = PlanModification(
        plan_id=plan.plan_id,
        user_id=user_id,
        action="add_step",
        details={"step_code": step_code, "question_text": question_text[:100]},
    )
    db.add(mod)
    
    plan.updated_at = datetime.utcnow()
    db.commit()
    
    user_activities = get_user_activities(db, user_id)
    
    return jsonify({
        "success": True,
        "step": format_step_for_response(step, user_activities),
    })


@bp.route("/reassign", methods=["POST"])
def reassign_step():
    """
    Reassign a step to another user or to system.
    
    Request body:
    {
        "step_id": "uuid",
        "assign_to_user_id": "uuid" or null,
        "note": "..."  // Optional
    }
    """
    data = request.json or {}
    step_id = data.get("step_id")
    assign_to_user_id = data.get("assign_to_user_id")
    note = data.get("note")
    
    if not step_id:
        return jsonify({"error": "step_id is required"}), 400
    
    try:
        step_uuid = uuid.UUID(step_id)
        assign_to_uuid = uuid.UUID(assign_to_user_id) if assign_to_user_id else None
    except ValueError:
        return jsonify({"error": "Invalid UUID"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    step = db.query(PlanStep).filter(PlanStep.step_id == step_uuid).first()
    if not step:
        return jsonify({"error": "Step not found"}), 404
    
    old_assigned = step.assigned_to_user_id
    step.assigned_to_user_id = assign_to_uuid
    
    # Log modification
    mod = PlanModification(
        plan_id=step.plan_id,
        user_id=user_id,
        action="reassign_step",
        details={
            "step_id": str(step.step_id),
            "old_assigned": str(old_assigned) if old_assigned else None,
            "new_assigned": str(assign_to_uuid) if assign_to_uuid else "system",
            "note": note,
        },
    )
    db.add(mod)
    
    step.plan.updated_at = datetime.utcnow()
    db.commit()
    
    return jsonify({
        "success": True,
        "step_id": str(step.step_id),
        "assigned_to": str(assign_to_uuid) if assign_to_uuid else None,
    })


@bp.route("/resolve", methods=["POST"])
def resolve_plan():
    """
    Mark a plan as resolved.
    
    Request body:
    {
        "plan_id": "uuid",
        "resolution_type": "eligibility_verified",
        "resolution_notes": "..."
    }
    """
    data = request.json or {}
    plan_id = data.get("plan_id")
    resolution_type = data.get("resolution_type")
    resolution_notes = data.get("resolution_notes")
    
    if not plan_id or not resolution_type:
        return jsonify({"error": "plan_id and resolution_type are required"}), 400
    
    try:
        plan_uuid = uuid.UUID(plan_id)
    except ValueError:
        return jsonify({"error": "Invalid plan_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    plan = db.query(ResolutionPlan).filter(ResolutionPlan.plan_id == plan_uuid).first()
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    
    plan.status = PlanStatus.RESOLVED
    plan.resolved_at = datetime.utcnow()
    plan.resolved_by = user_id
    plan.resolution_type = resolution_type
    plan.resolution_notes = resolution_notes
    plan.updated_at = datetime.utcnow()
    
    # Log modification
    mod = PlanModification(
        plan_id=plan.plan_id,
        user_id=user_id,
        action="resolve",
        details={"resolution_type": resolution_type, "notes": resolution_notes},
    )
    db.add(mod)
    
    db.commit()
    
    return jsonify({
        "success": True,
        "plan_id": str(plan.plan_id),
        "status": plan.status,
        "resolved_at": plan.resolved_at.isoformat(),
    })


@bp.route("/escalate", methods=["POST"])
def escalate_plan():
    """
    Escalate a plan to another user or queue.
    
    Request body:
    {
        "plan_id": "uuid",
        "escalate_to_user_id": "uuid",
        "escalation_reason": "..."
    }
    """
    data = request.json or {}
    plan_id = data.get("plan_id")
    escalate_to_user_id = data.get("escalate_to_user_id")
    escalation_reason = data.get("escalation_reason")
    
    if not plan_id or not escalation_reason:
        return jsonify({"error": "plan_id and escalation_reason are required"}), 400
    
    try:
        plan_uuid = uuid.UUID(plan_id)
        escalate_to_uuid = uuid.UUID(escalate_to_user_id) if escalate_to_user_id else None
    except ValueError:
        return jsonify({"error": "Invalid UUID"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    plan = db.query(ResolutionPlan).filter(ResolutionPlan.plan_id == plan_uuid).first()
    if not plan:
        return jsonify({"error": "Plan not found"}), 404
    
    plan.status = PlanStatus.ESCALATED
    plan.escalated_at = datetime.utcnow()
    plan.escalated_to = escalate_to_uuid
    plan.escalation_reason = escalation_reason
    plan.updated_at = datetime.utcnow()
    
    # Log modification
    mod = PlanModification(
        plan_id=plan.plan_id,
        user_id=user_id,
        action="escalate",
        details={
            "escalate_to": str(escalate_to_uuid) if escalate_to_uuid else None,
            "reason": escalation_reason,
        },
    )
    db.add(mod)
    
    db.commit()
    
    return jsonify({
        "success": True,
        "plan_id": str(plan.plan_id),
        "status": plan.status,
        "escalated_to": str(escalate_to_uuid) if escalate_to_uuid else None,
    })


@bp.route("/skip", methods=["POST"])
def skip_step():
    """
    Skip a step.
    
    Request body:
    {
        "step_id": "uuid",
        "reason": "..."
    }
    """
    data = request.json or {}
    step_id = data.get("step_id")
    reason = data.get("reason")
    
    if not step_id:
        return jsonify({"error": "step_id is required"}), 400
    
    try:
        step_uuid = uuid.UUID(step_id)
    except ValueError:
        return jsonify({"error": "Invalid step_id"}), 400
    
    db = get_db_session()
    user_id = get_current_user_id()
    
    if not user_id:
        return jsonify({"error": "User not authenticated"}), 401
    
    step = db.query(PlanStep).filter(PlanStep.step_id == step_uuid).first()
    if not step:
        return jsonify({"error": "Step not found"}), 404
    
    step.status = StepStatus.SKIPPED
    step.completed_at = datetime.utcnow()
    
    plan = step.plan
    
    # Find next step
    next_step = db.query(PlanStep).filter(
        PlanStep.plan_id == plan.plan_id,
        PlanStep.status == StepStatus.PENDING
    ).order_by(PlanStep.step_order).first()
    
    if next_step:
        next_step.status = StepStatus.CURRENT
        plan.current_step_id = next_step.step_id
    else:
        plan.current_step_id = None
    
    # Log modification
    mod = PlanModification(
        plan_id=plan.plan_id,
        user_id=user_id,
        action="skip_step",
        details={"step_id": str(step.step_id), "reason": reason},
    )
    db.add(mod)
    
    plan.updated_at = datetime.utcnow()
    db.commit()
    
    user_activities = get_user_activities(db, user_id)
    
    return jsonify({
        "success": True,
        "step_id": str(step.step_id),
        "plan": format_plan_for_response(plan, user_activities),
    })
