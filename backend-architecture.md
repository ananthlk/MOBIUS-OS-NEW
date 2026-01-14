# Mobius OS - Backend Architecture & API Structure

## Overview

The backend architecture is designed to support the frontend component structure with mode-based routing, component-specific endpoints, and intelligent database selection (Firestore vs PostgreSQL).

## Architecture Principles

1. **Mode-Driven Routing**: Each mode (Eligibility, Front Desk, Backend, Email Drafter, etc.) has its own endpoint namespace
2. **Component-Specific Endpoints**: Each reusable component has corresponding backend endpoints
3. **Database Selection**: 
   - **Firestore**: Real-time data, user sessions, chat messages, live alerts, tasks
   - **PostgreSQL**: Structured data, patient records, claims, authorizations, audit logs, user management

## API Endpoint Structure

### Base Structure

```
/api/v1/
├── /auth/                    # Authentication endpoints
├── /modes/                   # Mode-based endpoints
│   ├── /eligibility/
│   ├── /front-desk/
│   ├── /backend/
│   ├── /email-drafter/
│   └── /[mode-name]/
├── /components/              # Component-specific endpoints (shared across modes)
│   ├── /tasks/
│   ├── /feedback/
│   ├── /guidance/
│   ├── /context/
│   └── /alerts/
├── /users/                   # User management
└── /records/                 # Record ID management (patient, claim, visit, etc.)
```

## Mode-Based Endpoints

Each mode has a dedicated endpoint group that handles mode-specific logic:

### Example: Eligibility Mode

```
POST   /api/v1/modes/eligibility/context          # Get/set context for eligibility mode
GET    /api/v1/modes/eligibility/summary          # Get context summary
POST   /api/v1/modes/eligibility/quick-action     # Execute quick action (e.g., "Check Eligibility")
GET    /api/v1/modes/eligibility/patient/:id      # Get patient eligibility data
POST   /api/v1/modes/eligibility/authorization    # Request authorization
GET    /api/v1/modes/eligibility/claims/:id       # Get claims for patient
```

### Example: Front Desk Mode

```
POST   /api/v1/modes/front-desk/context
GET    /api/v1/modes/front-desk/summary
POST   /api/v1/modes/front-desk/quick-action
GET    /api/v1/modes/front-desk/appointments
POST   /api/v1/modes/front-desk/check-in
```

### Mode Endpoint Pattern

```
/api/v1/modes/{mode-name}/
├── GET    /context              # Get current context
├── POST   /context              # Update context
├── GET    /summary              # Get context summary
├── POST   /quick-action         # Execute quick action
└── [mode-specific endpoints]    # Custom endpoints per mode
```

## Component-Specific Endpoints

These endpoints are shared across all modes but can be mode-aware:

### Tasks & Reminders

```
GET    /api/v1/components/tasks/                    # Get tasks for current context
POST   /api/v1/components/tasks/                   # Create new task
PUT    /api/v1/components/tasks/:id                 # Update task
DELETE /api/v1/components/tasks/:id                 # Delete task
POST   /api/v1/components/tasks/:id/complete        # Mark task complete
GET    /api/v1/components/tasks/shared              # Get shared tasks from backend
GET    /api/v1/components/tasks/backend             # Get backend tasks
```

### Feedback Component

```
POST   /api/v1/components/feedback/                  # Submit feedback
GET    /api/v1/components/feedback/:messageId       # Get feedback for message
POST   /api/v1/components/feedback/rating           # Submit thumbs up/down
POST   /api/v1/components/feedback/questionnaire    # Submit questionnaire
```

### Guidance Actions

```
GET    /api/v1/components/guidance/:contextId        # Get guidance actions for context
POST   /api/v1/components/guidance/execute           # Execute guidance action
GET    /api/v1/components/guidance/dynamic          # Get dynamic buttons/forms
```

### Context & Summary

```
GET    /api/v1/components/context/current            # Get current context
POST   /api/v1/components/context/update            # Update context
GET    /api/v1/components/context/summary           # Get context summary
POST   /api/v1/components/context/quick-action      # Execute quick action
```

### Alerts

```
GET    /api/v1/components/alerts/                    # Get active alerts
POST   /api/v1/components/alerts/                    # Create alert
PUT    /api/v1/components/alerts/:id/acknowledge     # Acknowledge alert
GET    /api/v1/components/alerts/live                # WebSocket/SSE for live alerts
```

