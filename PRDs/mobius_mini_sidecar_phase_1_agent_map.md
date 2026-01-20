## PRD → Decision Agent + Module Mapping
### Mobius Mini + Sidecar (Phase 1)

- **PRD**: `PRDs/mobius_mini_sidecar_phase_1_prd.md`
- **Generated**: 2026-01-19
- **Mode**: analysis-only (no implementation changes in this step)
- **Visual relationship map**: `PRDs/mobius_mini_sidecar_phase_1_relationship_map.md`

### Terminology note
Per your definition, an **agent makes decisions**. In this PRD, most responsibilities are **modules/services**, not decision agents.

The two “agents” you listed are treated below as **modules** (they produce data / render UI; they don’t decide outcomes).

### Available modules (given)
- **`PatientDataAgent` (module)**: creates patient data (patient snapshot + directory/search seed data)
- **`UIStripAgent` (module)**: implements UI strip surfaces (Mini + Sidecar) and their data bindings

### Decision agents implied by the PRD (missing unless you already have them elsewhere)
- **`RecordDetectionAgent`**: decides/derives `patient_key` from page/app context (or validates provided key)
- **`ProceedDecisionAgent`**: decides proceed indicator (grey/green/yellow/blue) from context + policy
- **`ExecutionModeDecisionAgent`**: decides execution mode (agentic/copilot/user-driven)
- **`TaskingDecisionAgent`**: decides tasking summary and “needs acknowledgement” style flags
- **`OutcomeComputationAgent`**: computes derived outcomes (Acknowledged/Unacknowledged/Dismissed/Invalidated)
- **`PolicyDecisionAgent`**: decides show/hide, UI variants, timeout thresholds, notification/assignment rules by tenant/role/site
- **`AssignmentDecisionAgent`**: decides when/whom to assign/notify for offline continuation

### Missing modules/services (flagged because PRD requires them)
- **`SharedPatientStateCore`**: shared read/write services used by both surfaces (patient state, submissions, event log, projection triggers)
- **`BackendAPIAndPersistenceModule`**: API endpoints + PostgreSQL tables + write paths + validation
- **`RealtimeProjectionModule`**: Firestore projections, fanout, subscriptions, reconnect/idempotency plumbing
- **`EventLogAuditModule`**: append-only event log storage + correlation IDs + PHI-safe payload schemas
- **`SecurityComplianceModule`**: tokenization/hashing + PHI-safe logging enforcement
- **`TestAutomationModule`**: unit/integration test harness and scenarios for PRD behaviors

### Repo touchpoints (current)
- **Mini backend stubs**: `backend/app/modes/mini.py` (`/api/v1/mini/status`, `/api/v1/mini/note`, `/api/v1/mini/patient/search`)
- **Extension Mini + Sidecar UI**: `extension/src/content.ts`
- **Extension API client**: `extension/src/services/api.ts`
- **UI types**: `extension/src/types/index.ts`
- **Chat-only backend “agent”** (not PRD-specific): `backend/app/agents/base_agent/conversation_agent.py`

## Mini vs Sidecar: separate surface paths (new insight)

- **Why**: Mini and Sidecar have different UX + latency constraints and payload needs, so keeping handlers separate reduces coupling.
- **Invariant**: keep **one shared underlying patient state** and decisioning pipeline so both surfaces reference the same latest System Response / Submission / Outcome state.

### Recommended split
- **Backend routing**:
  - Mini: `/api/v1/mini/*` (already exists)
  - Sidecar: `/api/v1/sidecar/*` (recommended)
- **Frontend call paths**:
  - Mini calls only `/mini/*`
  - Sidecar calls only `/sidecar/*` (and/or sidecar chat endpoints)
  - Both share the same `patient_key` identity and subscribe to the same underlying patient state projection.

### Recommended module decomposition
- `UIStripAgent` (module) decomposes into:
  - **`MiniSurfaceModule`**: Mini-only payload shaping + endpoint handlers
  - **`SidecarSurfaceModule`**: Sidecar-only payload shaping + richer endpoint handlers
