"""
Mini surface endpoints for Mobius OS.

Provides compact patient state display for the floating widget.
Delegates to PatientDataAgent for data and DecisionOrchestrator for decisions.
Persists System Responses and handles acknowledgements via services.

Loads payment_probability and task_instances for decision agents.

User Awareness Sprint:
- Loads user profile for personalization
- Generates personalized greetings
- Filters quick actions based on user activities
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from flask import Blueprint, request, jsonify

from app.agents.patient_data_agent import PatientDataAgent
from app.agents.decision_agents import DecisionOrchestrator, DecisionContext
from app.services.patient_state import PatientStateService
from app.services.event_log import EventLogService
from app.services.projection import ProjectionService
from app.services.auth_service import get_auth_service
from app.services.user_context import get_user_context_service, UserProfile
from app.services.personalization import get_personalization_service
from app.services.bottleneck_cascade import cascade_bottleneck_override
from app.db.postgres import get_db_session
from app.models.probability import PaymentProbability, TaskInstance, TaskTemplate, UserPreference
from app.models.patient import PatientContext
from app.models.resolution import ResolutionPlan, PlanStep, PlanStatus, StepStatus
from app.models.activity import UserActivity

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


def _get_current_user() -> Optional[UserProfile]:
    """Get current user profile from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    print(f"[mini] DEBUG: Auth header present: {bool(auth_header)}, starts with Bearer: {auth_header.startswith('Bearer ')}")
    if not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    print(f"[mini] DEBUG: Token length: {len(token)}")
    auth_service = get_auth_service()
    user = auth_service.validate_access_token(token)
    print(f"[mini] DEBUG: Token validation result: {user}")
    
    if not user:
        return None
    
    # Load full user profile
    user_context_service = get_user_context_service()
    profile = user_context_service.get_user_profile(user.user_id)
    print(f"[mini] DEBUG: User profile loaded: {profile.user_id if profile else None}")
    return profile


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
    """Get user ID from request data, auth token, or default."""
    # First check request data
    user_id = data.get("user_id")
    if user_id:
        try:
            return uuid.UUID(user_id)
        except ValueError:
            pass
    
    # Then try to get from auth token
    user_profile = _get_current_user()
    if user_profile:
        return user_profile.user_id
    
    # Fallback to default (should have a valid user in DB)
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
            # Batch recommendation fields (Workflow Mode UI)
            "agentic_confidence": prob.agentic_confidence,
            "recommended_mode": prob.recommended_mode,
            "recommendation_reason": prob.recommendation_reason,
            "agentic_actions": prob.agentic_actions,
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




def _map_factor_to_activities(factor_type: str) -> list:
    """Map factor type to activity codes that can handle it.
    
    This handles both explicit assignable_activities and legacy handle_* codes.
    """
    factor_activity_map = {
        "eligibility": ["verify_eligibility", "check_in_patients"],
        "coverage": ["prior_authorization"],
        "attendance": ["schedule_appointments", "patient_outreach", "check_in_patients"],
        "errors": ["submit_claims", "rework_denials"],
    }
    return factor_activity_map.get(factor_type, [])


def _step_matches_user_activities(step, user_activities: list) -> bool:
    """Check if a step matches user's activities.
    
    Matches if:
    1. Step's assignable_activities overlap with user_activities, OR
    2. Step's factor_type maps to activities that user has
    """
    if not user_activities or len(user_activities) == 0:
        return False
    
    step_activities = step.assignable_activities or []
    
    # Direct match: step activities overlap with user activities
    if step_activities:
        overlap = [a for a in step_activities if a in user_activities]
        if overlap:
            return True
    
    # Factor-based match: map factor_type to activities
    if step.factor_type:
        factor_activities = _map_factor_to_activities(step.factor_type)
        overlap = [a for a in factor_activities if a in user_activities]
        if overlap:
            return True
    
    # Handle legacy handle_* codes (map to factor activities)
    if step_activities:
        for activity in step_activities:
            if activity.startswith("handle_"):
                factor = activity.replace("handle_", "")
                factor_activities = _map_factor_to_activities(factor)
                overlap = [a for a in factor_activities if a in user_activities]
                if overlap:
                    return True
    
    return False