### Chat & Messages

```
GET    /api/v1/components/chat/messages              # Get chat history
POST   /api/v1/components/chat/messages             # Send message
GET    /api/v1/components/chat/thinking/:messageId  # Get thinking process for message
POST   /api/v1/components/chat/stream               # Stream chat response (SSE/WebSocket)
```

### Record ID Management

```
GET    /api/v1/records/:type/:id                     # Get record by type and ID
POST   /api/v1/records/                              # Create/update record
GET    /api/v1/records/search                        # Search records
GET    /api/v1/records/types                         # Get available record types
```

## Backend Module Structure

```
backend/
├── app/
│   ├── __init__.py                 # Flask app factory
│   ├── config.py                   # Configuration
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py                 # Authentication routes
│   │   ├── modes/
│   │   │   ├── __init__.py
│   │   │   ├── eligibility.py      # Eligibility mode endpoints
│   │   │   ├── front_desk.py       # Front desk mode endpoints
│   │   │   ├── backend.py          # Backend mode endpoints
│   │   │   ├── email_drafter.py    # Email drafter mode endpoints
│   │   │   └── base.py             # Base mode handler
│   │   ├── components/
│   │   │   ├── __init__.py
│   │   │   ├── tasks.py            # Tasks endpoints
│   │   │   ├── feedback.py         # Feedback endpoints
│   │   │   ├── guidance.py         # Guidance actions endpoints
│   │   │   ├── context.py          # Context endpoints
│   │   │   ├── alerts.py           # Alerts endpoints
│   │   │   └── chat.py             # Chat endpoints
│   │   ├── records.py              # Record ID management
│   │   └── users.py                # User management
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mode_service.py         # Mode switching and management
│   │   ├── context_service.py      # Context management
│   │   ├── task_service.py         # Task management
│   │   ├── feedback_service.py     # Feedback processing
│   │   ├── guidance_service.py     # Dynamic guidance generation
│   │   ├── alert_service.py        # Alert management
│   │   └── chat_service.py         # Chat/LLM integration
│   ├── models/
│   │   ├── __init__.py
│   │   ├── postgres/
│   │   │   ├── __init__.py
│   │   │   ├── user.py             # User model (PostgreSQL)
│   │   │   ├── patient.py          # Patient model (PostgreSQL)
│   │   │   ├── claim.py            # Claim model (PostgreSQL)
│   │   │   ├── authorization.py    # Authorization model (PostgreSQL)
│   │   │   ├── visit.py            # Visit model (PostgreSQL)
│   │   │   └── audit.py            # Audit log (PostgreSQL)
│   │   └── firestore/
│   │       ├── __init__.py
│   │       ├── session.py          # User session (Firestore)
│   │       ├── context.py          # Current context (Firestore)
│   │       ├── task.py             # Task (Firestore)
│   │       ├── message.py          # Chat message (Firestore)
│   │       ├── feedback.py         # Feedback (Firestore)
│   │       └── alert.py            # Alert (Firestore)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── postgres.py             # PostgreSQL connection & session
│   │   ├── firestore.py            # Firestore client
│   │   └── db_selector.py          # Database selection logic
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── oauth.py                # OAuth implementation
│   │   └── jwt.py                  # JWT token management
│   └── utils/
│       ├── __init__.py
│       ├── validators.py
│       └── helpers.py
```

## Database Schema Design

### PostgreSQL Schema (Structured Data)

```sql
-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50),
    client_id UUID REFERENCES clients(id),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Clients
CREATE TABLE clients (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    logo_url VARCHAR(500),
    created_at TIMESTAMP
);

-- Patients
CREATE TABLE patients (
    id UUID PRIMARY KEY,
    mrn VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    date_of_birth DATE,
    client_id UUID REFERENCES clients(id),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Claims
CREATE TABLE claims (
    id UUID PRIMARY KEY,
    claim_number VARCHAR(100) UNIQUE NOT NULL,
    patient_id UUID REFERENCES patients(id),
    status VARCHAR(50),
    amount DECIMAL(10,2),
    submitted_date DATE,
    created_at TIMESTAMP
);

-- Authorizations
CREATE TABLE authorizations (
    id UUID PRIMARY KEY,
    auth_number VARCHAR(100) UNIQUE NOT NULL,
    patient_id UUID REFERENCES patients(id),
    status VARCHAR(50),
    requested_date DATE,
    approved_date DATE,
    created_at TIMESTAMP
);

-- Visits
CREATE TABLE visits (
    id UUID PRIMARY KEY,
    visit_number VARCHAR(100) UNIQUE NOT NULL,
    patient_id UUID REFERENCES patients(id),
    visit_date DATE,
    provider_id UUID,
    created_at TIMESTAMP
);

-- Audit Logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id UUID,
    mode VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP
);
```