- Add a shared module boundary:
  - **`SharedPatientStateCore`**: shared read/write services used by both surfaces (patient state, submissions, event log, projection triggers)

## Data schema ownership (who does CRUD)

PRD model: **PostgreSQL = authoritative system of record**; **Firestore = realtime projection**.

### PostgreSQL (authoritative) — CRUD owners

| Entity (PRD) | Storage | Create | Read | Update | Delete |
|---|---|---|---|---|---|
| `tenant`, `role`, `app_user`, `application` | Postgres | `BackendAPIAndPersistenceModule` | `BackendAPIAndPersistenceModule` | `BackendAPIAndPersistenceModule` | avoid hard delete |
| `policy_config` (versioned) | Postgres | `BackendAPIAndPersistenceModule` | `BackendAPIAndPersistenceModule` | avoid (prefer new version) | avoid hard delete |
| `patient_context` | Postgres | `BackendAPIAndPersistenceModule` (via `SharedPatientStateCore`) | `SharedPatientStateCore` | `BackendAPIAndPersistenceModule` | avoid hard delete |
| `patient_snapshot` (versioned) | Postgres | `BackendAPIAndPersistenceModule` | `SharedPatientStateCore` | avoid (insert new version) | avoid hard delete |
| `system_response` (append-only) | Postgres | `BackendAPIAndPersistenceModule` (after decision agents compute) | `SharedPatientStateCore` | avoid (insert new response) | avoid hard delete |
| `mini_submission` (ack; append-only) | Postgres | `BackendAPIAndPersistenceModule` (triggered by Mini/Sidecar Send) | `SharedPatientStateCore` | avoid | avoid hard delete |
| `assignment` | Postgres | `BackendAPIAndPersistenceModule` (after `AssignmentDecisionAgent`) | `SharedPatientStateCore` | `BackendAPIAndPersistenceModule` (status transitions) | avoid hard delete |
| `event_log` (append-only ledger) | Postgres | `EventLogAuditModule` | `EventLogAuditModule` | never | never |

### Firestore (derived projections) — CRUD owners

| Projection doc (PRD) | Storage | Upsert/Update | Read | Delete |
|---|---|---|---|---|
| `tenants/{tenant_id}/patient_state/{patient_key}` | Firestore | `RealtimeProjectionModule` | `UIStripAgent` (Mini + Sidecar subscribe) | rare (retention/cleanup policy) |
| `tenants/{tenant_id}/user_inbox/{user_id}` | Firestore | `RealtimeProjectionModule` | `UIStripAgent` (Sidecar) | rare |
| `tenants/{tenant_id}/invocation_presence/{invocation_id}` (optional) | Firestore | `RealtimeProjectionModule` | `UIStripAgent` | optional/TTL |

### Rule of thumb
- **Decision agents compute** (proceed/mode/tasking/outcomes/assignments) but do **not** write DBs directly.\n+- **Modules do CRUD**:\n+  - Postgres writes: `BackendAPIAndPersistenceModule` (+ `EventLogAuditModule` for append-only ledger)\n+  - Firestore writes: `RealtimeProjectionModule`\n+  - Client reads/subscribes: `UIStripAgent` (Mini/Sidecar)\n+
---

## Task inventory (Phase 1) with decision agents vs modules

### UI surfaces: Mini + Sidecar
- **T01 — Mini UI (PRD §4.1, §10)**  
  - **Surface path**: Mini (`/api/v1/mini/*`)
  - **Module owner**: `MiniSurfaceModule` (within `UIStripAgent`)
  - **Decision agents involved**: `RecordDetectionAgent`, `ProceedDecisionAgent`, `ExecutionModeDecisionAgent`, `TaskingDecisionAgent`, `PolicyDecisionAgent`  
  - **PRD requirements**: patient snapshot, proceed indicator, execution mode, tasking summary, quick note + Send acknowledgement entry; “read-only projection + acknowledgement entry”.  
  - **Blocked by missing**:
    - **decision agents**: all listed above (unless already implemented elsewhere)
    - **modules**: `SharedPatientStateCore`, `BackendAPIAndPersistenceModule`, `RealtimeProjectionModule`  
  - **Likely repo touchpoints later**: `extension/src/content.ts`, `extension/src/services/api.ts`, `backend/app/modes/mini.py`

