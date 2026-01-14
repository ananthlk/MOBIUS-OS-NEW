# Mobius OS Test Suite

Test structure for Mobius OS project with unit and integration tests for both backend and frontend.

## Structure

```
tests/
├── unit/
│   ├── backend/          # Backend unit tests
│   │   └── test_conversation_agent.py
│   └── frontend/         # Frontend unit tests
│       └── ConversationAgent.test.ts
└── integration/
    ├── backend/          # Backend integration tests
    │   └── test_chat_mode_endpoint.py
    └── frontend/         # Frontend integration tests
        └── ChatModeIntegration.test.ts
```

## Backend Tests

### Unit Tests

Comprehensive test cases for individual components (e.g., ConversationAgent).

**Run unit tests:**
```bash
cd backend
source ../venv/bin/activate
pytest tests/unit/backend/ -v
```

**Test Coverage:**
- ConversationAgent class methods
- Message processing
- Session ID validation
- Error handling
- Edge cases

### Integration Tests

Tests for API endpoints and full request/response cycles.

**Run integration tests:**
```bash
cd backend
source ../venv/bin/activate
pytest tests/integration/backend/ -v
```

**Test Coverage:**
- HTTP endpoints
- Request/response format
- Error responses
- CORS headers
- Multiple requests

## Frontend Tests

### Unit Tests

Tests for individual frontend components and utilities.

**Run unit tests:**
```bash
cd extension
npm test
```

**Test Coverage:**
- API service functions
- Session management
- Component rendering
- Utility functions

### Integration Tests

End-to-end tests for frontend-backend integration.

**Run integration tests:**
```bash
cd extension
npm test -- --testPathPattern=integration
```

**Test Coverage:**
- Full message flow
- Session persistence
- Error handling
- Request/response validation

## Running All Tests

### Backend
```bash
cd backend
source ../venv/bin/activate
pytest tests/ -v --cov=app
```

### Frontend
```bash
cd extension
npm test -- --coverage
```

## Test Coverage Goals

- **Unit Tests**: 80%+ coverage for core components
- **Integration Tests**: All API endpoints and critical user flows

## Adding New Tests

### Backend Unit Test
Create a new file in `tests/unit/backend/` following the pattern:
- `test_<component_name>.py`
- One comprehensive test class per component
- Test all methods and edge cases

### Backend Integration Test
Create a new file in `tests/integration/backend/` following the pattern:
- `test_<mode>_endpoint.py`
- Test full HTTP request/response cycle
- Test error cases and edge conditions

### Frontend Unit Test
Create a new file in `tests/unit/frontend/` following the pattern:
- `<ComponentName>.test.ts`
- Test component functionality in isolation

### Frontend Integration Test
Create a new file in `tests/integration/frontend/` following the pattern:
- `<Feature>Integration.test.ts`
- Test end-to-end user flows
