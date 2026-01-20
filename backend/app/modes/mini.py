"""
Mini surface endpoints for Mobius OS.

Provides compact patient state display for the floating widget.
Delegates to PatientDataAgent for data and DecisionOrchestrator for decisions.
Persists System Responses and handles acknowledgements via services.

Loads payment_probability and task_instances for decision agents.
"""

import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify

from app.agents.patient_data_agent import PatientDataAgent
from app.agents.decision_agents import DecisionOrchestrator, DecisionContext
from app.services.patient_state import PatientStateService
from app.services.event_log import EventLogService
from app.services.projection import ProjectionService
from app.db.postgres import get_db_session
from app.models.probability import PaymentProbability, TaskInstance, TaskTemplate, UserPreference
from app.models.patient import PatientContext

bp = Blueprint("mini", __name__, url_prefix="/api/v1/mini")

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
            # LLM-generated problem statement
            "problem_statement": prob.problem_statement,
            "problem_details": prob.problem_details,
        }
    except Exception as e:
        print(f"[mini] Error loading payment probability: {e}")
        return None


def _get_task_count(patient_context_id: uuid.UUID) -> int:
    """Get count of pending tasks for badge display."""
    try:
        db = get_db_session()
        count = db.query(TaskInstance).filter(
            TaskInstance.patient_context_id == patient_context_id,
            TaskInstance.status == "pending"
        ).count()
        return count
    except Exception as e:
        print(f"[mini] Error counting tasks: {e}")
        return 0


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
                "is_blocking": False,  # Could be derived from steps
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
                    "is_blocking": False,  # Template-level blocking
                } if template else {}
            })
        
        return result
    except Exception as e:
        print(f"[mini] Error loading task instances: {e}")
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
        print(f"[mini] Error loading user preference: {e}")
        return None


@bp.route("/status", methods=["POST"])
def status():
    """
    Return proceed/tasking status for the Mini widget.

    Reads patient data from PostgreSQL, computes decisions via agents,
    persists the SystemResponse, and updates Firestore projection.
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    tenant_id = _get_tenant_id(data)
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
    user_id = _get_user_id(data)
    
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
    mini_payload = computed_response.to_mini_payload()
    
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
                surface_type="mini",
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
            # Log error but don't fail the request - decisions are still computed
            print(f"[mini/status] Error persisting SystemResponse: {e}")
            import traceback
            traceback.print_exc()
    
    # Build needs_attention from proceed + problem_statement
    proceed_data = mini_payload["proceed"]
    problem_statement = None
    if payment_probability:
        problem_statement = payment_probability.get("problem_statement")
    
    # If no problem_statement from batch job, generate a fallback
    if not problem_statement and payment_probability:
        lowest_factor = payment_probability.get("lowest_factor")
        lowest_reason = payment_probability.get("lowest_factor_reason")
        if lowest_factor:
            action_map = {
                "eligibility": "Confirm insurance eligibility",
                "coverage": "Verify service coverage",
                "attendance": "Confirm appointment attendance",
                "errors": "Review billing information",
            }
            action = action_map.get(lowest_factor, "Review patient information")
            if lowest_reason:
                problem_statement = f"{action} - {lowest_reason}"
            else:
                problem_statement = action
    
    # Get attention status from patient context
    attention_status = None
    if patient_context:
        attention_status = patient_context.attention_status
    
    # Get task count for badge
    task_count = 0
    if patient_context:
        task_count = _get_task_count(patient_context.patient_context_id)
    
    return jsonify({
        "ok": True,
        "session_id": session_id,
        "surface": "mini",
        "system_response_id": str(system_response_id) if system_response_id else None,
        "patient": {
            "found": bool(patient_key and patient_snapshot),
            "display_name": patient_snapshot.get("display_name") if patient_snapshot else None,
            "id_masked": patient_snapshot.get("id_masked") if patient_snapshot else None,
        } if patient_key else None,
        # New "needs_attention" format (replaces "proceed")
        "needs_attention": {
            "color": proceed_data["color"],
            "problem_statement": problem_statement,
            "user_status": attention_status,  # "resolved" | "confirmed_unresolved" | "unable_to_confirm" | null
        },
        # Keep "proceed" for backwards compatibility
        "proceed": proceed_data,
        # Task info for badge/sidecar link
        "has_tasks": task_count > 0,
        "task_count": task_count,
        # Mode info (for future sidecar)
        "mode": mini_payload.get("mode"),
        "computed_at": mini_payload["computed_at"],
    })


@bp.route("/ack", methods=["POST"])
def submit_ack():
    """
    Submit acknowledgement from Mini (same semantics as Sidecar).

    This is the state-committing Send action (PRD §1.4, §6.3).
    Persists submission, logs event, and updates Firestore.
    
    Now also handles attention_status updates:
    - "resolved" -> user resolved the issue
    - "confirmed_unresolved" -> issue confirmed but needs sidecar
    - "unable_to_confirm" -> needs investigation in sidecar
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
    
    # New: attention_status for "Needs Attention" workflow
    attention_status = data.get("attention_status")  # "resolved" | "confirmed_unresolved" | "unable_to_confirm"
    
    # Determine if we should signal frontend to open sidecar
    open_sidecar = attention_status in ("confirmed_unresolved", "unable_to_confirm")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    
    # Note is optional if attention_status is provided (status change is acknowledgement)
    if not note_text and not attention_status:
        return jsonify({"error": "note or attention_status is required"}), 400

    submitted_at = datetime.utcnow()
    submission_id = None

    # Get patient context for persistence
    patient_context = None
    patient_context_obj = None
    if patient_key:
        patient_context = _patient_agent.get_patient_context(tenant_id, patient_key)
        # Also get the actual ORM object to update attention_status
        if patient_context:
            db = get_db_session()
            patient_context_obj = db.query(PatientContext).filter(
                PatientContext.patient_context_id == patient_context.patient_context_id
            ).first()

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
    
    # Update attention_status on patient_context if provided
    if attention_status and patient_context_obj:
        try:
            db = get_db_session()
            patient_context_obj.attention_status = attention_status
            patient_context_obj.attention_status_at = submitted_at
            patient_context_obj.attention_status_by_id = user_id
            db.commit()
            print(f"[mini/ack] Updated attention_status to '{attention_status}' for patient {patient_key}")
        except Exception as e:
            print(f"[mini/ack] Error updating attention_status: {e}")
            db.rollback()

    # Persist submission to PostgreSQL (if we have note_text)
    if patient_context and system_response_id and note_text:
        try:
            submission = _patient_state_service.create_submission(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                system_response_id=system_response_id,
                user_id=user_id,
                note_text=note_text,
                override_proceed=override_proceed or attention_status,  # Map attention_status to override_proceed
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
                has_overrides=bool(override_proceed or override_tasking or attention_status),
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
            print(f"[mini/ack] Error persisting submission: {e}")
            return jsonify({"error": f"Failed to save submission: {str(e)}"}), 500
    
    # Even without note_text, if attention_status changed, log as acknowledgement
    elif patient_context and attention_status:
        try:
            _event_log_service.log_user_acknowledged(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                user_id=user_id,
                submission_id=None,
                system_response_id=system_response_id,
                has_overrides=True,
                correlation_id=correlation_id,
            )
        except Exception as e:
            print(f"[mini/ack] Error logging acknowledgement: {e}")

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "surface": "mini",
        "submission_id": str(submission_id) if submission_id else None,
        "submission": {
            "note": note_text,
            "override_proceed": override_proceed,
            "override_tasking": override_tasking,
            "attention_status": attention_status,
            "submitted_at": submitted_at.isoformat(),
        },
        "open_sidecar": open_sidecar,  # Signal frontend to open sidecar
    })