- **T02 — Sidecar UI (PRD §4.2)**  
  - **Surface path**: Sidecar (`/api/v1/sidecar/*`)
  - **Module owner**: `SidecarSurfaceModule` (within `UIStripAgent`)
  - **Decision agents involved**: `TaskingDecisionAgent`, `OutcomeComputationAgent`, `PolicyDecisionAgent`  
  - **PRD requirements**: expanded context, chat/note composition, action buttons, task visibility, history/metadata.  
  - **Blocked by missing modules**: `SharedPatientStateCore`, `BackendAPIAndPersistenceModule`, `EventLogAuditModule`, `RealtimeProjectionModule`  
  - **Likely repo touchpoints later**: `extension/src/content.ts`

- **T03 — Shared state between Mini and Sidecar (PRD §4, §11)**  
  - **Surface path**: Shared (both surfaces converge on one state)
  - **Module owner**: `SharedPatientStateCore`  
  - **Decision agents involved**: (none; this is synchronization, not decision-making)  
  - **PRD requirements**: “Mini and Sidecar always reference the same underlying state”; one Patient Context at a time.  
  - **Blocked by missing modules**: `SharedPatientStateCore`, `RealtimeProjectionModule`, `BackendAPIAndPersistenceModule`  
  - **Likely repo touchpoints later**: `extension/src/content.ts`, `extension/src/utils/session.ts`, `extension/src/utils/uiDefaults.ts`

- **T04 — Send == acknowledgement (PRD §1.4, §3.3, §6.3)**  
  - **Surface path**: Shared (Send exists in both surfaces)
  - **Module owners**: `MiniSurfaceModule` + `SidecarSurfaceModule` (trigger), `SharedPatientStateCore` (validate/persist)  
  - **Decision agents involved**: `OutcomeComputationAgent` (outcome depends on ack presence)  
  - **Blocked by missing modules**: `SharedPatientStateCore`, `BackendAPIAndPersistenceModule`, `EventLogAuditModule`  
  - **Notes**: “Send is the only state-committing user event”; non-send interactions must not mutate state.

- **T05 — Draft/override UX rules (PRD §10.2)**  
  - **Surface path**: Shared (local drafts exist in both surfaces)
  - **Module owners**: `MiniSurfaceModule` + `SidecarSurfaceModule` (local drafts)
  - **Decision agents involved**: (none; this is local UX validation, not system decisioning)  
  - **PRD requirements**: local override draft with dirty flag + validation; note required when overrides present; Send enabled/disabled.  
  - **Blocked by missing modules**: `SharedPatientStateCore` + `BackendAPIAndPersistenceModule` (canonical submission contract + server-side validation)

### Patient data (display + search seed)
- **T06 — Patient snapshot fields + masking rules (PRD §10.2, §13.2.10)**  
  - **Module owner**: `PatientDataAgent`  
  - **Decision agents involved**: `PolicyDecisionAgent` (policy-controlled display rules)  
  - **PRD requirements**: display name (policy-controlled), external ID label, masked identifier, DOB optional.  
  - **Blocked by missing modules**: `SecurityComplianceModule`, `BackendAPIAndPersistenceModule`

- **T07 — Patient directory/search seed data (PRD §3.2, §10.2; supports Mini correction modal)**  
  - **Surface path**: Mini (`/api/v1/mini/*`)
  - **Module owners**: `PatientDataAgent` (data), `MiniSurfaceModule` (UI wiring)  
  - **Decision agents involved**: (none; seed data is not decisioning)  
  - **Blocked by missing modules**: `SharedPatientStateCore` (if tenant/policy-aware), `BackendAPIAndPersistenceModule` (real search), `SecurityComplianceModule` (tokenization/hashing constraints)
  - **Current repo touchpoints**: `backend/app/modes/mini.py` (stub search), `extension/src/content.ts` (modal/search UI)