def _get_resolution_plan(patient_context_id: uuid.UUID, user_activities: list = None) -> dict | None:
    """Load resolution plan for Mini display (active OR resolved).
    
    Returns action-centric format with:
    - gap_types: what needs attention
    - current_step: the step to show in Mini (null if resolved)
    - progress: completion status per factor
    - actions_for_user: count of steps user can act on
    - status: 'active' or 'resolved'
    
    Any user with matching activities will see the task - no role check needed.
    """
    try:
        db = get_db_session()
        # Get any plan (active or resolved) - prefer active if multiple exist
        plan = db.query(ResolutionPlan).filter(
            ResolutionPlan.patient_context_id == patient_context_id,
            ResolutionPlan.status.in_([PlanStatus.ACTIVE, PlanStatus.RESOLVED])
        ).order_by(
            # Active plans first, then by updated_at descending
            ResolutionPlan.status.asc(),  # 'active' < 'resolved' alphabetically
            ResolutionPlan.updated_at.desc()
        ).first()
        
        if not plan:
            return None
        
        # For resolved plans, return simplified response
        if plan.status == PlanStatus.RESOLVED:
            return {
                "plan_id": str(plan.plan_id),
                "gap_types": plan.gap_types,
                "status": "resolved",
                "factors": {},
                "current_step": None,
                "actions_for_user": 0,
                "factor_modes": plan.factor_modes or {},
                "resolution_type": plan.resolution_type,
                "resolution_notes": plan.resolution_notes,
                "resolved_at": plan.resolved_at.isoformat() if plan.resolved_at else None,
            }
        
        # Build progress and count actions for active plans
        factors = {}
        actions_for_user = 0
        current_step_data = None
        matching_step_data = None  # Step that matches user's activities
        total_pending_steps = 0
        
        # Load steps explicitly from DB
        steps = db.query(PlanStep).filter(PlanStep.plan_id == plan.plan_id).all()
        print(f"[mini] DEBUG: Plan {plan.plan_id} has {len(steps)} steps")
        
        for step in steps:
            factor = step.factor_type or "general"
            if factor not in factors:
                factors[factor] = {"done": 0, "total": 0, "status": "pending"}
            factors[factor]["total"] += 1
            
            if step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED]:
                factors[factor]["done"] += 1
            elif step.status in [StepStatus.CURRENT, StepStatus.PENDING]:
                if step.status == StepStatus.CURRENT:
                    factors[factor]["status"] = "needs_action"
                total_pending_steps += 1
                
                # Format step data (only for CURRENT steps to show in UI)
                if step.status == StepStatus.CURRENT:
                    step_data = {
                        "step_id": str(step.step_id),
                        "step_code": step.step_code,
                        "question_text": step.question_text,
                        "step_type": step.step_type,
                        "input_type": step.input_type,
                        "answer_options": step.answer_options,
                        "system_suggestion": step.system_suggestion,
                        "factor_type": step.factor_type,
                        "assignable_activities": step.assignable_activities,
                    }
                
                # Check if this step matches user's activities (for both CURRENT and PENDING)
                # Any user with matching activities can see the task
                step_matches = _step_matches_user_activities(step, user_activities)
                print(f"[mini] DEBUG: Step {step.step_code} (status={step.status}) - user_activities={user_activities}, assignable={step.assignable_activities}, factor={step.factor_type}, matches={step_matches}")
                
                if step_matches:
                    actions_for_user += 1
                    if step.status == StepStatus.CURRENT and not matching_step_data:
                        matching_step_data = step_data
                        print(f"[mini] DEBUG: Setting matching_step_data to {step.step_code}")
                
                # Track first current step as fallback info
                if step.status == StepStatus.CURRENT and not current_step_data:
                    current_step_data = step_data
        
        # Show steps that match user's activities
        display_step = matching_step_data
        
        # Determine factor status
        for factor_data in factors.values():
            if factor_data["done"] == factor_data["total"]:
                factor_data["status"] = "ready"
        
        return {
            "plan_id": str(plan.plan_id),
            "gap_types": plan.gap_types,
            "status": "active",
            "factors": factors,
            "current_step": display_step,  # Shows steps matching user's activities
            "actions_for_user": actions_for_user,
            "total_pending": total_pending_steps,  # Total pending for all users
            # Show "other_role_tasks" if user has activities but no matching tasks
            "other_role_tasks": (total_pending_steps - actions_for_user) if (user_activities and len(user_activities) > 0 and actions_for_user < total_pending_steps) else 0,
            # Factor workflow modes (e.g., { "eligibility": "mobius" })
            "factor_modes": plan.factor_modes or {},
        }
    except Exception as e:
        print(f"[mini] Error loading resolution plan: {e}")
        import traceback
        traceback.print_exc()
        return None


