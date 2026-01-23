"""
Unit tests for Sidecar State Service.

Tests the core logic for:
- Care readiness computation
- Bottleneck extraction
- Milestone management
- Alert handling
"""

import sys
import os

# Add backend to path BEFORE any app imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import pytest
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch

from app.services.sidecar_state import (
    compute_care_readiness,
    _map_probability_to_status,
    _compute_factor_status,
    _compute_mode_recommendation,
    build_factors_array,
    determine_focus,
    get_bottlenecks,
    get_milestones,
    get_user_alerts,
    get_unread_alert_count,
    build_sidecar_state,
)
from app.models.resolution import StepStatus, PlanStatus


# =============================================================================
# Test _map_probability_to_status
# =============================================================================

class TestMapProbabilityToStatus:
    """Tests for probability to status mapping."""
    
    def test_high_probability_returns_complete(self):
        """Probability >= 0.85 should return 'complete'."""
        assert _map_probability_to_status(0.85) == "complete"
        assert _map_probability_to_status(0.95) == "complete"
        assert _map_probability_to_status(1.0) == "complete"
    
    def test_medium_probability_returns_in_progress(self):
        """Probability 0.5-0.84 should return 'in_progress'."""
        assert _map_probability_to_status(0.5) == "in_progress"
        assert _map_probability_to_status(0.7) == "in_progress"
        assert _map_probability_to_status(0.84) == "in_progress"
    
    def test_low_probability_returns_blocked(self):
        """Probability < 0.5 should return 'blocked'."""
        assert _map_probability_to_status(0.0) == "blocked"
        assert _map_probability_to_status(0.3) == "blocked"
        assert _map_probability_to_status(0.49) == "blocked"
    
    def test_none_returns_pending(self):
        """None probability should return 'pending'."""
        assert _map_probability_to_status(None) == "pending"


# =============================================================================
# Test compute_care_readiness
# =============================================================================

class TestComputeCareReadiness:
    """Tests for care readiness computation."""
    
    def test_no_probability_returns_defaults(self):
        """When no probability data, should return default values."""
        result = compute_care_readiness(None)
        
        assert result["position"] == 50
        assert result["direction"] == "stable"
        assert "factors" in result
        assert result["factors"]["visit_confirmed"]["status"] == "pending"
        assert result["factors"]["eligibility_verified"]["status"] == "pending"
        assert result["factors"]["authorization_secured"]["status"] == "pending"
        assert result["factors"]["documentation_ready"]["status"] == "pending"
    
    def test_high_probability_returns_complete_factors(self):
        """High probability values should map to complete factors."""
        prob = MagicMock()
        prob.overall_probability = 0.92
        prob.prob_appointment_attendance = 0.95
        prob.prob_eligibility = 0.90
        prob.prob_coverage = 0.88
        prob.prob_no_errors = 0.92
        
        result = compute_care_readiness(prob)
        
        assert result["position"] == 92
        assert result["factors"]["visit_confirmed"]["status"] == "complete"
        assert result["factors"]["eligibility_verified"]["status"] == "complete"
        assert result["factors"]["authorization_secured"]["status"] == "complete"
        assert result["factors"]["documentation_ready"]["status"] == "complete"
    
    def test_low_probability_returns_blocked_factors(self):
        """Low probability values should map to blocked factors."""
        prob = MagicMock()
        prob.overall_probability = 0.35
        prob.prob_appointment_attendance = 0.30
        prob.prob_eligibility = 0.25
        prob.prob_coverage = 0.40
        prob.prob_no_errors = 0.45
        
        result = compute_care_readiness(prob)
        
        assert result["position"] == 35
        assert result["factors"]["visit_confirmed"]["status"] == "blocked"
        assert result["factors"]["eligibility_verified"]["status"] == "blocked"
        assert result["factors"]["authorization_secured"]["status"] == "blocked"
        assert result["factors"]["documentation_ready"]["status"] == "blocked"
    
    def test_mixed_probability_returns_mixed_factors(self):
        """Mixed probability values should return appropriate statuses."""
        prob = MagicMock()
        prob.overall_probability = 0.65
        prob.prob_appointment_attendance = 0.90  # complete
        prob.prob_eligibility = 0.60             # in_progress
        prob.prob_coverage = 0.40                # blocked
        prob.prob_no_errors = 0.85               # complete
        
        result = compute_care_readiness(prob)
        
        assert result["position"] == 65
        assert result["factors"]["visit_confirmed"]["status"] == "complete"
        assert result["factors"]["eligibility_verified"]["status"] == "in_progress"
        assert result["factors"]["authorization_secured"]["status"] == "blocked"
        assert result["factors"]["documentation_ready"]["status"] == "complete"