### Record binding & detection
- **T08 — Patient key acquisition (PRD §3.2, §10.2 “stable patient key (tokenized)”)**  
  - **Decision agent owner**: **missing** `RecordDetectionAgent`  
  - **Blocked by missing modules**: `SecurityComplianceModule`  
  - **Also depends on decision agents**: `PolicyDecisionAgent` (what sources are allowed per tenant/app)  
  - **Notes**: current extension supports manual override; PRD expects detection or provided identifier.

### Backend API contracts & persistence (PostgreSQL + Firestore)
- **T09 — Define Mini/Sidecar API contract around PRD entities (PRD §10–§13)**  
  - **Surface path**: Shared (surface endpoints differ; contract/core is shared)
  - **Module owners**: **missing** `SharedPatientStateCore` + `BackendAPIAndPersistenceModule`  
  - **Decision agents involved**: `ProceedDecisionAgent`, `ExecutionModeDecisionAgent`, `TaskingDecisionAgent`, `OutcomeComputationAgent` (contract must carry their outputs)  
  - **PRD requirements**: patient context, latest system response, submission (ack), projections for realtime.  
  - **Separation detail**: `/api/v1/mini/*` and `/api/v1/sidecar/*` should both delegate to the same shared core services; avoid duplicating decisioning in surface handlers.
  - **Repo touchpoints later**: `backend/app/modes/mini.py`, (new) routes/services/models; `extension/src/services/api.ts`

- **T10 — PostgreSQL schema & constraints (PRD §13.2)**  
  - **Module owner**: **missing** `BackendAPIAndPersistenceModule`  
  - **Decision agents involved**: (none; storage schema)  
  - **PRD requirements**: tables like `patient_context`, `patient_snapshot`, `system_response`, `mini_submission`, `assignment`, `event_log`, plus tenant/user/role/policy.  
  - **Blocked by missing modules**: `SecurityComplianceModule` (PHI-safe payloads)

- **T11 — Firestore projections schema (PRD §12.2, §13.3)**  
  - **Module owner**: **missing** `RealtimeProjectionModule`  
  - **Decision agents involved**: (none; projection shape)  
  - **PRD requirements**: `patient_state` projection (tenant + patient_key), `user_inbox`, optional presence docs.

- **T12 — Consistency pipeline (PRD §12.3)**  
  - **Module owner**: **missing** `RealtimeProjectionModule`  
  - **Decision agents involved**: (none; pipeline)  
  - **PRD requirements**: Postgres transaction → internal event → async Firestore projection update; UI subscribes to Firestore.

### System Responses, acknowledgements, outcomes, audit
- **T13 — Emit `System.Response` events (PRD §6.1)**  
  - **Module owner**: **missing** `EventLogAuditModule`  
  - **Decision agents involved**: `ProceedDecisionAgent`, `ExecutionModeDecisionAgent`, `TaskingDecisionAgent` (they produce the response content)  
  - **Blocked by missing modules**: `BackendAPIAndPersistenceModule`, `SecurityComplianceModule`

- **T14 — Emit `User.Acknowledged` on Send (PRD §6.3)**  
  - **Module owners**: `UIStripAgent` (trigger), **missing** `EventLogAuditModule` + `BackendAPIAndPersistenceModule` (persist + correlate)  
  - **Decision agents involved**: `OutcomeComputationAgent` (ack presence drives outcome)  
  - **Notes**: submission must reference base system response and include overrides + note text.

- **T15 — Optional `User.Interaction` sampling (PRD §6.2)**  
  - **Module owner**: **missing** `EventLogAuditModule`  
  - **Decision agents involved**: (none)  
  - **Notes**: must not commit state; useful for UX/telemetry only.

- **T16 — Compute outcomes (PRD §1.5, §3.4, §6.4)**  
  - **Decision agent owner**: **missing** `OutcomeComputationAgent`  
  - **Module required**: `EventLogAuditModule` (inputs) + `BackendAPIAndPersistenceModule` (storage of computed outcome/projection)  
  - **PRD requirements**: Acknowledged / Unacknowledged / Dismissed / Invalidated computed from events (neutral storage).