@bp.route("/note", methods=["POST"])
def note():
    """
    Accept a note submission from the mini widget.

    DEPRECATED: Use /ack endpoint instead. Kept for backwards compatibility.
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    note_text = (data.get("note") or "").strip()

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not note_text:
        return jsonify({"error": "note is required"}), 400

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "note": note_text,
    })


@bp.route("/issue", methods=["POST"])
def report_issue():
    """
    Report a new issue from the Mini widget.
    
    Creates a UserReportedIssue record for batch job processing.
    The batch job will calculate probability and create PaymentProbability.
    """
    from app.models.user_issue import UserReportedIssue
    
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    patient_key = (data.get("patient_key") or "").strip()
    issue_text = (data.get("issue_text") or "").strip()
    
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not patient_key:
        return jsonify({"error": "patient_key is required"}), 400
    if not issue_text:
        return jsonify({"error": "issue_text is required"}), 400
    if len(issue_text) > 500:
        return jsonify({"error": "issue_text must be 500 characters or less"}), 400
    
    tenant_id = _get_tenant_id(data)
    user_id = _get_user_id(data)
    
    with get_db_session() as session:
        # Find or create PatientContext
        patient_context = session.query(PatientContext).filter(
            PatientContext.tenant_id == tenant_id,
            PatientContext.patient_key == patient_key
        ).first()
        
        if not patient_context:
            # Create new PatientContext if doesn't exist
            patient_context = PatientContext(
                tenant_id=tenant_id,
                patient_key=patient_key,
            )
            session.add(patient_context)
            session.flush()
        
        # Create the UserReportedIssue
        issue = UserReportedIssue(
            patient_context_id=patient_context.patient_context_id,
            reported_by_id=user_id,
            issue_text=issue_text,
            status="pending",
        )
        session.add(issue)
        session.commit()
        
        issue_id = str(issue.issue_id)
    
    # Log the event
    _event_log_service.append_event(
        tenant_id=tenant_id,
        event_type="issue_reported",
        actor_user_id=user_id if user_id else None,
        payload={
            "entity_type": "user_reported_issue",
            "entity_id": issue_id,
            "session_id": session_id,
            "patient_key": patient_key,
            "issue_text": issue_text,
        }
    )
    
    return jsonify({
        "ok": True,
        "issue_id": issue_id,
    })


@bp.route("/patient/search", methods=["GET"])
def patient_search():
    """
    Patient search endpoint for the mini's correction modal.

    Returns matching patients from the database.
    """
    q = (request.args.get("q") or "").strip()
    tenant_id_str = request.args.get("tenant_id")
    
    try:
        limit = int(request.args.get("limit") or "8")
    except ValueError:
        limit = 8
    
    # Get tenant ID
    tenant_id = DEFAULT_TENANT_ID
    if tenant_id_str:
        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except ValueError:
            pass

    if not q:
        return jsonify({"ok": True, "q": q, "results": []})

    # Search using PatientDataAgent
    results = _patient_agent.search_patients(tenant_id, q, limit=min(limit, 25))

    return jsonify({"ok": True, "q": q, "results": results})