# =============================================================================
# Test get_bottlenecks
# =============================================================================

class TestGetBottlenecks:
    """Tests for bottleneck extraction."""
    
    def test_no_plan_returns_empty(self):
        """When no plan, should return empty list."""
        db = MagicMock()
        result = get_bottlenecks(db, None, "John")
        assert result == []
    
    def test_returns_current_and_pending_steps(self):
        """Should return current and pending steps as bottlenecks."""
        from app.models.resolution import StepStatus
        
        db = MagicMock()
        
        # Mock plan
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        
        # Mock steps
        step1 = MagicMock()
        step1.step_id = uuid.uuid4()
        step1.question_text = "Is insurance on file?"
        step1.description = "Check for insurance card"
        step1.factor_type = "eligibility"
        step1.answer_options = [
            {"code": "yes", "label": "Yes"},
            {"code": "no", "label": "No"},
        ]
        step1.can_system_answer = True
        step1.system_suggestion = {"source": "Auto-detected from EMR"}
        step1.status = StepStatus.CURRENT
        step1.step_order = 1
        step1.milestone_id = None
        step1.selected_answer = None
        step1.sources = {}
        step1.answers = []  # Empty list for no previous answers
        step1.template_id = None  # No linked template
        
        step2 = MagicMock()
        step2.step_id = uuid.uuid4()
        step2.question_text = "Is coverage active?"
        step2.description = None
        step2.factor_type = "eligibility"
        step2.answer_options = []
        step2.can_system_answer = False
        step2.system_suggestion = None
        step2.status = StepStatus.PENDING
        step2.step_order = 2
        step2.milestone_id = None
        step2.selected_answer = None
        step2.sources = {}
        step2.answers = []  # Empty list for no previous answers
        step2.template_id = None  # No linked template
        
        # Mock query chain: db.query(PlanStep).filter(...).order_by(...).all()
        # The filter is called twice (once for plan_id, once for status.in_)
        mock_order_by = MagicMock()
        mock_order_by.all.return_value = [step1, step2]
        
        mock_filter = MagicMock()
        mock_filter.order_by.return_value = mock_order_by
        
        # filter() can be chained, so it returns itself
        mock_filter.filter.return_value = mock_filter
        
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_filter
        db.query.return_value = mock_query
        
        result = get_bottlenecks(db, plan, "John")
        
        assert len(result) == 2
        
        # Check first bottleneck
        assert result[0]["question_text"] == "Is insurance on file?"
        assert result[0]["mobius_can_handle"] == True
        assert len(result[0]["answer_options"]) == 2
        
        # Check second bottleneck
        assert result[1]["question_text"] == "Is coverage active?"
        assert result[1]["mobius_can_handle"] == False


# =============================================================================
# Test Alert Functions
# =============================================================================

class TestAlertFunctions:
    """Tests for alert retrieval functions."""
    
    def test_get_user_alerts_returns_list(self):
        """Should return list of alert dicts."""
        db = MagicMock()
        user_id = uuid.uuid4()
        
        # Mock alert
        alert = MagicMock()
        alert.to_dict.return_value = {
            "id": str(uuid.uuid4()),
            "type": "win",
            "title": "Success!",
        }
        
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [alert]
        
        result = get_user_alerts(db, user_id, limit=10)
        
        assert len(result) == 1
        assert result[0]["type"] == "win"
    
    def test_get_unread_alert_count(self):
        """Should return count of unread alerts."""
        db = MagicMock()
        user_id = uuid.uuid4()
        
        db.query.return_value.filter.return_value.count.return_value = 5
        
        result = get_unread_alert_count(db, user_id)
        
        assert result == 5


