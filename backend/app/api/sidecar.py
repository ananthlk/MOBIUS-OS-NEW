"""
Sidecar API Blueprint

Flask routes for the Sidecar UI:
- GET /api/v1/sidecar/state - Full sidecar state
- GET /api/v1/user/alerts - All user alerts (cross-patient)
- POST /api/v1/sidecar/answer - Submit answer to question
- POST /api/v1/sidecar/note - Add note to bottleneck
- POST /api/v1/sidecar/assign - Assign to Mobius
- POST /api/v1/sidecar/assign-bulk - Bulk assign
- POST /api/v1/sidecar/own - User takes ownership
"""

from flask import Blueprint, request, jsonify, g
from functools import wraps
from datetime import datetime
from uuid import UUID
import traceback

from app.db.postgres import get_db_session
from app.models import (
    PatientContext,
    ResolutionPlan,
    PlanStep,
    StepAnswer,
    PlanNote,
    AppUser,
    UserAlert,
    UserOwnedTask,
    Milestone,
    MilestoneHistory,
    UserRemedy,
)
from app.models.resolution import StepStatus, AnswerMode
from app.services.sidecar_state import (
    build_sidecar_state,
    get_user_alerts,
    get_unread_alert_count,
    mark_alerts_read,
    create_user_owned_task,
)
from app.services.auth_service import get_user_from_token

# Create blueprint (named 'sidecar_api' to avoid collision with legacy 'sidecar' blueprint)
sidecar_bp = Blueprint('sidecar_api', __name__, url_prefix='/api/v1')


# =============================================================================
# Auth Decorator
# =============================================================================