### Realtime + multi-user/multi-tab + offline continuation
- **T17 — Realtime UI updates <1s (PRD §7, §8)**  
  - **Module owner**: **missing** `RealtimeProjectionModule`  
  - **Decision agents involved**: (none)  
  - **Blocked by missing modules**: `BackendAPIAndPersistenceModule` (event + projection inputs)

- **T18 — Multi-tab + multi-user visibility (PRD §2.1)**  
  - **Module owner**: **missing** `RealtimeProjectionModule`  
  - **Decision agents involved**: (none)  
  - **Notes**: client subscriptions + projection design + presence (optional).

- **T19 — Offline pickup: assignments/notifications + inbox (PRD §3.5, §7, §12.2)**  
  - **Decision agent owner**: **missing** `AssignmentDecisionAgent`  
  - **Decision agents involved**: `PolicyDecisionAgent` (rules), `OutcomeComputationAgent` (unack detection)  
  - **Blocked by missing modules**: `BackendAPIAndPersistenceModule`, `RealtimeProjectionModule`  
  - **UI dependency (module)**: `UIStripAgent` to render “inbox/open assignments” once projections exist.

### Policy-driven configuration
- **T20 — Tenant policy config (PRD §9, §2.1 entry gating)**  
  - **Decision agent owner**: **missing** `PolicyDecisionAgent`  
  - **Module required**: `BackendAPIAndPersistenceModule` (store policy) + `UIStripAgent` (consume show/hide + variants client-side)  
  - **PRD requirements**: mini show/hide rules, unack timeout threshold, notification rules, UI variants by role/app.  
  - **Notes**: current extension has a per-domain allowlist (not tenant policy).

### Non-functional + security/compliance
- **T21 — Idempotent handling + reconnect safety (PRD §8)**  
  - **Module owner**: **missing** `RealtimeProjectionModule` (and `BackendAPIAndPersistenceModule` for idempotency keys)  
  - **Decision agents involved**: (none)  

- **T22 — HIPAA-safe logging + PHI controls (PRD §8 “no raw PHI in events”, §13.2.14)**  
  - **Module owner**: **missing** `SecurityComplianceModule`  
  - **Decision agents involved**: (none)  
  - **Notes**: tokenized patient_key, hashed external IDs, payload schemas that avoid raw PHI.

### Testing
- **T23 — Backend + frontend tests for Mini/Sidecar flows (PRD end-to-end)**  
  - **Module owner**: **missing** `TestAutomationModule`  
  - **Decision agents involved**: all decision agents above (tests must validate decision outputs + invariants)  
  - **Likely repo touchpoints later**: `tests/integration/*`, `tests/unit/*`, `backend/test_conversation_agent.py`, `tests/integration/frontend/*`

---

## Quick responsibility matrix (what your current modules can cover)
- **`UIStripAgent` (module) can own**: Mini/Sidecar UI, shared client-side state, validation UX, “Send” semantics on the client, wiring to backend APIs (once defined).
- **`PatientDataAgent` (module) can own**: Patient snapshot formatting/masking guidance, sample patient directory/search seed data, patient data fixtures for UI development.
- **Everything else is blocked without new modules + decision agents**, primarily persistence + realtime projection + audit/event storage, plus decision agents for proceed/mode/tasking/policy/assignments.

## Recommended next adds (highest unblock value)
### Modules (plumbing)
1. **`BackendAPIAndPersistenceModule`**
2. **`RealtimeProjectionModule`**
3. **`EventLogAuditModule`**
4. **`SecurityComplianceModule`**

### Decision agents (PRD “makes decisions”)
1. **`RecordDetectionAgent`**
2. **`ProceedDecisionAgent`**
3. **`ExecutionModeDecisionAgent`**
4. **`TaskingDecisionAgent`**
5. **`PolicyDecisionAgent`**
6. **`AssignmentDecisionAgent`**
7. **`OutcomeComputationAgent`**