# =============================================================================
# Test build_sidecar_state
# =============================================================================

class TestBuildSidecarState:
    """Tests for full sidecar state builder."""
    
    def test_builds_complete_response_without_patient(self):
        """Should build valid response even without patient context."""
        db = MagicMock()
        user_id = uuid.uuid4()
        
        # Mock alert query
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        
        result = build_sidecar_state(
            db=db,
            user_id=user_id,
            patient_context=None,
            session_id="test-session"
        )
        
        assert result["ok"] == True
        assert result["session_id"] == "test-session"
        assert result["surface"] == "sidecar"
        assert result["record"]["type"] == "patient"
        assert result["care_readiness"]["position"] == 50
        assert result["bottlenecks"] == []
        assert result["milestones"] == []
    
    def test_builds_complete_response_with_patient(self):
        """Should build full response with patient context."""
        db = MagicMock()
        user_id = uuid.uuid4()
        
        # Mock patient context
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        patient_context.display_name = "John Smith"
        patient_context.tenant_id = uuid.uuid4()
        
        # Mock snapshot (needed for patient_name extraction)
        snapshot = MagicMock()
        snapshot.snapshot_version = 1
        snapshot.display_name = "John Smith"
        patient_context.snapshots = [snapshot]
        
        # Mock various queries
        db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
        db.query.return_value.filter.return_value.all.return_value = []
        
        result = build_sidecar_state(
            db=db,
            user_id=user_id,
            patient_context=patient_context,
            session_id="test-session"
        )
        
        assert result["ok"] == True
        assert result["record"]["displayName"] == "John Smith"
        assert result["record"]["shortName"] == "John"
        assert result["record"]["possessive"] == "John's"
        assert "computed_at" in result


# =============================================================================
# Test Model to_dict Methods
# =============================================================================

class TestModelToDictMethods:
    """Tests for model serialization."""
    
    def test_user_alert_to_dict(self):
        """UserAlert.to_dict should return expected structure."""
        from app.models.sidecar import UserAlert
        
        alert = UserAlert(
            alert_id=uuid.uuid4(),
            alert_type="win",
            priority="high",
            title="Test Alert",
            subtitle="Test subtitle",
            patient_key="pt_123",
            patient_name="John",
            action_type="open_sidecar",
            action_url=None,
            read=False,
            created_at=datetime.utcnow(),
        )
        
        result = alert.to_dict()
        
        assert "id" in result
        assert result["type"] == "win"
        assert result["priority"] == "high"
        assert result["title"] == "Test Alert"
        assert result["patient_key"] == "pt_123"
        assert result["read"] == False
    
    def test_milestone_to_dict(self):
        """Milestone.to_dict should return expected structure."""
        from app.models.sidecar import Milestone
        
        milestone = Milestone(
            milestone_id=uuid.uuid4(),
            milestone_type="eligibility",
            label="John's insurance verified",
            status="complete",
        )
        milestone.substeps = []
        milestone.history = []
        
        result = milestone.to_dict()
        
        assert "id" in result
        assert result["type"] == "eligibility"
        assert result["label"] == "John's insurance verified"
        assert result["status"] == "complete"
        assert result["substeps"] == []
        assert result["history"] == []
    
    def test_user_owned_task_to_dict(self):
        """UserOwnedTask.to_dict should return expected structure."""
        from app.models.sidecar import UserOwnedTask
        
        step_id = uuid.uuid4()
        task = UserOwnedTask(
            ownership_id=uuid.uuid4(),
            plan_step_id=step_id,
            question_text="Is insurance on file?",
            patient_key="pt_123",
            patient_name="John",
            status="active",
            assigned_at=datetime.utcnow(),
        )
        
        result = task.to_dict()
        
        assert "id" in result
        assert result["bottleneck_id"] == str(step_id)
        assert result["question_text"] == "Is insurance on file?"
        assert result["status"] == "active"