### Firestore Collections (Real-time/Document Data)

```
firestore/
├── sessions/
│   └── {sessionId}/
│       ├── userId
│       ├── mode
│       ├── context
│       ├── createdAt
│       └── lastActivity
│
├── contexts/
│   └── {contextId}/
│       ├── mode
│       ├── recordType
│       ├── recordId
│       ├── summary
│       ├── status
│       └── updatedAt
│
├── tasks/
│   └── {taskId}/
│       ├── contextId
│       ├── label
│       ├── type (normal|shared|backend)
│       ├── completed
│       ├── assignedTo
│       ├── createdAt
│       └── completedAt
│
├── messages/
│   └── {messageId}/
│       ├── contextId
│       ├── type (system|user)
│       ├── content
│       ├── thinking (array)
│       ├── feedback
│       ├── createdAt
│       └── threadId
│
├── feedback/
│   └── {feedbackId}/
│       ├── messageId
│       ├── rating (up|down)
│       ├── questionnaire
│       ├── comments
│       ├── submittedAt
│       └── userId
│
└── alerts/
    └── {alertId}/
        ├── type
        ├── message
        ├── contextId
        ├── userId
        ├── acknowledged
        ├── createdAt
        └── expiresAt
```

## Database Selection Logic

### Use PostgreSQL for:
- **User Management**: Users, roles, permissions
- **Client Data**: Client information, branding
- **Patient Records**: MRN, demographics, medical data
- **Claims**: Structured claim data, financials
- **Authorizations**: Authorization requests and approvals
- **Visits**: Visit records, appointments
- **Audit Logs**: Compliance, tracking, reporting

### Use Firestore for:
- **Sessions**: Active user sessions, real-time state
- **Context**: Current working context (real-time updates)
- **Tasks**: Task lists (real-time collaboration)
- **Messages**: Chat messages (real-time streaming)
- **Feedback**: User feedback (quick writes)
- **Alerts**: Live alerts (real-time notifications)

## Mode Service Architecture

```python
# services/mode_service.py

class ModeService:
    """
    Manages mode switching and mode-specific logic
    Each mode has its own handler
    """
    
    def __init__(self):
        self.modes = {
            'eligibility': EligibilityModeHandler(),
            'front-desk': FrontDeskModeHandler(),
            'backend': BackendModeHandler(),
            'email-drafter': EmailDrafterModeHandler(),
        }
    
    def get_mode_handler(self, mode_name: str):
        return self.modes.get(mode_name)
    
    def get_context(self, mode_name: str, user_id: str):
        handler = self.get_mode_handler(mode_name)
        return handler.get_context(user_id)
    
    def execute_quick_action(self, mode_name: str, action: str, params: dict):
        handler = self.get_mode_handler(mode_name)
        return handler.execute_action(action, params)

class BaseModeHandler:
    """Base class for all mode handlers"""
    
    def get_context(self, user_id: str):
        # Get from Firestore
        pass
    
    def get_summary(self, context_id: str):
        # Generate summary based on mode
        pass
    
    def execute_action(self, action: str, params: dict):
        # Execute mode-specific action
        pass

class EligibilityModeHandler(BaseModeHandler):
    """Eligibility mode specific logic"""
    
    def execute_action(self, action: str, params: dict):
        if action == 'check_eligibility':
            # Query PostgreSQL for patient data
            # Query Firestore for current context
            # Return eligibility status
            pass
        elif action == 'request_authorization':
            # Create authorization in PostgreSQL
            # Update context in Firestore
            pass
```

## Component Service Architecture