def require_auth(f):
    """Decorator to require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"ok": False, "error": "Missing or invalid Authorization header"}), 401
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        try:
            with get_db_session() as db:
                user = get_user_from_token(db, token)
                if not user:
                    return jsonify({"ok": False, "error": "Invalid or expired token"}), 401
                
                g.user = user
                g.user_id = user.user_id
                g.tenant_id = user.tenant_id
        except Exception as e:
            print(f"[Sidecar API] Auth error: {e}")
            return jsonify({"ok": False, "error": "Authentication failed"}), 401
        
        return f(*args, **kwargs)
    return decorated


# =============================================================================
# GET /api/v1/sidecar/state
# =============================================================================

@sidecar_bp.route('/sidecar/state', methods=['GET'])
@require_auth
def get_sidecar_state():
    """
    Get full sidecar state for a patient.
    
    Query params:
        patient_key: Optional patient identifier
        session_id: Session ID
    """
    try:
        patient_key = request.args.get('patient_key')
        session_id = request.args.get('session_id', '')
        
        with get_db_session() as db:
            # Find patient context by patient_key (external key like "demo_001")
            patient_context = None
            if patient_key:
                # First try by patient_key (external identifier)
                patient_context = db.query(PatientContext).filter(
                    PatientContext.tenant_id == g.tenant_id,
                    PatientContext.patient_key == patient_key
                ).first()
                
                # If not found, try by patient_context_id (UUID) for backwards compatibility
                if not patient_context:
                    try:
                        patient_context = db.query(PatientContext).filter(
                            PatientContext.tenant_id == g.tenant_id,
                            PatientContext.patient_context_id == UUID(patient_key)
                        ).first()
                    except (ValueError, TypeError):
                        pass  # Not a valid UUID, skip
                
                # Expire the object to force fresh data on next access (in build_sidecar_state)
                if patient_context:
                    db.expire(patient_context)
            
            # Build state (will refresh patient_context inside)
            state = build_sidecar_state(
                db=db,
                user_id=g.user_id,
                patient_context=patient_context,
                session_id=session_id
            )
            
            return jsonify(state)
    
    except Exception as e:
        print(f"[Sidecar API] Error in get_sidecar_state: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# GET /api/v1/user/alerts
# =============================================================================

@sidecar_bp.route('/user/alerts', methods=['GET'])
@require_auth
def get_alerts():
    """
    Get all alerts for the current user (cross-patient).
    
    Used by global toast manager for notifications.
    """
    try:
        with get_db_session() as db:
            alerts = get_user_alerts(db, g.user_id, limit=50)
            unread_count = get_unread_alert_count(db, g.user_id)
            
            return jsonify({
                "ok": True,
                "alerts": alerts,
                "unread_count": unread_count,
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in get_alerts: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@sidecar_bp.route('/user/alerts/read', methods=['POST'])
@require_auth
def mark_alerts_as_read():
    """Mark alerts as read."""
    try:
        data = request.get_json() or {}
        alert_ids = data.get('alert_ids')  # Optional - if None, marks all as read
        
        with get_db_session() as db:
            if alert_ids:
                alert_ids = [UUID(aid) for aid in alert_ids]
            
            count = mark_alerts_read(db, g.user_id, alert_ids)
            
            return jsonify({
                "ok": True,
                "marked_count": count,
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in mark_alerts_as_read: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/answer
# =============================================================================

@sidecar_bp.route('/sidecar/answer', methods=['POST'])
@require_auth
def submit_answer():
    """
    Submit an answer to a question/bottleneck.
    
    Body:
        session_id: string
        patient_key: string
        bottleneck_id: string (step_id)
        answer_id: string (answer code)
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id', '')
        patient_key = data.get('patient_key')
        bottleneck_id = data.get('bottleneck_id')
        answer_id = data.get('answer_id')
        
        if not bottleneck_id or not answer_id:
            return jsonify({"ok": False, "error": "Missing bottleneck_id or answer_id"}), 400
        
        with get_db_session() as db:
            # Get the step
            step = db.query(PlanStep).filter(
                PlanStep.step_id == UUID(bottleneck_id)
            ).first()
            
            if not step:
                return jsonify({"ok": False, "error": "Step not found"}), 404
            
            # Record the answer
            answer = StepAnswer(
                step_id=step.step_id,
                answer_code=answer_id,
                answered_by=g.user_id,
                answer_mode=AnswerMode.USER_DRIVEN,
            )
            db.add(answer)
            
            # Update step status based on action type
            if answer_id == 'skip':
                # User skipped - set to SKIPPED (user override)
                step.status = StepStatus.SKIPPED
                step.resolved_at = datetime.utcnow()
            else:
                # User provided an answer - set to ANSWERED
                # Batch job will evaluate and determine if issue is resolved
                step.status = StepStatus.ANSWERED
            
            step.answered_at = datetime.utcnow()
            
            db.commit()
            
            return jsonify({
                "ok": True,
                "step_id": str(step.step_id),
                "answer_id": answer_id,
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in submit_answer: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/note
# =============================================================================

@sidecar_bp.route('/sidecar/note', methods=['POST'])
@require_auth
def add_note():
    """
    Add a note to a bottleneck/step.
    
    Body:
        session_id: string
        patient_key: string
        bottleneck_id: string (step_id)
        note_text: string
    """
    try:
        data = request.get_json() or {}
        bottleneck_id = data.get('bottleneck_id')
        note_text = data.get('note_text', '').strip()
        
        if not bottleneck_id:
            return jsonify({"ok": False, "error": "Missing bottleneck_id"}), 400
        
        if not note_text:
            return jsonify({"ok": False, "error": "Note text is required"}), 400
        
        with get_db_session() as db:
            # Get the step
            step = db.query(PlanStep).filter(
                PlanStep.step_id == UUID(bottleneck_id)
            ).first()
            
            if not step:
                return jsonify({"ok": False, "error": "Step not found"}), 404
            
            # Create note
            note = PlanNote(
                plan_id=step.plan_id,
                user_id=g.user_id,
                note_text=note_text,
                related_factor=step.factor_type,
            )
            db.add(note)
            db.commit()
            
            return jsonify({
                "ok": True,
                "note_id": str(note.note_id),
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in add_note: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/assign
# =============================================================================

@sidecar_bp.route('/sidecar/assign', methods=['POST'])
@require_auth
def assign_to_mobius():
    """
    Assign a bottleneck to Mobius (agentic mode).
    
    Body:
        session_id: string
        patient_key: string
        bottleneck_id: string (step_id)
        mode: "agentic" | "copilot"
    """
    try:
        data = request.get_json() or {}
        bottleneck_id = data.get('bottleneck_id')
        mode = data.get('mode', 'agentic')
        
        if not bottleneck_id:
            return jsonify({"ok": False, "error": "Missing bottleneck_id"}), 400
        
        with get_db_session() as db:
            # Get the step
            step = db.query(PlanStep).filter(
                PlanStep.step_id == UUID(bottleneck_id)
            ).first()
            
            if not step:
                return jsonify({"ok": False, "error": "Step not found"}), 404
            
            if not step.can_system_answer:
                return jsonify({"ok": False, "error": "This task cannot be handled by Mobius"}), 400
            
            # Update step assignment
            step.assigned_to_user_id = None  # Unassign from user
            step.assignee_type = "mobius"  # Set assignee type for UI display
            step.status = StepStatus.CURRENT
            
            # Record the assignment mode (would trigger agent execution)
            answer = StepAnswer(
                step_id=step.step_id,
                answer_code=f"assigned_{mode}",
                answered_by=g.user_id,
                answer_mode=AnswerMode.AGENTIC if mode == 'agentic' else AnswerMode.COPILOT,
            )
            db.add(answer)
            db.commit()
            
            return jsonify({
                "ok": True,
                "step_id": str(step.step_id),
                "mode": mode,
                "message": "Mobius is working on it...",
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in assign_to_mobius: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/assign-bulk
# =============================================================================

@sidecar_bp.route('/sidecar/assign-bulk', methods=['POST'])
@require_auth
def bulk_assign_to_mobius():
    """
    Bulk assign multiple bottlenecks to Mobius.
    
    Body:
        session_id: string
        patient_key: string
        bottleneck_ids: string[] (step_ids)
    """
    try:
        data = request.get_json() or {}
        bottleneck_ids = data.get('bottleneck_ids', [])
        
        if not bottleneck_ids:
            return jsonify({"ok": False, "error": "No bottleneck_ids provided"}), 400
        
        with get_db_session() as db:
            assigned_count = 0
            skipped_count = 0
            
            for bid in bottleneck_ids:
                step = db.query(PlanStep).filter(
                    PlanStep.step_id == UUID(bid)
                ).first()
                
                if not step:
                    skipped_count += 1
                    continue
                
                if not step.can_system_answer:
                    skipped_count += 1
                    continue
                
                # Assign to Mobius
                step.assigned_to_user_id = None
                step.assignee_type = "mobius"  # Set assignee type for UI display
                step.status = StepStatus.CURRENT
                
                answer = StepAnswer(
                    step_id=step.step_id,
                    answer_code="assigned_agentic_bulk",
                    answered_by=g.user_id,
                    answer_mode=AnswerMode.AGENTIC,
                )
                db.add(answer)
                assigned_count += 1
            
            db.commit()
            
            return jsonify({
                "ok": True,
                "assigned_count": assigned_count,
                "skipped_count": skipped_count,
                "message": f"Assigned {assigned_count} items to Mobius",
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in bulk_assign_to_mobius: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/own
# =============================================================================

@sidecar_bp.route('/sidecar/own', methods=['POST'])
@require_auth
def take_ownership():
    """
    User takes ownership of a bottleneck ("I'll handle this").
    
    Body:
        session_id: string
        patient_key: string
        bottleneck_id: string (step_id)
        initial_note: string (optional)
    """
    try:
        data = request.get_json() or {}
        patient_key = data.get('patient_key')
        bottleneck_id = data.get('bottleneck_id')
        initial_note = data.get('initial_note')
        
        if not bottleneck_id:
            return jsonify({"ok": False, "error": "Missing bottleneck_id"}), 400
        
        with get_db_session() as db:
            # Get the step
            step = db.query(PlanStep).filter(
                PlanStep.step_id == UUID(bottleneck_id)
            ).first()
            
            if not step:
                return jsonify({"ok": False, "error": "Step not found"}), 404
            
            # Get plan for patient context
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.plan_id == step.plan_id
            ).first()
            
            if not plan:
                return jsonify({"ok": False, "error": "Plan not found"}), 404
            
            # Get patient context
            patient_context = db.query(PatientContext).filter(
                PatientContext.patient_context_id == plan.patient_context_id
            ).first()
            
            patient_name = patient_context.display_name if patient_context else "Patient"
            
            # Update step assignment
            step.assigned_to_user_id = g.user_id
            step.assignee_type = "user"  # Set assignee type for UI display
            step.status = StepStatus.CURRENT
            
            # Create user-owned task record
            owned_task = create_user_owned_task(
                db=db,
                user_id=g.user_id,
                tenant_id=g.tenant_id,
                plan_step_id=step.step_id,
                plan_id=plan.plan_id,
                patient_context_id=plan.patient_context_id,
                question_text=step.question_text,
                patient_name=patient_name,
                patient_key=patient_key or str(plan.patient_context_id),
                initial_note=initial_note,
            )
            
            # Record the ownership answer
            answer = StepAnswer(
                step_id=step.step_id,
                answer_code="user_owned",
                answered_by=g.user_id,
                answer_mode=AnswerMode.USER_DRIVEN,
            )
            db.add(answer)
            db.commit()
            
            return jsonify({
                "ok": True,
                "step_id": str(step.step_id),
                "ownership_id": str(owned_task.ownership_id),
                "message": "You're on it",
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in take_ownership: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/workflow
# =============================================================================

@sidecar_bp.route('/sidecar/workflow', methods=['POST'])
@require_auth
def set_workflow_mode():
    """
    Set workflow mode for a resolution plan.
    Called when user accepts batch recommendation from Mini or selects mode in Sidecar.
    
    Body:
        patient_key: string
        plan_id: string (optional - if not provided, uses active plan for patient)
        mode: "mobius" | "together" | "manual"
        note: string (optional)
    """
    try:
        data = request.get_json() or {}
        patient_key = data.get('patient_key')
        plan_id = data.get('plan_id')
        mode = data.get('mode')
        note = data.get('note')
        
        if not mode:
            return jsonify({"ok": False, "error": "Missing mode"}), 400
        
        if mode not in ['mobius', 'together', 'manual']:
            return jsonify({"ok": False, "error": "Invalid mode. Must be 'mobius', 'together', or 'manual'"}), 400
        
        with get_db_session() as db:
            # Find the plan
            plan = None
            
            if plan_id:
                plan = db.query(ResolutionPlan).filter(
                    ResolutionPlan.plan_id == UUID(plan_id),
                    ResolutionPlan.tenant_id == g.tenant_id
                ).first()
            elif patient_key:
                # Find active plan for patient
                patient_context = db.query(PatientContext).filter(
                    PatientContext.tenant_id == g.tenant_id,
                    PatientContext.patient_key == patient_key
                ).first()
                
                if patient_context:
                    from app.models.resolution import PlanStatus
                    plan = db.query(ResolutionPlan).filter(
                        ResolutionPlan.patient_context_id == patient_context.patient_context_id,
                        ResolutionPlan.status == PlanStatus.ACTIVE
                    ).first()
            
            if not plan:
                return jsonify({"ok": False, "error": "Plan not found"}), 404
            
            # Update workflow mode
            plan.workflow_mode = mode
            plan.workflow_mode_set_at = datetime.utcnow()
            plan.workflow_mode_set_by = g.user_id
            
            # Add note if provided
            if note:
                plan_note = PlanNote(
                    plan_id=plan.plan_id,
                    user_id=g.user_id,
                    note_text=f"[Workflow: {mode}] {note}",
                )
                db.add(plan_note)
            
            db.commit()
            
            # Determine response message based on mode
            messages = {
                'mobius': "Mobius is on it. You'll be notified when complete.",
                'together': "Let's work on this together.",
                'manual': "Got it. Tracking your progress.",
            }
            
            return jsonify({
                "ok": True,
                "plan_id": str(plan.plan_id),
                "mode": mode,
                "message": messages.get(mode, "Workflow mode set."),
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in set_workflow_mode: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/resolve-override
# =============================================================================

@sidecar_bp.route('/sidecar/resolve-override', methods=['POST'])
@require_auth
def resolve_override():
    """
    User marks a plan/bottleneck as already resolved.
    This is an override - user knows the issue is resolved but system hasn't caught up.
    
    Body:
        patient_key: string
        plan_id: string (optional)
        resolution_note: string (required - user must explain how it was resolved)
    """
    try:
        data = request.get_json() or {}
        patient_key = data.get('patient_key')
        plan_id = data.get('plan_id')
        resolution_note = data.get('resolution_note', '').strip()
        
        if not resolution_note:
            return jsonify({"ok": False, "error": "Resolution note is required"}), 400
        
        with get_db_session() as db:
            # Find the plan
            plan = None
            
            if plan_id:
                plan = db.query(ResolutionPlan).filter(
                    ResolutionPlan.plan_id == UUID(plan_id),
                    ResolutionPlan.tenant_id == g.tenant_id
                ).first()
            elif patient_key:
                # Find active plan for patient
                patient_context = db.query(PatientContext).filter(
                    PatientContext.tenant_id == g.tenant_id,
                    PatientContext.patient_key == patient_key
                ).first()
                
                if patient_context:
                    from app.models.resolution import PlanStatus
                    plan = db.query(ResolutionPlan).filter(
                        ResolutionPlan.patient_context_id == patient_context.patient_context_id,
                        ResolutionPlan.status == PlanStatus.ACTIVE
                    ).first()
            
            if not plan:
                return jsonify({"ok": False, "error": "Plan not found"}), 404
            
            # Mark plan as resolved
            from app.models.resolution import PlanStatus
            plan.status = PlanStatus.RESOLVED
            plan.resolved_at = datetime.utcnow()
            plan.resolved_by = g.user_id
            plan.resolution_type = "user_override"
            plan.resolution_notes = resolution_note
            
            # Mark all pending/current steps as resolved
            for step in plan.steps:
                if step.status in [StepStatus.PENDING, StepStatus.CURRENT, StepStatus.ANSWERED]:
                    step.status = StepStatus.RESOLVED
                    step.resolved_at = datetime.utcnow()
            
            # Cascade to payment_probability (Layer 1)
            # Note: Sidecar can override specific bottlenecks, so cascade each gap_type
            if plan.gap_types:
                from app.services.bottleneck_cascade import cascade_bottleneck_override
                for gap_type in plan.gap_types:
                    cascade_bottleneck_override(
                        db=db,
                        patient_context_id=plan.patient_context_id,
                        bottleneck_factor=gap_type,  # e.g., "eligibility"
                        status="resolved",  # Sidecar resolve-override always means resolved
                        user_id=g.user_id,
                        submitted_at=datetime.utcnow(),
                        source_layer="layer2"
                    )
            
            db.commit()
            
            return jsonify({
                "ok": True,
                "plan_id": str(plan.plan_id),
                "message": "Marked as resolved.",
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in resolve_override: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/factor-mode
# =============================================================================

@sidecar_bp.route('/sidecar/factor-mode', methods=['POST'])
@require_auth
def set_factor_mode():
    """
    Set workflow mode for a specific factor.
    
    When mode is set, auto-assigns steps based on mode:
    - mobius: All steps assigned to mobius
    - together: can_system_answer=True -> mobius, else -> user
    - manual: All steps assigned to user
    
    Body:
        patient_key: string
        factor_type: string (attendance | eligibility | coverage | clean_claim | errors)
        mode: string (mobius | together | manual)
    """
    try:
        data = request.get_json() or {}
        patient_key = data.get('patient_key')
        factor_type = data.get('factor_type')
        mode = data.get('mode')
        
        if not factor_type:
            return jsonify({"ok": False, "error": "Missing factor_type"}), 400
        
        if not mode or mode not in ['mobius', 'together', 'manual']:
            return jsonify({"ok": False, "error": "Invalid mode. Must be 'mobius', 'together', or 'manual'"}), 400
        
        valid_factors = ['attendance', 'eligibility', 'coverage', 'clean_claim', 'errors']
        if factor_type not in valid_factors:
            return jsonify({"ok": False, "error": f"Invalid factor_type. Must be one of: {valid_factors}"}), 400
        
        with get_db_session() as db:
            # Find the plan
            plan = None
            
            if patient_key:
                patient_context = db.query(PatientContext).filter(
                    PatientContext.tenant_id == g.tenant_id,
                    PatientContext.patient_key == patient_key
                ).first()
                
                if patient_context:
                    from app.models.resolution import PlanStatus
                    plan = db.query(ResolutionPlan).filter(
                        ResolutionPlan.patient_context_id == patient_context.patient_context_id,
                        ResolutionPlan.status == PlanStatus.ACTIVE
                    ).first()
            
            if not plan:
                return jsonify({"ok": False, "error": "No active plan found"}), 404
            
            # Update factor_modes
            if plan.factor_modes is None:
                plan.factor_modes = {}
            
            # Need to create a new dict to trigger SQLAlchemy change detection
            new_factor_modes = dict(plan.factor_modes)
            new_factor_modes[factor_type] = mode
            plan.factor_modes = new_factor_modes
            
            # Auto-assign steps based on mode
            steps = db.query(PlanStep).filter(
                PlanStep.plan_id == plan.plan_id,
                PlanStep.factor_type == factor_type
            ).all()
            
            assignments = []
            for step in steps:
                if mode == "mobius":
                    step.assignee_type = "mobius"
                elif mode == "manual":
                    step.assignee_type = "user"
                elif mode == "together":
                    step.assignee_type = "mobius" if step.can_system_answer else "user"
                
                assignments.append({
                    "step_id": str(step.step_id),
                    "assignee_type": step.assignee_type
                })
            
            db.commit()
            
            return jsonify({
                "ok": True,
                "factor_type": factor_type,
                "mode": mode,
                "steps_updated": len(steps),
                "assignments": assignments,
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in set_factor_mode: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# POST /api/v1/sidecar/remedy
# =============================================================================

@sidecar_bp.route('/sidecar/remedy', methods=['POST'])
@require_auth
def add_remedy():
    """
    Add a user remedy - what the user tried that wasn't in predefined steps.
    
    This captures user innovation and feeds into the learning loop.
    Batch job can use this to improve future recommendations.
    
    Body:
        patient_key: string
        factor_type: string (eligibility | coverage | attendance | clean_claim | errors)
        remedy_text: string (what the user tried)
        outcome: string (worked | partial | failed)
        outcome_notes: string (optional details)
    """
    try:
        data = request.get_json() or {}
        patient_key = data.get('patient_key')
        factor_type = data.get('factor_type')
        remedy_text = data.get('remedy_text', '').strip()
        outcome = data.get('outcome')
        outcome_notes = data.get('outcome_notes', '').strip() or None
        
        # Validation
        if not patient_key:
            return jsonify({"ok": False, "error": "Missing patient_key"}), 400
        
        if not factor_type:
            return jsonify({"ok": False, "error": "Missing factor_type"}), 400
        
        valid_factors = ['attendance', 'eligibility', 'coverage', 'clean_claim', 'errors']
        if factor_type not in valid_factors:
            return jsonify({"ok": False, "error": f"Invalid factor_type. Must be one of: {valid_factors}"}), 400
        
        if not remedy_text:
            return jsonify({"ok": False, "error": "Missing remedy_text"}), 400
        
        if not outcome or outcome not in ['worked', 'partial', 'failed']:
            return jsonify({"ok": False, "error": "Invalid outcome. Must be 'worked', 'partial', or 'failed'"}), 400
        
        with get_db_session() as db:
            # Find patient context
            patient_context = db.query(PatientContext).filter(
                PatientContext.tenant_id == g.tenant_id,
                PatientContext.patient_key == patient_key
            ).first()
            
            if not patient_context:
                return jsonify({"ok": False, "error": "Patient not found"}), 404
            
            # Find active plan (optional)
            from app.models.resolution import PlanStatus
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.patient_context_id == patient_context.patient_context_id,
                ResolutionPlan.status == PlanStatus.ACTIVE
            ).first()
            
            # Create remedy
            remedy = UserRemedy(
                patient_context_id=patient_context.patient_context_id,
                plan_id=plan.plan_id if plan else None,
                factor_type=factor_type,
                remedy_text=remedy_text,
                outcome=outcome,
                outcome_notes=outcome_notes,
                created_by=g.user_id,
            )
            db.add(remedy)
            db.commit()
            
            return jsonify({
                "ok": True,
                "remedy_id": str(remedy.remedy_id),
                "message": "Remedy recorded. Thanks for the feedback!",
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in add_remedy: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# GET /api/v1/sidecar/evidence
# =============================================================================

@sidecar_bp.route('/sidecar/evidence', methods=['GET'])
@require_auth
def get_evidence():
    """
    Get evidence (Layer 4/5/6) for a factor or step.
    
    Query params:
        patient_key: string
        factor: string (optional - get all evidence for factor)
        step_id: string (optional - get evidence for specific step)
    """
    try:
        patient_key = request.args.get('patient_key')
        factor_type = request.args.get('factor')
        step_id = request.args.get('step_id')
        
        with get_db_session() as db:
            from app.models.evidence import Evidence, SourceDocument
            
            # Find patient context
            patient_context = None
            if patient_key:
                patient_context = db.query(PatientContext).filter(
                    PatientContext.tenant_id == g.tenant_id,
                    PatientContext.patient_key == patient_key
                ).first()
            
            if not patient_context:
                return jsonify({"ok": False, "error": "Patient not found"}), 404
            
            # Query evidence
            query = db.query(Evidence).filter(
                Evidence.patient_context_id == patient_context.patient_context_id
            )
            
            if factor_type:
                query = query.filter(Evidence.factor_type == factor_type)
            
            # If step_id provided, filter to evidence linked to that step
            if step_id:
                step = db.query(PlanStep).filter(
                    PlanStep.step_id == UUID(step_id)
                ).first()
                
                if step and step.evidence_ids:
                    evidence_uuids = [UUID(eid) for eid in step.evidence_ids]
                    query = query.filter(Evidence.evidence_id.in_(evidence_uuids))
            
            evidence_list = query.all()
            
            # Build response
            evidence_response = []
            for e in evidence_list:
                # Get source document
                source_info = None
                if e.source_id:
                    source = db.query(SourceDocument).filter(
                        SourceDocument.source_id == e.source_id
                    ).first()
                    if source:
                        source_info = {
                            "source_id": str(source.source_id),
                            "label": source.document_label,
                            "type": source.document_type,
                            "system": source.source_system,
                            "date": source.document_date.isoformat() if source.document_date else None,
                            "trust_score": source.trust_score,
                        }
                
                evidence_response.append({
                    "evidence_id": str(e.evidence_id),
                    "factor_type": e.factor_type,
                    "fact_type": e.fact_type,
                    "fact_summary": e.fact_summary,
                    "fact_data": e.fact_data,
                    "impact_direction": e.impact_direction,
                    "impact_weight": e.impact_weight,
                    "is_stale": e.is_stale,
                    "source": source_info,
                })
            
            return jsonify({
                "ok": True,
                "factor_type": factor_type,
                "evidence": evidence_response,
                "count": len(evidence_response),
            })
    
    except Exception as e:
        print(f"[Sidecar API] Error in get_evidence: {e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500