# =============================================================================
# Test _compute_factor_status (NEW)
# =============================================================================

class TestComputeFactorStatus:
    """Tests for factor status computation based on probability and steps."""
    
    def test_resolved_when_high_prob_no_unresolved_steps(self):
        """High probability (>=0.85) with no unresolved steps should return 'resolved'."""
        assert _compute_factor_status(0.90, False) == "resolved"
        assert _compute_factor_status(0.85, False) == "resolved"
        assert _compute_factor_status(1.0, False) == "resolved"
    
    def test_blocked_when_has_unresolved_steps(self):
        """Should return 'blocked' when there are unresolved steps, regardless of probability."""
        assert _compute_factor_status(0.90, True) == "blocked"
        assert _compute_factor_status(0.95, True) == "blocked"
        assert _compute_factor_status(1.0, True) == "blocked"
    
    def test_blocked_when_low_probability(self):
        """Should return 'blocked' when probability is below threshold."""
        assert _compute_factor_status(0.40, False) == "blocked"
        assert _compute_factor_status(0.50, False) == "blocked"
        assert _compute_factor_status(0.84, False) == "blocked"
        assert _compute_factor_status(0.0, False) == "blocked"
    
    def test_waiting_when_none_probability(self):
        """Should return 'waiting' when probability is None."""
        assert _compute_factor_status(None, False) == "waiting"
        assert _compute_factor_status(None, True) == "blocked"  # Has unresolved steps takes priority


# =============================================================================
# Test _compute_mode_recommendation (NEW)
# =============================================================================

class TestComputeModeRecommendation:
    """Tests for workflow mode recommendation computation."""
    
    def test_recommends_mobius_when_all_automatable(self):
        """Should recommend 'mobius' when all steps can be automated."""
        # Create mock steps where all have can_system_answer=True
        step1 = MagicMock()
        step1.can_system_answer = True
        step2 = MagicMock()
        step2.can_system_answer = True
        step3 = MagicMock()
        step3.can_system_answer = True
        
        steps = [step1, step2, step3]
        result = _compute_mode_recommendation(steps)
        
        assert result["mode"] == "mobius"
        assert result["confidence"] == 0.95
        assert "All steps can be automated" in result["reason"]
    
    def test_recommends_together_when_some_automatable(self):
        """Should recommend 'together' when some steps can be automated."""
        step1 = MagicMock()
        step1.can_system_answer = True
        step2 = MagicMock()
        step2.can_system_answer = False
        step3 = MagicMock()
        step3.can_system_answer = True
        
        steps = [step1, step2, step3]
        result = _compute_mode_recommendation(steps)
        
        assert result["mode"] == "together"
        assert result["confidence"] == 0.8
        assert "2 of 3" in result["reason"]
    
    def test_recommends_manual_when_none_automatable(self):
        """Should recommend 'manual' when no steps can be automated."""
        step1 = MagicMock()
        step1.can_system_answer = False
        step2 = MagicMock()
        step2.can_system_answer = False
        
        steps = [step1, step2]
        result = _compute_mode_recommendation(steps)
        
        assert result["mode"] == "manual"
        assert result["confidence"] == 0.7
        assert "human action" in result["reason"]
    
    def test_returns_default_when_no_steps(self):
        """Should return default recommendation when no steps provided."""
        result = _compute_mode_recommendation([])
        
        assert result["mode"] == "mobius"
        assert result["confidence"] == 0.5
        assert "No steps defined" in result["reason"]


# =============================================================================
# Test build_factors_array (NEW)
# =============================================================================

