"""
Sidecar surface endpoints for Mobius OS.

Provides expanded context, history, and inbox for the full sidebar view.
Delegates to PatientDataAgent for data and DecisionOrchestrator for decisions.
Persists System Responses and handles acknowledgements via services.
"""

import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from sqlalchemy import desc

from app.agents.patient_data_agent import PatientDataAgent
from app.agents.decision_agents import DecisionOrchestrator, DecisionContext
from app.services.patient_state import PatientStateService
from app.services.event_log import EventLogService
from app.services.projection import ProjectionService
from app.db.postgres import get_db_session
from app.models import EventLog, Assignment
from app.models.probability import PaymentProbability, TaskInstance, TaskTemplate, UserPreference

bp = Blueprint("sidecar", __name__, url_prefix="/api/v1/sidecar")

# Initialize agents and services
_patient_agent = PatientDataAgent()
_orchestrator = DecisionOrchestrator()
_patient_state_service = PatientStateService()
_event_log_service = EventLogService()
_projection_service = ProjectionService()

# Default tenant/user IDs for development (no auth yet)
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _get_tenant_id(data: dict) -> uuid.UUID:
    """Get tenant ID from request data or use default."""
    tenant_id = data.get("tenant_id")
    if tenant_id:
        try:
            return uuid.UUID(tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


def _get_user_id(data: dict) -> uuid.UUID:
    """Get user ID from request data or use default (no auth yet)."""
    user_id = data.get("user_id")
    if user_id:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    return DEFAULT_USER_ID


def _get_payment_probability(patient_context_id: uuid.UUID) -> dict | None:
    """Load latest payment probability for a patient."""
    try:
        db = get_db_session()
        prob = db.query(PaymentProbability).filter(
            PaymentProbability.patient_context_id == patient_context_id
        ).order_by(PaymentProbability.computed_at.desc()).first()
        
        if not prob:
            return None
        
        return {
            "overall_probability": prob.overall_probability,
            "confidence": prob.confidence,
            "prob_attendance": prob.prob_appointment_attendance,
            "prob_eligibility": prob.prob_eligibility,
            "prob_coverage": prob.prob_coverage,
            "prob_no_errors": prob.prob_no_errors,
            "lowest_factor": prob.lowest_factor,
            "lowest_factor_reason": prob.lowest_factor_reason,
            "target_date": prob.target_date.isoformat() if prob.target_date else None,
        }
    except Exception as e:
        print(f"[sidecar] Error loading payment probability: {e}")
        return None


def _get_task_instances(patient_context_id: uuid.UUID) -> list:
    """Load pending task instances for a patient with template info."""
    try:
        db = get_db_session()
        instances = db.query(TaskInstance).filter(
            TaskInstance.patient_context_id == patient_context_id,
            TaskInstance.status == "pending"
        ).all()
        
        result = []
        for inst in instances:
            # Load template
            template = db.query(TaskTemplate).filter(
                TaskTemplate.template_id == inst.template_id
            ).first()
            
            result.append({
                "instance_id": str(inst.instance_id),
                "status": inst.status,
                "priority": inst.priority,
                "assigned_to_type": inst.assigned_to_type,
                "reason": inst.reason,
                "is_blocking": False,
                "template": {
                    "template_id": str(template.template_id) if template else None,
                    "task_code": template.task_code if template else None,
                    "task_name": template.task_name if template else None,
                    "can_system_execute": template.can_system_execute if template else False,
                    "requires_human_in_loop": template.requires_human_in_loop if template else False,
                    "success_rate_threshold": template.success_rate_threshold if template else 0.8,
                    "historical_success_rate": template.historical_success_rate if template else None,
                    "value_tier": template.value_tier if template else None,
                    "always_requires_oversight": template.always_requires_oversight if template else False,
                    "is_blocking": False,
                } if template else {}
            })
        
        return result
    except Exception as e:
        print(f"[sidecar] Error loading task instances: {e}")
        return []


def _get_user_preference(user_id: uuid.UUID) -> dict | None:
    """Load user preference for oversight settings."""
    try:
        db = get_db_session()
        pref = db.query(UserPreference).filter(
            UserPreference.user_id == user_id
        ).first()
        
        if not pref:
            return None
        
        return {
            "always_require_oversight": pref.always_require_oversight,
        }
    except Exception as e:
        print(f"[sidecar] Error loading user preference: {e}")
        return None


@bp.route("/state", methods=["POST"])
def get_state():
    """
    Get full patient state for Sidecar rendering.

    Reads patient data from PostgreSQL, computes decisions via agents,
    persists the SystemResponse, and updates Firestore projection.
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    tenant_id = _get_tenant_id(data)
    user_id = _get_user_id(data)
    patient_key = (data.get("patient_key") or "").strip()
    correlation_id = data.get("correlation_id") or session_id

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    # Get patient snapshot from database
    patient_snapshot = None
    patient_context = None
    payment_probability = None
    task_instances = []
    user_preference = None
    
    if patient_key:
        patient_snapshot = _patient_agent.get_patient_snapshot_by_key(tenant_id, patient_key)
        patient_context = _patient_agent.get_patient_context(tenant_id, patient_key)
        
        # Load additional data for decision agents
        if patient_context:
            payment_probability = _get_payment_probability(patient_context.patient_context_id)
            task_instances = _get_task_instances(patient_context.patient_context_id)
    
    # Load user preference for oversight settings
    user_preference = _get_user_preference(user_id)
    
    # Build decision context with all available data
    context = DecisionContext(
        tenant_id=str(tenant_id),
        patient_key=patient_key or None,
        session_id=session_id,
        user_id=str(user_id),
        patient_snapshot=patient_snapshot,
        payment_probability=payment_probability,
        task_instances=task_instances,
        user_preference=user_preference,
    )
    
    # Compute decisions using orchestrator
    computed_response = _orchestrator.compute_all(context)
    sidecar_payload = computed_response.to_sidecar_payload()
    
    # Persist SystemResponse to PostgreSQL (if patient context exists)
    system_response_id = None
    if patient_context:
        try:
            # Get reasoning from proceed agent result
            proceed_result = computed_response.agent_results.get("ProceedDecisionAgent")
            proceed_reasoning = proceed_result.reasoning if proceed_result else None
            
            db_response = _patient_state_service.create_system_response(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                proceed_indicator=computed_response.proceed_indicator.value,
                execution_mode=computed_response.execution_mode.value if computed_response.execution_mode else None,
                tasking_summary=computed_response.tasking.summary if computed_response.tasking else None,
                rationale=proceed_reasoning,
                surface_type="sidecar",
                correlation_id=correlation_id,
            )
            system_response_id = db_response.system_response_id
            
            # Log System.Response event
            _event_log_service.log_system_response(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                system_response_id=system_response_id,
                proceed_indicator=computed_response.proceed_indicator.value,
                execution_mode=computed_response.execution_mode.value if computed_response.execution_mode else None,
                correlation_id=correlation_id,
            )
            
            # Update Firestore projection
            _projection_service.update_patient_state_from_response(
                tenant_id=tenant_id,
                patient_key=patient_key,
                system_response_id=system_response_id,
                proceed_indicator=computed_response.proceed_indicator.value,
                execution_mode=computed_response.execution_mode.value if computed_response.execution_mode else None,
                tasking_summary=computed_response.tasking.summary if computed_response.tasking else None,
                computed_at=db_response.computed_at,
            )
        except Exception as e:
            print(f"[sidecar/state] Error persisting SystemResponse: {e}")
            import traceback
            traceback.print_exc()
    
    # Get recent history for this patient
    history_events = []
    if patient_context:
        try:
            db = get_db_session()
            events = (
                db.query(EventLog)
                .filter(EventLog.patient_context_id == patient_context.patient_context_id)
                .order_by(desc(EventLog.created_at))
                .limit(10)
                .all()
            )
            history_events = [
                {
                    "event_type": e.event_type,
                    "created_at": e.created_at.isoformat(),
                    "payload": e.payload_json,
                }
                for e in events
            ]
        except Exception as e:
            print(f"[sidecar/state] Error loading history: {e}")
    
    # Get inbox preview for this user
    inbox_preview = {"open_count": 0, "assignments": []}
    try:
        db = get_db_session()
        open_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.assigned_to_user_id == user_id,
                Assignment.status == "open",
            )
            .limit(5)
            .all()
        )
        inbox_preview = {
            "open_count": len(open_assignments),
            "assignments": [
                {
                    "assignment_id": str(a.assignment_id),
                    "patient_key": _get_patient_key_for_assignment(a),
                    "reason_code": a.reason_code,
                }
                for a in open_assignments
            ],
        }
    except Exception as e:
        print(f"[sidecar/state] Error loading inbox: {e}")
    
    return jsonify({
        "ok": True,
        "session_id": session_id,
        "surface": "sidecar",
        "system_response_id": str(system_response_id) if system_response_id else None,
        "patient_state": {
            "found": bool(patient_key and patient_snapshot),
            "patient_key": patient_key or None,
            "snapshot": patient_snapshot,
            "system_response": {
                "proceed_indicator": sidecar_payload["proceed_indicator"],
                "proceed_text": sidecar_payload["proceed_text"],
                "execution_mode": sidecar_payload["execution_mode"],
                "tasking": sidecar_payload["tasking"],
                "outcome": sidecar_payload["outcome"],
                "computed_at": sidecar_payload["computed_at"],
            },
        },
        "policy": sidecar_payload["policy"],
        "assignment": sidecar_payload["assignment"],
        "history": history_events,
        "inbox_preview": inbox_preview,
    })


def _get_patient_key_for_assignment(assignment: Assignment) -> str:
    """Get patient_key from assignment's patient_context."""
    try:
        if assignment.patient_context:
            return assignment.patient_context.patient_key
    except Exception:
        pass
    return ""


@bp.route("/ack", methods=["POST"])
def submit_ack():
    """
    Submit acknowledgement from Sidecar (same semantics as Mini).

    This is the state-committing Send action.
    Persists submission, logs event, and updates Firestore.
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    tenant_id = _get_tenant_id(data)
    user_id = _get_user_id(data)
    patient_key = (data.get("patient_key") or "").strip()
    system_response_id_str = data.get("system_response_id")
    note_text = (data.get("note") or "").strip()
    override_proceed = data.get("override_proceed")
    override_tasking = data.get("override_tasking")
    correlation_id = data.get("correlation_id") or session_id

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not note_text:
        return jsonify({"error": "note is required"}), 400

    submitted_at = datetime.utcnow()
    submission_id = None

    # Get patient context for persistence
    patient_context = None
    if patient_key:
        patient_context = _patient_agent.get_patient_context(tenant_id, patient_key)

    # Parse system_response_id if provided
    system_response_id = None
    if system_response_id_str:
        try:
            system_response_id = uuid.UUID(system_response_id_str)
        except ValueError:
            pass

    # If no system_response_id provided, get the latest one
    if not system_response_id and patient_context:
        latest = _patient_state_service.get_latest_system_response(patient_context.patient_context_id)
        if latest:
            system_response_id = latest.system_response_id

    # Persist submission to PostgreSQL
    if patient_context and system_response_id:
        try:
            submission = _patient_state_service.create_submission(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                system_response_id=system_response_id,
                user_id=user_id,
                note_text=note_text,
                override_proceed=override_proceed,
                override_tasking=override_tasking,
            )
            submission_id = submission.mini_submission_id
            
            # Log User.Acknowledged event
            _event_log_service.log_user_acknowledged(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                user_id=user_id,
                submission_id=submission_id,
                system_response_id=system_response_id,
                has_overrides=bool(override_proceed or override_tasking),
                correlation_id=correlation_id,
            )
            
            # Update Firestore projection
            _projection_service.update_patient_state_from_submission(
                tenant_id=tenant_id,
                patient_key=patient_key,
                submission_id=submission_id,
                user_id=user_id,
                submitted_at=submitted_at,
            )
        except Exception as e:
            print(f"[sidecar/ack] Error persisting submission: {e}")
            return jsonify({"error": f"Failed to save submission: {str(e)}"}), 500

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "surface": "sidecar",
        "submission_id": str(submission_id) if submission_id else None,
        "submission": {
            "note": note_text,
            "override_proceed": override_proceed,
            "override_tasking": override_tasking,
            "submitted_at": submitted_at.isoformat(),
        },
    })


@bp.route("/history", methods=["POST"])
def get_history():
    """
    Get event history for current patient context.

    Returns audit-safe events (no raw PHI).
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    tenant_id = _get_tenant_id(data)
    patient_key = (data.get("patient_key") or "").strip()
    limit = min(int(data.get("limit") or 50), 100)

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    events = []
    has_more = False

    # Get patient context
    patient_context = None
    if patient_key:
        patient_context = _patient_agent.get_patient_context(tenant_id, patient_key)

    # Query EventLog
    if patient_context:
        try:
            db = get_db_session()
            query = (
                db.query(EventLog)
                .filter(EventLog.patient_context_id == patient_context.patient_context_id)
                .order_by(desc(EventLog.created_at))
                .limit(limit + 1)  # +1 to check if there's more
            )
            results = query.all()
            
            has_more = len(results) > limit
            events = [
                {
                    "event_id": str(e.event_id),
                    "event_type": e.event_type,
                    "created_at": e.created_at.isoformat(),
                    "payload": e.payload_json,
                    "correlation_id": e.correlation_id,
                }
                for e in results[:limit]
            ]
        except Exception as e:
            print(f"[sidecar/history] Error loading events: {e}")

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "patient_key": patient_key or None,
        "events": events,
        "has_more": has_more,
    })


@bp.route("/inbox", methods=["POST"])
def get_inbox():
    """
    Get user's inbox (open assignments for offline pickup).
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    tenant_id = _get_tenant_id(data)
    user_id = _get_user_id(data)

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    assignments = []
    try:
        db = get_db_session()
        open_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.tenant_id == tenant_id,
                Assignment.assigned_to_user_id == user_id,
                Assignment.status == "open",
            )
            .order_by(desc(Assignment.created_at))
            .all()
        )
        assignments = [
            {
                "assignment_id": str(a.assignment_id),
                "patient_key": _get_patient_key_for_assignment(a),
                "reason_code": a.reason_code,
                "created_at": a.created_at.isoformat(),
                "status": a.status,
            }
            for a in open_assignments
        ]
    except Exception as e:
        print(f"[sidecar/inbox] Error loading assignments: {e}")

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "assignments": assignments,
    })
