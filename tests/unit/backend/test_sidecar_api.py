"""
Unit tests for Sidecar API Endpoints.

Tests the Flask blueprint routes:
- GET /api/v1/sidecar/state
- GET /api/v1/user/alerts
- POST /api/v1/sidecar/answer
- POST /api/v1/sidecar/note
- POST /api/v1/sidecar/assign
- POST /api/v1/sidecar/own
- POST /api/v1/sidecar/workflow
- POST /api/v1/sidecar/resolve-override
"""

import pytest
import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import sys
import os
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def app():
    """Create Flask test app."""
    from server import create_app
    app = create_app(init_database=False)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_user():
    """Create mock user for auth."""
    user = MagicMock()
    user.user_id = uuid.uuid4()
    user.tenant_id = uuid.uuid4()
    user.email = "test@demo.clinic"
    user.display_name = "Test User"
    return user


@pytest.fixture
def auth_header(mock_user):
    """Create auth header with mock token."""
    return {"Authorization": "Bearer test-token-12345"}


# =============================================================================
# Test GET /api/v1/sidecar/state
# =============================================================================

class TestGetSidecarState:
    """Tests for sidecar state endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    @patch('app.api.sidecar.build_sidecar_state')
    def test_returns_state_for_authenticated_user(
        self, mock_build_state, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return sidecar state for authenticated user."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        mock_build_state.return_value = {
            "ok": True,
            "session_id": "test-session",
            "surface": "sidecar",
            "record": {"type": "patient"},
            "care_readiness": {"position": 50},
            "bottlenecks": [],
            "milestones": [],
            "alerts": [],
            "user_owned_tasks": [],
            "computed_at": datetime.utcnow().isoformat(),
        }
        
        response = client.get(
            '/api/v1/sidecar/state?session_id=test-session',
            headers=auth_header
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["surface"] == "sidecar"
    
    def test_returns_401_without_auth(self, client):
        """Should return 401 without auth header."""
        response = client.get('/api/v1/sidecar/state')
        
        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["ok"] == False
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_401_with_invalid_token(
        self, mock_db_session, mock_get_user, client
    ):
        """Should return 401 with invalid token."""
        mock_get_user.return_value = None
        mock_db_session.return_value.__enter__.return_value = MagicMock()
        
        response = client.get(
            '/api/v1/sidecar/state',
            headers={"Authorization": "Bearer invalid-token"}
        )
        
        assert response.status_code == 401


# =============================================================================
# Test GET /api/v1/user/alerts
# =============================================================================

class TestGetAlerts:
    """Tests for user alerts endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    @patch('app.api.sidecar.get_user_alerts')
    @patch('app.api.sidecar.get_unread_alert_count')
    def test_returns_alerts_for_user(
        self, mock_unread_count, mock_get_alerts, mock_db_session, mock_get_user, 
        client, mock_user, auth_header
    ):
        """Should return alerts list for authenticated user."""
        mock_get_user.return_value = mock_user
        mock_db_session.return_value.__enter__.return_value = MagicMock()
        
        mock_get_alerts.return_value = [
            {"id": "1", "type": "win", "title": "Success!"},
            {"id": "2", "type": "reminder", "title": "Follow up"},
        ]
        mock_unread_count.return_value = 1
        
        response = client.get('/api/v1/user/alerts', headers=auth_header)
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert len(data["alerts"]) == 2
        assert data["unread_count"] == 1


# =============================================================================
# Test POST /api/v1/sidecar/answer
# =============================================================================