class TestBuildFactorsArray:
    """Tests for building the factors array for UI."""
    
    def test_returns_five_factors_in_order(self):
        """Should return all five factors in correct sequence order."""
        db = MagicMock()
        
        # Mock query that returns no steps
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value = mock_query
        
        factors = build_factors_array(db, None, None, None)
        
        assert len(factors) == 5
        assert factors[0]["factor_type"] == "attendance"
        assert factors[1]["factor_type"] == "eligibility"
        assert factors[2]["factor_type"] == "coverage"
        assert factors[3]["factor_type"] == "clean_claim"
        assert factors[4]["factor_type"] == "errors"
        
        # Check order values
        assert factors[0]["order"] == 1
        assert factors[1]["order"] == 2
        assert factors[2]["order"] == 3
        assert factors[3]["order"] == 4
        assert factors[4]["order"] == 5
    
    def test_factor_status_reflects_probability_and_steps(self):
        """Should compute correct status based on probability and steps."""
        db = MagicMock()
        
        # Mock query that returns no steps
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value = mock_query
        
        # Mock probability with high eligibility but no attendance
        probability = MagicMock()
        probability.prob_appointment_attendance = 0.50  # Low -> blocked
        probability.prob_eligibility = 0.90  # High -> resolved
        probability.prob_coverage = None  # None -> waiting
        probability.prob_no_errors = 0.85  # Threshold -> resolved
        
        factors = build_factors_array(db, None, probability, None)
        
        # attendance has low prob -> blocked
        assert factors[0]["status"] == "blocked"
        # eligibility has high prob -> resolved
        assert factors[1]["status"] == "resolved"
        # coverage has None prob -> waiting
        assert factors[2]["status"] == "waiting"
        # clean_claim and errors both use prob_no_errors (0.85 >= 0.85) -> resolved
        assert factors[3]["status"] == "resolved"
        assert factors[4]["status"] == "resolved"
    
    def test_steps_grouped_by_factor_type(self):
        """Steps should be grouped under correct factor based on factor_type."""
        db = MagicMock()
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.factor_modes = {}
        
        # Create mock steps with different factor types
        step1 = MagicMock()
        step1.step_id = uuid.uuid4()
        step1.factor_type = "eligibility"
        step1.status = StepStatus.PENDING
        step1.can_system_answer = True
        step1.assignee_type = "mobius"
        step1.question_text = "Check insurance"
        step1.rationale = None
        step1.evidence_ids = None
        
        step2 = MagicMock()
        step2.step_id = uuid.uuid4()
        step2.factor_type = "eligibility"
        step2.status = StepStatus.CURRENT
        step2.can_system_answer = False
        step2.assignee_type = "user"
        step2.question_text = "Verify coverage"
        step2.rationale = None
        step2.evidence_ids = None
        
        step3 = MagicMock()
        step3.step_id = uuid.uuid4()
        step3.factor_type = "attendance"
        step3.status = StepStatus.PENDING
        step3.can_system_answer = True
        step3.assignee_type = "mobius"
        step3.question_text = "Confirm visit"
        step3.rationale = None
        step3.evidence_ids = None
        
        # Mock query to return steps
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = [step1, step2, step3]
        db.query.return_value = mock_query
        
        factors = build_factors_array(db, plan, None, None)
        
        # Eligibility should have 2 steps
        eligibility_factor = next(f for f in factors if f["factor_type"] == "eligibility")
        assert len(eligibility_factor["steps"]) == 2
        
        # Attendance should have 1 step
        attendance_factor = next(f for f in factors if f["factor_type"] == "attendance")
        assert len(attendance_factor["steps"]) == 1
        
        # Coverage should have 0 steps
        coverage_factor = next(f for f in factors if f["factor_type"] == "coverage")
        assert len(coverage_factor["steps"]) == 0
    
    def test_mode_from_plan_factor_modes(self):
        """Mode should be populated from plan.factor_modes."""
        db = MagicMock()
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.factor_modes = {
            "eligibility": "mobius",
            "coverage": "together",
            "attendance": "manual"
        }
        
        # Mock query that returns no steps
        mock_query = MagicMock()
        mock_query.filter.return_value.order_by.return_value.all.return_value = []
        db.query.return_value = mock_query
        
        factors = build_factors_array(db, plan, None, None)
        
        eligibility = next(f for f in factors if f["factor_type"] == "eligibility")
        assert eligibility["mode"] == "mobius"
        
        coverage = next(f for f in factors if f["factor_type"] == "coverage")
        assert coverage["mode"] == "together"
        
        attendance = next(f for f in factors if f["factor_type"] == "attendance")
        assert attendance["mode"] == "manual"
        
        # Clean claim and errors have no mode set
        clean_claim = next(f for f in factors if f["factor_type"] == "clean_claim")
        assert clean_claim["mode"] is None


