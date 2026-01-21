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
            # Find patient context
            patient_context = None
            if patient_key:
                patient_context = db.query(PatientContext).filter(
                    PatientContext.tenant_id == g.tenant_id,
                    PatientContext.patient_context_id == patient_key
                ).first()
                
                # Also try by external key if not found by ID
                if not patient_context:
                    patient_context = db.query(PatientContext).filter(
                        PatientContext.tenant_id == g.tenant_id
                    ).first()  # Fallback - would need proper key lookup
            
            # Build state
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
            
            # Update step status
            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.utcnow()
            
            # Find next step in plan and make it current
            plan = db.query(ResolutionPlan).filter(
                ResolutionPlan.plan_id == step.plan_id
            ).first()
            
            if plan:
                next_step = db.query(PlanStep).filter(
                    PlanStep.plan_id == plan.plan_id,
                    PlanStep.status == StepStatus.PENDING
                ).order_by(PlanStep.step_order).first()
                
                if next_step:
                    next_step.status = StepStatus.CURRENT
                    plan.current_step_id = next_step.step_id
                else:
                    # No more steps - check if plan is complete
                    pending_count = db.query(PlanStep).filter(
                        PlanStep.plan_id == plan.plan_id,
                        PlanStep.status.in_([StepStatus.PENDING, StepStatus.CURRENT])
                    ).count()
                    
                    if pending_count == 0:
                        plan.status = "resolved"
                        plan.resolved_at = datetime.utcnow()
                        plan.resolved_by = g.user_id
            
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