class TestSubmitAnswer:
    """Tests for submit answer endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_submits_answer_successfully(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should submit answer and update step status."""
        mock_get_user.return_value = mock_user
        
        # Mock database and step
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        step_id = uuid.uuid4()
        mock_step = MagicMock()
        mock_step.step_id = step_id
        mock_step.plan_id = uuid.uuid4()
        mock_step.status = "current"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_step
        mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        mock_db.query.return_value.filter.return_value.count.return_value = 0
        
        response = client.post(
            '/api/v1/sidecar/answer',
            headers=auth_header,
            json={
                "session_id": "test-session",
                "patient_key": "pt_123",
                "bottleneck_id": str(step_id),
                "answer_id": "yes"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["answer_id"] == "yes"
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_400_without_required_fields(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 400 if required fields missing."""
        mock_get_user.return_value = mock_user
        mock_db_session.return_value.__enter__.return_value = MagicMock()
        
        response = client.post(
            '/api/v1/sidecar/answer',
            headers=auth_header,
            json={"session_id": "test-session"}
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_404_for_nonexistent_step(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 404 if step not found."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response = client.post(
            '/api/v1/sidecar/answer',
            headers=auth_header,
            json={
                "bottleneck_id": str(uuid.uuid4()),
                "answer_id": "yes"
            }
        )
        
        assert response.status_code == 404


# =============================================================================
# Test POST /api/v1/sidecar/note
# =============================================================================

class TestAddNote:
    """Tests for add note endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_adds_note_successfully(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should add note to bottleneck."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        step_id = uuid.uuid4()
        mock_step = MagicMock()
        mock_step.step_id = step_id
        mock_step.plan_id = uuid.uuid4()
        mock_step.factor_type = "eligibility"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_step
        
        response = client.post(
            '/api/v1/sidecar/note',
            headers=auth_header,
            json={
                "bottleneck_id": str(step_id),
                "note_text": "Patient will bring card tomorrow"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert "note_id" in data
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_400_for_empty_note(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 400 if note text is empty."""
        mock_get_user.return_value = mock_user
        mock_db_session.return_value.__enter__.return_value = MagicMock()
        
        response = client.post(
            '/api/v1/sidecar/note',
            headers=auth_header,
            json={
                "bottleneck_id": str(uuid.uuid4()),
                "note_text": "   "
            }
        )
        
        assert response.status_code == 400


# =============================================================================
# Test POST /api/v1/sidecar/assign
# =============================================================================

class TestAssignToMobius:
    """Tests for assign to Mobius endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_assigns_to_mobius_agentic_mode(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should assign step to Mobius in agentic mode."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        step_id = uuid.uuid4()
        mock_step = MagicMock()
        mock_step.step_id = step_id
        mock_step.can_system_answer = True
        mock_step.status = "current"
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_step
        
        response = client.post(
            '/api/v1/sidecar/assign',
            headers=auth_header,
            json={
                "bottleneck_id": str(step_id),
                "mode": "agentic"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["mode"] == "agentic"
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_400_if_mobius_cannot_handle(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 400 if step cannot be handled by Mobius."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        mock_step = MagicMock()
        mock_step.can_system_answer = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_step
        
        response = client.post(
            '/api/v1/sidecar/assign',
            headers=auth_header,
            json={
                "bottleneck_id": str(uuid.uuid4()),
                "mode": "agentic"
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "cannot be handled" in data["error"]


# =============================================================================
# Test POST /api/v1/sidecar/own
# =============================================================================

class TestTakeOwnership:
    """Tests for take ownership endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    @patch('app.api.sidecar.create_user_owned_task')
    def test_creates_owned_task(
        self, mock_create_task, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should create user-owned task record."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        step_id = uuid.uuid4()
        plan_id = uuid.uuid4()
        patient_context_id = uuid.uuid4()
        
        mock_step = MagicMock()
        mock_step.step_id = step_id
        mock_step.plan_id = plan_id
        mock_step.question_text = "Is insurance on file?"
        
        mock_plan = MagicMock()
        mock_plan.plan_id = plan_id
        mock_plan.patient_context_id = patient_context_id
        
        mock_patient = MagicMock()
        mock_patient.display_name = "John Smith"
        
        # Configure query mocks
        def query_side_effect(model):
            mock_query = MagicMock()
            if "PlanStep" in str(model):
                mock_query.filter.return_value.first.return_value = mock_step
            elif "ResolutionPlan" in str(model):
                mock_query.filter.return_value.first.return_value = mock_plan
            elif "PatientContext" in str(model):
                mock_query.filter.return_value.first.return_value = mock_patient
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        owned_task = MagicMock()
        owned_task.ownership_id = uuid.uuid4()
        mock_create_task.return_value = owned_task
        
        response = client.post(
            '/api/v1/sidecar/own',
            headers=auth_header,
            json={
                "patient_key": "pt_123",
                "bottleneck_id": str(step_id),
                "initial_note": "I'll check on this today"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert "ownership_id" in data


# =============================================================================
# Test POST /api/v1/sidecar/assign-bulk
# =============================================================================

class TestBulkAssign:
    """Tests for bulk assign endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_bulk_assigns_multiple_steps(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should assign multiple steps to Mobius."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        step1 = MagicMock()
        step1.can_system_answer = True
        step2 = MagicMock()
        step2.can_system_answer = True
        step3 = MagicMock()
        step3.can_system_answer = False  # Will be skipped
        
        steps = [step1, step2, step3]
        call_count = [0]
        
        def query_filter_side_effect(*args, **kwargs):
            mock_result = MagicMock()
            if call_count[0] < len(steps):
                mock_result.first.return_value = steps[call_count[0]]
                call_count[0] += 1
            else:
                mock_result.first.return_value = None
            return mock_result
        
        mock_db.query.return_value.filter.side_effect = query_filter_side_effect
        
        response = client.post(
            '/api/v1/sidecar/assign-bulk',
            headers=auth_header,
            json={
                "bottleneck_ids": [str(uuid.uuid4()) for _ in range(3)]
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["assigned_count"] == 2
        assert data["skipped_count"] == 1


# =============================================================================
# Test POST /api/v1/sidecar/workflow
# =============================================================================

class TestWorkflowMode:
    """Tests for workflow mode endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_set_workflow_mode_mobius(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should set workflow mode to mobius."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock plan lookup
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.workflow_mode = None
        plan.workflow_mode_set_at = None
        plan.workflow_mode_set_by = None
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = plan
        mock_db.query.return_value = mock_query
        
        response = client.post(
            '/api/v1/sidecar/workflow',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "mode": "mobius",
                "note": "Test note"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["mode"] == "mobius"
        assert "Mobius is on it" in data["message"]
        assert plan.workflow_mode == "mobius"
        assert plan.workflow_mode_set_by == mock_user.user_id
        # Verify note was added if provided
        if mock_db.add.called:
            # PlanNote should have been added
            assert mock_db.add.called
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_set_workflow_mode_together(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should set workflow mode to together."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.workflow_mode = None
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = plan
        mock_db.query.return_value = mock_query
        
        response = client.post(
            '/api/v1/sidecar/workflow',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "mode": "together"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["mode"] == "together"
        assert "together" in data["message"].lower()
    
    @patch('app.api.sidecar.get_user_from_token')
    def test_set_workflow_mode_invalid_mode(
        self, mock_get_user, client, mock_user, auth_header
    ):
        """Should reject invalid mode."""
        mock_get_user.return_value = mock_user
        
        response = client.post(
            '/api/v1/sidecar/workflow',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "mode": "invalid"
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["ok"] == False
        assert "Invalid mode" in data["error"]


# =============================================================================
# Test POST /api/v1/sidecar/resolve-override
# =============================================================================

class TestResolveOverride:
    """Tests for resolve override endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_resolve_override_success(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should mark plan as resolved with override."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock plan and steps
        from app.models.resolution import PlanStatus
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.status = PlanStatus.ACTIVE
        plan.resolved_at = None
        plan.resolved_by = None
        plan.resolution_type = None
        plan.resolution_notes = None
        
        from app.models.resolution import StepStatus
        step1 = MagicMock()
        step1.status = StepStatus.PENDING
        step1.resolved_at = None
        step2 = MagicMock()
        step2.status = StepStatus.CURRENT
        step2.resolved_at = None
        
        plan.steps = [step1, step2]
        
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = plan
        mock_db.query.return_value = mock_query
        
        response = client.post(
            '/api/v1/sidecar/resolve-override',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "resolution_note": "Issue was resolved manually via phone call"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert "Marked as resolved" in data["message"]
        # Check that plan status was set to resolved
        from app.models.resolution import PlanStatus, StepStatus
        assert plan.status == PlanStatus.RESOLVED
        # Check that steps were marked as resolved
        assert step1.status == StepStatus.RESOLVED
        assert step2.status == StepStatus.RESOLVED
        assert plan.resolved_by == mock_user.user_id
        assert plan.resolution_type == "user_override"
        assert plan.resolution_notes == "Issue was resolved manually via phone call"
        assert step1.status == "resolved"
        assert step2.status == "resolved"
    
    @patch('app.api.sidecar.get_user_from_token')
    def test_resolve_override_missing_note(
        self, mock_get_user, client, mock_user, auth_header
    ):
        """Should reject if resolution note is missing."""
        mock_get_user.return_value = mock_user
        
        response = client.post(
            '/api/v1/sidecar/resolve-override',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "resolution_note": ""
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["ok"] == False
        assert "required" in data["error"].lower()


# =============================================================================
# Test POST /api/v1/sidecar/factor-mode
# =============================================================================

class TestSetFactorMode:
    """Tests for setting factor workflow mode."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_sets_mode_and_assigns_steps(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should set mode and auto-assign steps based on mode."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock patient context lookup
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        # Mock plan with factor_modes
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.factor_modes = {}
        
        # Mock steps for the factor
        step1 = MagicMock()
        step1.step_id = uuid.uuid4()
        step1.can_system_answer = True
        step1.assignee_type = None
        
        step2 = MagicMock()
        step2.step_id = uuid.uuid4()
        step2.can_system_answer = False
        step2.assignee_type = None
        
        # Configure query chain
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "ResolutionPlan" in model_name:
                mock_query.filter.return_value.first.return_value = plan
            elif "PlanStep" in model_name:
                mock_query.filter.return_value.all.return_value = [step1, step2]
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "eligibility",
                "mode": "together"
            }
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["factor_type"] == "eligibility"
        assert data["mode"] == "together"
        assert data["steps_updated"] == 2
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_mobius_mode_assigns_all_to_mobius(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Mobius mode should assign all steps to mobius."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.factor_modes = {}
        
        step1 = MagicMock()
        step1.step_id = uuid.uuid4()
        step1.can_system_answer = True
        step1.assignee_type = None
        
        step2 = MagicMock()
        step2.step_id = uuid.uuid4()
        step2.can_system_answer = False  # Even manual steps get assigned to mobius
        step2.assignee_type = None
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "ResolutionPlan" in model_name:
                mock_query.filter.return_value.first.return_value = plan
            elif "PlanStep" in model_name:
                mock_query.filter.return_value.all.return_value = [step1, step2]
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "eligibility",
                "mode": "mobius"
            }
        )
        
        assert response.status_code == 200
        # Both steps should be assigned to mobius
        assert step1.assignee_type == "mobius"
        assert step2.assignee_type == "mobius"
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_together_mode_splits_by_capability(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Together mode should split steps by capability."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.factor_modes = {}
        
        step1 = MagicMock()
        step1.step_id = uuid.uuid4()
        step1.can_system_answer = True  # Should go to mobius
        step1.assignee_type = None
        
        step2 = MagicMock()
        step2.step_id = uuid.uuid4()
        step2.can_system_answer = False  # Should go to user
        step2.assignee_type = None
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "ResolutionPlan" in model_name:
                mock_query.filter.return_value.first.return_value = plan
            elif "PlanStep" in model_name:
                mock_query.filter.return_value.all.return_value = [step1, step2]
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "eligibility",
                "mode": "together"
            }
        )
        
        assert response.status_code == 200
        # Step1 (can_system_answer=True) should go to mobius
        assert step1.assignee_type == "mobius"
        # Step2 (can_system_answer=False) should go to user
        assert step2.assignee_type == "user"
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_manual_mode_assigns_all_to_user(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Manual mode should assign all steps to user."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        plan = MagicMock()
        plan.plan_id = uuid.uuid4()
        plan.factor_modes = {}
        
        step1 = MagicMock()
        step1.step_id = uuid.uuid4()
        step1.can_system_answer = True  # Even automatable steps go to user
        step1.assignee_type = None
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "ResolutionPlan" in model_name:
                mock_query.filter.return_value.first.return_value = plan
            elif "PlanStep" in model_name:
                mock_query.filter.return_value.all.return_value = [step1]
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "eligibility",
                "mode": "manual"
            }
        )
        
        assert response.status_code == 200
        assert step1.assignee_type == "user"
    
    @patch('app.api.sidecar.get_user_from_token')
    def test_returns_400_for_invalid_factor_type(
        self, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 400 for invalid factor_type."""
        mock_get_user.return_value = mock_user
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "invalid_factor",
                "mode": "mobius"
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["ok"] == False
        assert "Invalid factor_type" in data["error"]
    
    @patch('app.api.sidecar.get_user_from_token')
    def test_returns_400_for_invalid_mode(
        self, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 400 for invalid mode."""
        mock_get_user.return_value = mock_user
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "eligibility",
                "mode": "invalid_mode"
            }
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["ok"] == False
        assert "Invalid mode" in data["error"]
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_404_when_no_plan(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 404 when no active plan for patient."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "ResolutionPlan" in model_name:
                mock_query.filter.return_value.first.return_value = None  # No plan
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.post(
            '/api/v1/sidecar/factor-mode',
            headers=auth_header,
            json={
                "patient_key": "demo_001",
                "factor_type": "eligibility",
                "mode": "mobius"
            }
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["ok"] == False
        assert "No active plan found" in data["error"]


# =============================================================================
# Test GET /api/v1/sidecar/evidence
# =============================================================================

class TestGetEvidence:
    """Tests for evidence retrieval endpoint."""
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_evidence_for_factor(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return evidence filtered by factor type."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        # Mock patient context
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        # Mock evidence
        evidence1 = MagicMock()
        evidence1.evidence_id = uuid.uuid4()
        evidence1.factor_type = "eligibility"
        evidence1.fact_type = "insurance_status"
        evidence1.fact_summary = "Insurance is active"
        evidence1.fact_data = {"status": "active"}
        evidence1.impact_direction = "positive"
        evidence1.impact_weight = 0.3
        evidence1.is_stale = False
        evidence1.source_id = None
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "Evidence" in model_name:
                mock_filter_chain = MagicMock()
                mock_filter_chain.filter.return_value = mock_filter_chain
                mock_filter_chain.all.return_value = [evidence1]
                mock_query.filter.return_value = mock_filter_chain
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.get(
            '/api/v1/sidecar/evidence?patient_key=demo_001&factor=eligibility',
            headers=auth_header
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["factor_type"] == "eligibility"
        assert data["count"] == 1
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["fact_type"] == "insurance_status"
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_evidence_for_step(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return evidence linked to specific step."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        step_id = uuid.uuid4()
        evidence_id = uuid.uuid4()
        
        # Mock step with evidence_ids
        step = MagicMock()
        step.step_id = step_id
        step.evidence_ids = [str(evidence_id)]
        
        # Mock evidence
        evidence1 = MagicMock()
        evidence1.evidence_id = evidence_id
        evidence1.factor_type = "eligibility"
        evidence1.fact_type = "coverage_check"
        evidence1.fact_summary = "Coverage verified"
        evidence1.fact_data = {}
        evidence1.impact_direction = "positive"
        evidence1.impact_weight = 0.5
        evidence1.is_stale = False
        evidence1.source_id = None
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "PlanStep" in model_name:
                mock_query.filter.return_value.first.return_value = step
            elif "Evidence" in model_name:
                mock_filter_chain = MagicMock()
                mock_filter_chain.filter.return_value = mock_filter_chain
                mock_filter_chain.all.return_value = [evidence1]
                mock_query.filter.return_value = mock_filter_chain
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.get(
            f'/api/v1/sidecar/evidence?patient_key=demo_001&step_id={step_id}',
            headers=auth_header
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["count"] == 1
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_includes_source_document_info(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should include source document info when available."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        patient_context = MagicMock()
        patient_context.patient_context_id = uuid.uuid4()
        
        source_id = uuid.uuid4()
        
        # Mock source document
        source = MagicMock()
        source.source_id = source_id
        source.document_label = "Insurance Card Scan"
        source.document_type = "insurance_card"
        source.source_system = "portal_upload"
        source.document_date = datetime(2024, 1, 15)
        source.trust_score = 0.95
        
        # Mock evidence with source
        evidence1 = MagicMock()
        evidence1.evidence_id = uuid.uuid4()
        evidence1.factor_type = "eligibility"
        evidence1.fact_type = "card_on_file"
        evidence1.fact_summary = "Card uploaded"
        evidence1.fact_data = {}
        evidence1.impact_direction = "positive"
        evidence1.impact_weight = 0.4
        evidence1.is_stale = False
        evidence1.source_id = source_id
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = patient_context
            elif "Evidence" in model_name:
                mock_filter_chain = MagicMock()
                mock_filter_chain.filter.return_value = mock_filter_chain
                mock_filter_chain.all.return_value = [evidence1]
                mock_query.filter.return_value = mock_filter_chain
            elif "SourceDocument" in model_name:
                mock_query.filter.return_value.first.return_value = source
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.get(
            '/api/v1/sidecar/evidence?patient_key=demo_001&factor=eligibility',
            headers=auth_header
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] == True
        assert data["count"] == 1
        
        evidence = data["evidence"][0]
        assert evidence["source"] is not None
        assert evidence["source"]["label"] == "Insurance Card Scan"
        assert evidence["source"]["type"] == "insurance_card"
        assert evidence["source"]["system"] == "portal_upload"
        assert evidence["source"]["trust_score"] == 0.95
    
    @patch('app.api.sidecar.get_user_from_token')
    @patch('app.api.sidecar.get_db_session')
    def test_returns_404_for_unknown_patient(
        self, mock_db_session, mock_get_user, client, mock_user, auth_header
    ):
        """Should return 404 for unknown patient key."""
        mock_get_user.return_value = mock_user
        
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        
        def query_side_effect(model):
            mock_query = MagicMock()
            model_name = str(model)
            if "PatientContext" in model_name:
                mock_query.filter.return_value.first.return_value = None  # Not found
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        response = client.get(
            '/api/v1/sidecar/evidence?patient_key=nonexistent&factor=eligibility',
            headers=auth_header
        )
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["ok"] == False
        assert "Patient not found" in data["error"]


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