# =============================================================================
# Test determine_focus (NEW)
# =============================================================================

class TestDetermineFocus:
    """Tests for determining which factor should be the user's focus."""
    
    def test_focus_on_first_blocked_matching_user_activities(self):
        """Should focus on first blocked factor that matches user's activities."""
        factors = [
            {"factor_type": "attendance", "status": "resolved", "is_focus": False},
            {"factor_type": "eligibility", "status": "blocked", "is_focus": False},
            {"factor_type": "coverage", "status": "blocked", "is_focus": False},
            {"factor_type": "clean_claim", "status": "waiting", "is_focus": False},
            {"factor_type": "errors", "status": "waiting", "is_focus": False},
        ]
        
        # User has verify_eligibility activity -> should focus on eligibility
        user_activities = ["verify_eligibility", "check_in_patients"]
        
        determine_focus(factors, user_activities)
        
        eligibility = next(f for f in factors if f["factor_type"] == "eligibility")
        assert eligibility["is_focus"] == True
        
        # Other blocked factor should NOT be focus
        coverage = next(f for f in factors if f["factor_type"] == "coverage")
        assert coverage["is_focus"] == False
    
    def test_fallback_to_first_blocked_factor(self):
        """Should fall back to first blocked factor when no activity match."""
        factors = [
            {"factor_type": "attendance", "status": "resolved", "is_focus": False},
            {"factor_type": "eligibility", "status": "resolved", "is_focus": False},
            {"factor_type": "coverage", "status": "blocked", "is_focus": False},
            {"factor_type": "clean_claim", "status": "blocked", "is_focus": False},
            {"factor_type": "errors", "status": "waiting", "is_focus": False},
        ]
        
        # User has no matching activities
        user_activities = ["unrelated_activity"]
        
        determine_focus(factors, user_activities)
        
        # Should pick first blocked factor (coverage)
        coverage = next(f for f in factors if f["factor_type"] == "coverage")
        assert coverage["is_focus"] == True
        
        # Second blocked factor should NOT be focus
        clean_claim = next(f for f in factors if f["factor_type"] == "clean_claim")
        assert clean_claim["is_focus"] == False
    
    def test_no_focus_when_all_resolved(self):
        """Should not set is_focus=True when all factors are resolved."""
        factors = [
            {"factor_type": "attendance", "status": "resolved", "is_focus": False},
            {"factor_type": "eligibility", "status": "resolved", "is_focus": False},
            {"factor_type": "coverage", "status": "resolved", "is_focus": False},
            {"factor_type": "clean_claim", "status": "resolved", "is_focus": False},
            {"factor_type": "errors", "status": "resolved", "is_focus": False},
        ]
        
        determine_focus(factors, ["verify_eligibility"])
        
        # No factor should have is_focus=True
        for factor in factors:
            assert factor["is_focus"] == False
    
    def test_no_focus_when_no_user_activities_and_none_blocked(self):
        """Should not set focus when no activities provided and nothing blocked."""
        factors = [
            {"factor_type": "attendance", "status": "waiting", "is_focus": False},
            {"factor_type": "eligibility", "status": "resolved", "is_focus": False},
            {"factor_type": "coverage", "status": "waiting", "is_focus": False},
            {"factor_type": "clean_claim", "status": "resolved", "is_focus": False},
            {"factor_type": "errors", "status": "waiting", "is_focus": False},
        ]
        
        determine_focus(factors, None)
        
        # No factor should have is_focus=True (none are blocked)
        for factor in factors:
            assert factor["is_focus"] == False


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