```python
# services/component_service.py

class ComponentService:
    """
    Base service for component operations
    Components can be mode-aware or mode-agnostic
    """
    
    def __init__(self, db_selector):
        self.db_selector = db_selector  # Chooses Firestore vs PostgreSQL
    
    def get_component_data(self, component_type: str, context_id: str, mode: str = None):
        # Get data for specific component
        # Can be mode-aware
        pass

class TaskService(ComponentService):
    """Task management service"""
    
    def get_tasks(self, context_id: str):
        # Get from Firestore (real-time)
        return self.db_selector.firestore.collection('tasks').where('contextId', '==', context_id).get()
    
    def create_task(self, task_data: dict):
        # Write to Firestore
        pass
    
    def get_shared_tasks(self, context_id: str):
        # Get tasks shared from backend (Firestore)
        pass

class FeedbackService(ComponentService):
    """Feedback collection service"""
    
    def submit_feedback(self, message_id: str, feedback_data: dict):
        # Write to Firestore (quick write)
        # Optionally aggregate to PostgreSQL for analytics
        pass

class GuidanceService(ComponentService):
    """Dynamic guidance generation"""
    
    def get_guidance_actions(self, context_id: str, mode: str):
        # Generate dynamic buttons/forms based on:
        # - Current mode
        # - Current context
        # - User role
        # - Available data
        pass
```

## API Request/Response Examples

### Get Context for Mode

```http
GET /api/v1/modes/eligibility/context
Authorization: Bearer {token}

Response:
{
  "mode": "eligibility",
  "contextId": "ctx_123",
  "recordType": "Patient ID",
  "recordId": "MRN553",
  "status": "proceed",
  "summary": "Reviewing eligibility for patient MRN553..."
}
```

### Execute Quick Action

```http
POST /api/v1/modes/eligibility/quick-action
Authorization: Bearer {token}
Content-Type: application/json

{
  "action": "check_eligibility",
  "params": {
    "patientId": "MRN553"
  }
}

Response:
{
  "success": true,
  "data": {
    "eligible": true,
    "requiresAuth": true,
    "status": "pending"
  },
  "guidanceActions": [
    {"label": "Request Authorization", "action": "request_auth"},
    {"label": "View Full Record", "action": "view_record"}
  ]
}
```

### Get Tasks

```http
GET /api/v1/components/tasks?contextId=ctx_123
Authorization: Bearer {token}

Response:
{
  "tasks": [
    {
      "id": "task_1",
      "label": "Verify insurance coverage",
      "type": "shared",
      "completed": false,
      "source": "backend"
    },
    {
      "id": "task_2",
      "label": "Check prior authorization",
      "type": "normal",
      "completed": true
    }
  ]
}
```

### Submit Feedback

```http
POST /api/v1/components/feedback
Authorization: Bearer {token}
Content-Type: application/json

{
  "messageId": "msg_456",
  "rating": "up",
  "questionnaire": {
    "improvement": "More details needed",
    "comments": "Could use more context"
  }
}

Response:
{
  "success": true,
  "feedbackId": "fb_789"
}
```

## Database Selection Helper

```python
# db/db_selector.py

class DatabaseSelector:
    """
    Intelligent database selection based on data characteristics
    """
    
    def __init__(self):
        self.postgres = get_postgres_session()
        self.firestore = get_firestore_client()
    
    def select_db(self, operation: str, data_type: str):
        """
        Select appropriate database based on operation and data type
        """
        # Real-time, document-based → Firestore
        if data_type in ['session', 'context', 'task', 'message', 'alert', 'feedback']:
            return self.firestore
        
        # Structured, relational → PostgreSQL
        if data_type in ['user', 'patient', 'claim', 'authorization', 'visit', 'audit']:
            return self.postgres
        
        # Default to Firestore for flexibility
        return self.firestore
    
    def get_patient(self, patient_id: str):
        """Get patient from PostgreSQL"""
        return self.postgres.query(Patient).filter(Patient.mrn == patient_id).first()
    
    def get_context(self, context_id: str):
        """Get context from Firestore"""
        return self.firestore.collection('contexts').document(context_id).get()
```

## Summary

This architecture provides:

1. **Mode-Based Organization**: Each mode has dedicated endpoints and handlers
2. **Component Reusability**: Components have shared endpoints that work across modes
3. **Intelligent Database Selection**: PostgreSQL for structured data, Firestore for real-time
4. **Scalable Structure**: Easy to add new modes and components
5. **Clear Separation**: Services handle business logic, routes handle HTTP, models handle data