def _get_user_activities(user_id: uuid.UUID) -> list:
    """Get activity codes for a user."""
    if not user_id:
        return []
    try:
        db = get_db_session()
        activities = db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).all()
        return [ua.activity.activity_code for ua in activities if ua.activity]
    except Exception:
        return []




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
    # Refresh to ensure we get fresh data from database (not cached)
    attention_status = None
    resolved_until = None
    is_resolved = False
    if patient_context:
        db = get_db_session()
        db.refresh(patient_context)  # Force refresh from database
        attention_status = patient_context.attention_status
        resolved_until = patient_context.resolved_until
        
        # Check if user previously marked as resolved - if so, check if still valid
        if attention_status == "resolved" and resolved_until:
            # User or system previously marked as resolved - check if still valid
            is_resolved = datetime.utcnow() < resolved_until
            if not is_resolved:
                # Suppression period expired - clear resolved status
                try:
                    patient_context.attention_status = None
                    patient_context.resolved_until = None
                    patient_context.override_color = None  # Clear override color when status expires
                    db.commit()
                    attention_status = None
                    print(f"[mini/status] Cleared expired resolved status for patient {patient_key}")
                except Exception as e:
                    print(f"[mini/status] Error clearing expired status: {e}")
                    db.rollback()
        elif attention_status == "resolved":
            # Resolved but no resolved_until set (legacy data) - still show as resolved
            is_resolved = True
        
        print(f"[mini/status] Patient {patient_key}: attention_status={attention_status}, resolved_until={resolved_until}, is_resolved={is_resolved}, proceed_indicator={computed_response.proceed_indicator.value}")
    
    # Get override_color if user has overridden
    override_color = None
    if patient_context:
        override_color = patient_context.override_color
        print(f"[mini/status] override_color={override_color}, proceed_indicator_color={proceed_data['color']}")
    
    # Determine final color: override_color takes precedence, otherwise use decision agent color
    final_color = override_color if override_color else proceed_data["color"]
    
    # Update proceed_data to use final_color for backwards compatibility
    proceed_data["color"] = final_color
    
    # Get task count for badge (legacy)
    # Suppress tasks if patient is resolved
    task_count = 0
    if patient_context and not is_resolved:
        task_count = _get_task_count(patient_context.patient_context_id)
    
    # User Awareness Sprint: Load user profile and personalization
    user_profile = _get_current_user()
    personalization_service = get_personalization_service()
    
    # Resolution Plan: Load active plan for action-centric UI
    # Suppress active steps if patient is resolved, but keep plan structure for history
    resolution_plan = None
    if patient_context:
        # Get user's activities from UserActivity table (their preferences)
        user_activities = _get_user_activities(user_profile.user_id) if user_profile else []
        print(f"[mini] DEBUG: user_profile={user_profile.user_id if user_profile else None}, user_activities={user_activities}")
        resolution_plan = _get_resolution_plan(patient_context.patient_context_id, user_activities)
        print(f"[mini] DEBUG: resolution_plan={resolution_plan}")
        
        # If resolved, suppress active steps but keep plan structure
        if is_resolved and resolution_plan:
            # Set actions_for_user to 0 and clear current_step
            resolution_plan["actions_for_user"] = 0
            resolution_plan["current_step"] = None
            resolution_plan["total_pending"] = 0
            resolution_plan["other_role_tasks"] = 0
    
    # Build personalization payload if user is authenticated
    user_data = None
    personalization_data = None
    
    if user_profile:
        user_data = {
            "user_id": str(user_profile.user_id),
            "display_name": user_profile.display_name,
            "greeting_name": user_profile.greeting_name,
            "is_onboarded": user_profile.is_onboarded,
            "activities": user_profile.activity_codes,
        }
        personalization_data = personalization_service.build_personalization_payload(
            user_profile,
            include_greeting=True,
            max_quick_actions=5
        )
    
    # Calculate agentic_confidence value (fix for 7800% bug)
    # agentic_confidence is stored as 0.0-1.0 in DB (Float), send as 0-100 integer for frontend
    agentic_conf = payment_probability.get("agentic_confidence") if payment_probability else None
    agentic_confidence_value = None
    if agentic_conf is not None:
        # Convert 0.0-1.0 to 0-100 integer
        # If value is > 1.0, it's already 0-100 scale (edge case), use as-is
        # Otherwise, convert 0.0-1.0 to 0-100
        if agentic_conf > 1.0:
            # Already 0-100 scale (edge case - shouldn't happen but handle it)
            agentic_confidence_value = int(agentic_conf)
        elif agentic_conf <= 1.0 and agentic_conf >= 0.0:
            # Normal case: 0.0-1.0 -> 0-100
            agentic_confidence_value = int(agentic_conf * 100)
        else:
            # Invalid value, set to None
            agentic_confidence_value = None
        print(f"[mini] DEBUG: agentic_confidence conversion - DB value: {agentic_conf}, converted: {agentic_confidence_value}")
    
    return jsonify({
        "ok": True,
        "session_id": session_id,
        "surface": "mini",
        "system_response_id": str(system_response_id) if system_response_id else None,
        # User Awareness Sprint: User and personalization data
        "user": user_data,
        "personalization": personalization_data,
        "authenticated": user_profile is not None,
        "patient": {
            "found": bool(patient_key and patient_snapshot),
            "display_name": patient_snapshot.get("display_name") if patient_snapshot else None,
            "id_masked": patient_snapshot.get("id_masked") if patient_snapshot else None,
        } if patient_key else None,
        # New "needs_attention" format (replaces "proceed")
        "needs_attention": {
            "color": final_color,  # Use override_color if set, otherwise decision agent color
            "problem_statement": problem_statement,
            "user_status": attention_status,  # "resolved" | "unresolved" | null
            "resolved_until": resolved_until.isoformat() if resolved_until else None,  # Include for frontend display
        },
        # Keep "proceed" for backwards compatibility
        "proceed": proceed_data,
        # Task info for badge/sidecar link (legacy)
        "has_tasks": task_count > 0,
        "task_count": task_count,
        # Resolution Plan: Action-centric UI data
        "resolution_plan": resolution_plan,
        "actions_for_user": resolution_plan.get("actions_for_user", 0) if resolution_plan else 0,
        # Mode info (for future sidecar)
        "mode": mini_payload.get("mode"),
        "computed_at": mini_payload["computed_at"],
        # Batch job recommendation for workflow mode (Workflow Mode UI)
        "agentic_confidence": agentic_confidence_value,
        "recommended_mode": payment_probability.get("recommended_mode") if payment_probability else None,
        "recommendation_reason": payment_probability.get("recommendation_reason") if payment_probability else None,
        "agentic_actions": payment_probability.get("agentic_actions") if payment_probability else None,
    })


