## Phase 1 Implementation Plan (Mini + Sidecar)

- **Source PRD**: `PRDs/mobius_mini_sidecar_phase_1_prd.md`
- **Mapping**: `PRDs/mobius_mini_sidecar_phase_1_agent_map.md`
- **Relationship map**: `PRDs/mobius_mini_sidecar_phase_1_relationship_map.md`

### Goal
Implement Phase 1 as PRD intends:
- **PostgreSQL** = authoritative system of record (auditable history + constraints)
- **Firestore** = realtime projection layer (subscription-friendly docs)
- **Mini and Sidecar** = separate surface paths (`/api/v1/mini/*` and `/api/v1/sidecar/*`) but **share one underlying patient state**.

---

## 0) Repo baseline (current)
- Backend currently has **Flask only** (`backend/requirements.txt`) and two blueprints:
  - `backend/app/modes/mini.py` → `/api/v1/mini/*` (stub)
  - `backend/app/modes/chat.py` → `/api/v1/modes/chat/*` (echo agent)
- No database layer exists yet (no models, migrations, or Firestore client code).

---

## 1) Architecture decisions (defaults)

### 1.1 Backend persistence stack (recommended)
- **SQLAlchemy** for ORM/models
- **Alembic** for migrations
- **psycopg** (or `psycopg2-binary`) for PostgreSQL driver
- **google-cloud-firestore** for Firestore projections

### 1.2 CQRS / ownership rules
- **Decision agents compute** values (proceed/mode/tasking/outcomes/assignments); they do **not** write DBs directly.
- **CRUD is owned by modules**:
  - Postgres writes: `BackendAPIAndPersistenceModule` (transactional)
  - Event ledger writes: `EventLogAuditModule` (append-only)
  - Firestore writes: `RealtimeProjectionModule` (upserts projections)

---

## 2) Data model (PostgreSQL) — tables to implement (PRD §13.2)

Implement (at minimum) these tables and constraints (names match PRD):
- `tenant`, `role`, `app_user`, `application`, `policy_config`
- `invocation`, `session`
- `patient_identity_ref` (optional in Phase 1), `patient_context`, `patient_snapshot`
- `system_response`
- `mini_submission`
- `assignment`
- `event_log` (append-only)

### 2.1 Key constraints & indexes
- `patient_context`: unique (`tenant_id`, `patient_key`)
- `system_response`: index (`tenant_id`, `patient_context_id`, `computed_at desc`)
- `mini_submission`:
  - references `system_response_id`, `user_id`, `patient_context_id`
  - requires non-empty `note_text`
  - requires at least one override (`override_proceed` or `override_tasking`) non-null (as PRD specifies)
- `event_log`: append-only (no updates/deletes); payload must be PHI-safe

---

## 3) Firestore projections (PRD §13.3)

### 3.1 Patient State Projection (doc)
- Key: `tenants/{tenant_id}/patient_state/{patient_key}`
- Fields:
  - `snapshot`
  - `latest_system_response`
  - `last_mini_submission`
  - `flags` (e.g., `needs_ack`, `open_assignment_count`)
  - `updated_at`

### 3.2 User Inbox Projection (doc)
- Key: `tenants/{tenant_id}/user_inbox/{user_id}`
- Fields:
  - `open_assignments[]`
  - `updated_at`

---

## 4) Endpoints (surface split) + shared core

### 4.1 Shared core service boundary (server-internal)
Create a `SharedPatientStateCore` service that exposes:
- `get_patient_state(tenant_id, patient_key)` (read, projection-first)
- `persist_system_response(...)` (write)
- `persist_submission_ack(...)` (write on Send)
- `persist_assignment(...)` (write)

And emits internal events for the projection updater.

### 4.2 Mini endpoints (`/api/v1/mini/*`)
- `POST /api/v1/mini/status`
  - Input: `session_id`, `tenant_id?`, `patient_key?` (or use detection/override)
  - Output: UI-friendly minimal payload: snapshot + proceed + tasking (+ mode if shown)
- `POST /api/v1/mini/ack` (recommended; replaces/extends current `/note`)
  - Input: `session_id`, `tenant_id`, `patient_key`, `note_text`, optional overrides, `system_response_id`
  - Output: acknowledgement metadata
- `GET /api/v1/mini/patient/search` (keep)

### 4.3 Sidecar endpoints (`/api/v1/sidecar/*`)
- `GET /api/v1/sidecar/state`
  - Output: richer payload: snapshot + latest system response + history + assignments/inbox metadata
- `POST /api/v1/sidecar/ack`
  - Same submission semantics as Mini
- Optional: `POST /api/v1/sidecar/chat/message` if Sidecar chat should be distinct from `/api/v1/modes/chat/message`

---

## 5) Realtime consistency pipeline (PRD §12.3)

1. **Postgres transaction** writes authoritative rows (`system_response`/`mini_submission`/`assignment`)
2. Append audit event to `event_log` (`System.Response`, `User.Acknowledged`, etc.)
3. Emit internal event (queue/in-process for Phase 1)
4. `RealtimeProjectionModule` updates Firestore projections asynchronously
5. Clients subscribe to Firestore docs for <1s updates

---

## 6) Implementation sequence (do this in order)

### Phase A — Foundations
1. Add dependencies (SQLAlchemy + Alembic + Postgres driver + Firestore client).
2. Add backend config for DB URLs/credentials (env-driven).
3. Add Alembic scaffolding and first migration.

### Phase B — Schema + CRUD modules
4. Implement SQLAlchemy models for PRD tables (Phase 1 subset is OK if wired to migration).
5. Generate and run migrations.
6. Implement `BackendAPIAndPersistenceModule` (transaction wrappers + CRUD).
7. Implement `EventLogAuditModule` (append-only + PHI-safe payload enforcement hooks).

### Phase C — Projections
8. Implement Firestore client + `RealtimeProjectionModule` upserts for:
   - `patient_state` projection
   - `user_inbox` projection

### Phase D — Surface split
9. Implement `SharedPatientStateCore` (shared services).
10. Extend `/api/v1/mini/*` endpoints to call SharedCore.
11. Add `/api/v1/sidecar/*` endpoints and call SharedCore.

### Phase E — Decision agents
12. Implement minimal decision agents (even rule-based stubs):
   - record detection (or accept provided `patient_key`)
   - proceed/mode/tasking computations
   - outcome computation and assignment decisioning (policy-driven)

### Phase F — Frontend wiring + tests
13. Update extension API client to call `/mini/*` vs `/sidecar/*` consistently.
14. Add backend unit tests for persistence + event log + projection updates.
15. Add integration tests for Mini + Sidecar flows.

---

## 7) What we implement first (pragmatic)
Start by making the system **buildable** end-to-end with minimal decisioning:
- Postgres schema + migrations
- Shared core + event log + projection updater (even if projection updater is synchronous initially)
- Mini status + ack endpoints writing rows + projecting patient_state
- Sidecar state endpoint reading the same projected patient_state

