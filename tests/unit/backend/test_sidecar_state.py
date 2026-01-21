"""
Unit tests for Sidecar State Service.

Tests the core logic for:
- Care readiness computation
- Bottleneck extraction
- Milestone management
- Alert handling
"""

import pytest
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))

from app.services.sidecar_state import (
    compute_care_readiness,
    _map_probability_to_status,
    get_bottlenecks,
    get_milestones,
    get_user_alerts,
    get_unread_alert_count,
    build_sidecar_state,
)


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
        
        step2 = MagicMock()
        step2.step_id = uuid.uuid4()
        step2.question_text = "Is coverage active?"
        step2.description = None
        step2.factor_type = "eligibility"
        step2.answer_options = []
        step2.can_system_answer = False
        step2.system_suggestion = None
        
        # Mock query
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [step1, step2]
        
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
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