@bp.route("/ack", methods=["POST"])
def submit_ack():
    """
    Submit acknowledgement from Mini (same semantics as Sidecar).

    This is the state-committing Send action (PRD §1.4, §6.3).
    Persists submission, logs event, and updates Firestore.
    
    Now also handles attention_status updates:
    - "resolved" -> user says it's resolved (even if system says there are issues)
    - "unresolved" -> user says it's unresolved (even if system says no issues)
    - Both are user overrides and display in purple color
    """
    data = request.json or {}
    print(f"[mini/ack DEBUG] Received request data: {data}")
    
    session_id = (data.get("session_id") or "").strip()
    tenant_id = _get_tenant_id(data)
    user_id = _get_user_id(data)
    patient_key = (data.get("patient_key") or "").strip()
    system_response_id_str = data.get("system_response_id")
    note_text = (data.get("note") or "").strip()
    override_proceed = data.get("override_proceed")
    override_tasking = data.get("override_tasking")
    correlation_id = data.get("correlation_id") or session_id
    
    # Resolution plan context (links note to the plan workflow)
    resolution_plan_id_str = data.get("resolution_plan_id")
    plan_step_id_str = data.get("plan_step_id")
    
    # New: attention_status for "Needs Attention" workflow
    attention_status = data.get("attention_status")  # "resolved" | "unresolved" | null
    
    # Per-factor override support (L2 bottleneck level)
    factor_type = data.get("factor_type")  # "eligibility" | "errors" | "coverage" | "attendance" | null
    
    print(f"[mini/ack DEBUG] Parsed: session_id={session_id}, patient_key={patient_key}, attention_status={attention_status}, factor_type={factor_type}")
    
    # Determine if we should signal frontend to open sidecar
    # For now, don't auto-open sidecar - user can open manually if needed
    open_sidecar = False

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
    db = get_db_session()  # Get session once - scoped_session returns same object per thread
    
    if patient_key:
        print(f"[mini/ack DEBUG] Looking up patient_key={patient_key} in tenant_id={tenant_id}")
        # Get patient_context directly from current session to avoid detached instance issues
        patient_context_obj = db.query(PatientContext).filter(
            PatientContext.tenant_id == tenant_id,
            PatientContext.patient_key == patient_key
        ).first()
        print(f"[mini/ack DEBUG] Direct lookup result: patient_context_obj={patient_context_obj is not None}")
        
        # Also get via agent for other uses (but this will be expired, so use patient_context_obj for updates)
        if patient_context_obj:
            patient_context = patient_context_obj  # Use the same object
            print(f"[mini/ack DEBUG] Found patient via direct lookup: patient_context_id={patient_context_obj.patient_context_id}")
        else:
            # Fallback: try via agent (for MRN resolution)
            print(f"[mini/ack DEBUG] Trying fallback via patient agent...")
            patient_context = _patient_agent.get_patient_context(tenant_id, patient_key)
            if patient_context:
                print(f"[mini/ack DEBUG] Found via agent, re-querying...")
                # Re-query in current session
                patient_context_obj = db.query(PatientContext).filter(
                    PatientContext.patient_context_id == patient_context.patient_context_id
                ).first()
            else:
                print(f"[mini/ack DEBUG] Patient NOT FOUND via agent either!")

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
    print(f"[mini/ack DEBUG] Checking attention_status update: attention_status={attention_status}, factor_type={factor_type}, patient_context_obj={patient_context_obj is not None}")
    if attention_status and patient_context_obj:
        print(f"[mini/ack DEBUG] Updating attention_status to '{attention_status}' for patient_context_id={patient_context_obj.patient_context_id}")
        try:
            # Per-factor override (L2 level) - store in factor_overrides JSONB
            if factor_type:
                # Update factor_overrides for specific factor
                factor_overrides = dict(patient_context_obj.factor_overrides or {})
                # Store both resolved AND unresolved as user overrides
                # "resolved" = user says this is fine (even if system says it's not)
                # "unresolved" = user says this needs work (even if system says it's fine)
                factor_overrides[factor_type] = attention_status
                patient_context_obj.factor_overrides = factor_overrides
                print(f"[mini/ack] Updated factor_overrides[{factor_type}] to '{attention_status}' for patient {patient_key}")
                print(f"[mini/ack] Full factor_overrides: {factor_overrides}")
                
                # Cascade to resolution plan for this factor
                cascade_bottleneck_override(
                    db=db,
                    patient_context_id=patient_context.patient_context_id,
                    bottleneck_factor=factor_type,
                    status=attention_status,
                    user_id=user_id,
                    submitted_at=submitted_at,
                    source_layer="layer2"
                )
            else:
                # Legacy patient-level override (from Mini without factor_type)
                # Use the same session - object is already attached
                patient_context_obj.attention_status = attention_status
                patient_context_obj.attention_status_at = submitted_at
                patient_context_obj.attention_status_by_id = user_id
                
                # Map attention_status to color and store override_color
                # resolved -> purple (user override), unresolved -> purple (user override)
                # Both resolved and unresolved are user overrides, so both get purple color
                if attention_status == "resolved":
                    patient_context_obj.override_color = "purple"
                elif attention_status == "unresolved":
                    patient_context_obj.override_color = "purple"  # User override - show purple
                else:
                    # Clear override if status is cleared
                    patient_context_obj.override_color = None
                
                # If resolved, set resolved_until date (time-bound suppression period)
                if attention_status == "resolved":
                    # Get target_date from latest payment_probability (visit/appointment date)
                    target_date = None
                    if patient_context:
                        payment_probability = _get_payment_probability(patient_context.patient_context_id)
                        if payment_probability and payment_probability.get("target_date"):
                            try:
                                # target_date is ISO format string from _get_payment_probability
                                target_date_str = payment_probability["target_date"]
                                # Parse ISO date string (e.g., "2026-02-15" or "2026-02-15T00:00:00")
                                if "T" in target_date_str:
                                    target_date = datetime.fromisoformat(target_date_str.replace("Z", "+00:00")).date()
                                else:
                                    target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                            except (ValueError, AttributeError, TypeError) as e:
                                print(f"[mini/ack] Error parsing target_date: {e}")
                                pass
                    
                    # Calculate resolved_until: target_date + 30 days, or now() + 30 days if no target_date
                    if target_date:
                        resolved_until = datetime.combine(target_date, datetime.max.time()) + timedelta(days=30)
                    else:
                        resolved_until = submitted_at + timedelta(days=30)
                    
                    patient_context_obj.resolved_until = resolved_until
                    print(f"[mini/ack] Set resolved_until to {resolved_until} for patient {patient_key}")
                else:
                    # If not resolved, clear resolved_until
                    patient_context_obj.resolved_until = None
                
                # Cascade update: Propagate user override to resolution_plan (Layer 2)
                if patient_context and attention_status in ("resolved", "unresolved"):
                    # Get latest payment_probability to identify bottleneck factor
                    latest_prob = db.query(PaymentProbability).filter(
                        PaymentProbability.patient_context_id == patient_context.patient_context_id
                    ).order_by(PaymentProbability.computed_at.desc()).first()
                    
                    if latest_prob and latest_prob.lowest_factor:
                        cascade_bottleneck_override(
                            db=db,
                            patient_context_id=patient_context.patient_context_id,
                            bottleneck_factor=latest_prob.lowest_factor,
                            status=attention_status,
                            user_id=user_id,
                            submitted_at=submitted_at,
                            source_layer="layer1"
                        )
                
                print(f"[mini/ack] Updated patient-level attention_status to '{attention_status}' for patient {patient_key}")
                print(f"[mini/ack] Verified: attention_status={patient_context_obj.attention_status}, resolved_until={patient_context_obj.resolved_until}, override_color={patient_context_obj.override_color}")
            
            db.commit()
            # Verify the update was saved
            db.refresh(patient_context_obj)
        except Exception as e:
            print(f"[mini/ack] Error updating attention_status: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()

    # Persist submission to PostgreSQL (if we have note_text)
    # Note: system_response_id is optional for simple note submissions
    if patient_context and note_text:
        try:
            # Parse plan context UUIDs
            resolution_plan_id = None
            plan_step_id = None
            if resolution_plan_id_str:
                try:
                    resolution_plan_id = uuid.UUID(resolution_plan_id_str)
                except ValueError:
                    pass
            if plan_step_id_str:
                try:
                    plan_step_id = uuid.UUID(plan_step_id_str)
                except ValueError:
                    pass
            
            submission = _patient_state_service.create_submission(
                tenant_id=tenant_id,
                patient_context_id=patient_context.patient_context_id,
                user_id=user_id,
                note_text=note_text,
                system_response_id=system_response_id,  # Optional
                override_proceed=override_proceed or attention_status,  # Map attention_status to override_proceed
                override_tasking=override_tasking,
                resolution_plan_id=resolution_plan_id,
                plan_step_id=plan_step_id,
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
                attention_status=attention_status,
            )
        except Exception as e:
            print(f"[mini/ack] Error persisting submission: {e}")
            return jsonify({"error": f"Failed to save submission: {str(e)}"}), 500
    
    # Even without note_text, if attention_status changed, log and update Firestore
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
            
            # Update Firestore projection with attention_status
            _projection_service.update_attention_status(
                tenant_id=tenant_id,
                patient_key=patient_key,
                attention_status=attention_status,
                updated_by=user_id,
                updated_at=submitted_at,
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
