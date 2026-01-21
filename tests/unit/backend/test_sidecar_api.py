"""
Unit tests for Sidecar API Endpoints.

Tests the Flask blueprint routes:
- GET /api/v1/sidecar/state
- GET /api/v1/user/alerts
- POST /api/v1/sidecar/answer
- POST /api/v1/sidecar/note
- POST /api/v1/sidecar/assign
- POST /api/v1/sidecar/own
"""

import pytest
import json
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'backend'))


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
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
