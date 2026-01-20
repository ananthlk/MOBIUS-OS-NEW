# Mobius Mini + Sidecar
## Phase 1 Product Requirements Document (PRD)

---

## Section 0 — Purpose & Framing

### 0.1 Purpose
Mobius Mini and Sidecar provide **context-aware system responses** embedded inside third‑party applications, enabling users to **acknowledge, act on, or ignore system responses** related to healthcare financial contexts (starting with Patient).

The system must:
- Surface information without requiring action
- Capture explicit acknowledgement when it occurs
- Record non‑acknowledgement without inferring intent
- Support live updates, multi‑user visibility, and offline continuation

### 0.2 What this is not
- Not a task manager
- Not a workflow engine
- Not a system of record
- Not an agent that assumes user intent

Mobius is a **response + acknowledgement system** layered on top of existing records.

---

## Section 1 — Core Definitions & Vocabulary (LOCKED)

### 1.1 Record
A **Record** is a long‑lived external entity (e.g., Patient, Claim).

Properties:
- Exists outside Mobius
- Has durable identity
- Does not have status in Mobius
- May appear many times across sessions, users, and applications

Mobius never owns the record.

---

### 1.2 System Response
A **System Response** occurs when Mobius computes and surfaces information related to a Record.

Examples:
- Patient context surfaced in Mini
- Proceed / Mode / Tasking computed
- Task recommendations updated

Characteristics:
- System‑generated
- Does not imply action is required
- May occur multiple times for the same record
- Observable and auditable

---

### 1.3 User Interaction
A **User Interaction** is navigational or exploratory behavior.

Examples:
- Opening Sidecar
- Typing without submission
- Switching tabs
- Viewing Mini

Characteristics:
- Does not commit intent
- Does not change system state
- May be ephemeral or sampled

---

### 1.4 User Acknowledgement
A **User Acknowledgement** is an explicit submission via the **Send** action.

It represents:
- Awareness of the system response
- Optional intent (note, confirmation, action)
- The only user action that commits state

Absence of acknowledgement is meaningful and must be recorded.

---

### 1.5 Derived Outcomes
Outcomes are **computed**, not asserted.

| Outcome | Condition |
|------|----------|
| Acknowledged | User Acknowledgement exists |
| Unacknowledged | System Response occurred with no acknowledgement |
| Dismissed | Explicit user dismissal |
| Invalidated | Context changed (record switch, navigation) |

UI and analytics may label *Unacknowledged* as “Ignored,” but storage remains neutral.

---

## Section 2 — Product Scope (Phase 1)

### 2.1 In Scope
- Patient invocation type
- Mini and Sidecar UI surfaces
- System Responses
- User Acknowledgements via Send
- Live updates
- Multi‑tab and multi‑user visibility
- Offline pickup of unacknowledged responses
- Audit‑safe event logging

### 2.2 Out of Scope
- Multi‑record chaining (e.g., patient → claims graph)
- Advanced agent autonomy
- SLA‑based workflow escalation
- Analytics dashboards (events may be logged)

---

## Section 3 — Canonical User Workflow

### 3.1 Entry
1. User opens a supported site or application
2. Mobius evaluates policy (tenant, role, site)
3. Mini is shown or hidden

---

### 3.2 System Response
4. Mobius detects or is provided a Patient identifier
5. Mobius computes and surfaces the current state:
   - Patient snapshot
   - Proceed indicator
   - Execution mode
   - Tasking summary

This constitutes a **System Response**.

---

### 3.3 User Paths

**Path A — Acknowledge**
- User enters note and/or selects an action
- User presses **Send**
- User Acknowledgement is recorded
- Automation may trigger

**Path B — Interact Only**
- User opens Sidecar or explores
- No submission occurs
- No acknowledgement recorded

**Path C — No Interaction**
- User leaves page or session ends

---

### 3.4 Outcome Computation
- Path A → Outcome = Acknowledged
- Path B or C → Outcome = Unacknowledged
- Context change → Outcome = Invalidated

---

### 3.5 Offline Continuation
If a System Response requires acknowledgement:
- An assignment or notification may be generated
- User may pick it up in a later session
- Prior context is reconstructed

---

## Section 4 — UI Surfaces

### 4.1 Mini
Mini displays:
- Record snapshot
- Proceed indicator
- Execution mode
- Tasking summary
- Quick input with Send action

Mini is a **read‑only projection** of current state plus acknowledgement entry.

### 4.2 Sidecar
Sidecar provides:
- Expanded context
- Chat or note composition
- Action buttons
- Task visibility
- History and metadata

Mini and Sidecar always reference the same underlying state.

---

## Section 5 — State & Indicators

### 5.1 Proceed Indicator
Represents system confidence or readiness.

Values:
- Grey — Not assessed
- Green — No action required or can proceed
- Yellow — Attention or review required
- Blue — System error or unavailable

### 5.2 Execution Mode
Indicates who can advance the state:
- Agentic
- Copilot
- User‑driven

### 5.3 Tasking Summary
A derived summary of active or pending tasks. Tasks justify indicators but do not define them.

---

## Section 6 — Event Model

### 6.1 System.Response
Emitted whenever Mobius surfaces or updates computed state.

### 6.2 User.Interaction
Optional navigational events (non‑committal).

### 6.3 User.Acknowledged
Emitted when Send is pressed. This is the only state‑committing user event.

### 6.4 Outcome
Computed from the presence or absence of acknowledgement events.

---

## Section 7 — Realtime & Offline Behavior

- Live clients subscribe to state updates
- Offline users receive assignments or notifications
- On login, unacknowledged responses are surfaced
- State is reconstructed independently of original page context

---

## Section 8 — Non‑Functional Requirements

- Realtime update latency target: <1 second
- Idempotent event handling
- Refresh and reconnect safety
- HIPAA‑safe logging (no raw PHI in events)
- Support high concurrency per tenant

---

## Section 9 — Policy‑Driven Configuration

Configurable by tenant:
- Mini show/hide rules
- Timeout threshold for unacknowledged responses
- Notification and assignment rules
- UI variants by role and application

---

## Section 10 — Front‑End Data Model (Mini, Patient)

> This section defines the **minimum data model required by the front end** to implement the Mini for record = Patient, as specified in this PRD. It is intentionally UI‑oriented and does not prescribe backend implementation details beyond what is required for correctness and realtime behavior.

### 10.1 Core concepts
The Mini binds to a **Patient Context**, renders the **latest System Response**, allows the user to draft **overrides**, and records a **submission** when Send is pressed.

The Mini does not own records or workflows; it renders and commits assertions.

### 10.2 Required front‑end entities

**Patient Context**
- Tenant identifier
- Stable patient key (tokenized; no raw MRN)
- Source system (optional)
- Last updated timestamp

**Patient Snapshot (display‑only)**
- Display name (policy‑controlled)
- External identifier label (e.g., ID / MRN)
- Masked identifier
- Date of birth (optional)

**System Response (latest)**
- Response identifier
- Timestamp of computation
- Proceed indicator (grey / green / yellow / blue)
- Execution mode (agentic / copilot / user‑driven)
- Tasking summary (Mini‑level)
- Optional rationale text

**Override Draft (local, non‑committal)**
- Proposed Proceed override (optional)
- Proposed Tasking override (optional)
- Dirty flag (differs from system values)
- Validation state (send enabled / disabled)

**Note Draft (local)**
- Free‑text note
- Required when overrides are present

**Submission (result of Send)**
- Submission identifier
- Submitting user
- Timestamp
- Base system response referenced
- Overrides asserted
- Note text

---

## Section 11 — Data Relationships (Schematic)

The following schematic describes how data relates conceptually. It is intended to guide both front‑end state management and backend persistence decisions.

```
Tenant
 └─ User
     └─ Invocation (Mini instance)
          └─ Patient Context (patient_key)
               ├─ Patient Snapshot (display)
               ├─ System Response (latest assessment)
               │     └─ Proceed / Mode / Tasking
               ├─ Submission (override + note)
               ├─ Assignment (offline pickup)
               └─ Event Log (audit)
```

The Mini always renders **one Patient Context at a time** and reacts to changes in the latest System Response or Submission.

---

## Section 12 — Storage & Realtime Strategy

> This section specifies **where data should live** to support live updates, offline pickup, and auditability. It does not mandate technology choices beyond PostgreSQL and Firestore.

### 12.1 PostgreSQL (System of Record)
PostgreSQL stores all **authoritative and auditable data**:
- Tenant, User, Role
- Policy and configuration
- Patient Context
- Patient Snapshot
- System Response
- Submission (acknowledgement via override)
- Assignment / notification
- Event Log (append‑only)

PostgreSQL is the source of truth for compliance, replay, and reporting.

### 12.2 Firestore (Realtime Projection Layer)
Firestore stores **denormalized, subscription‑friendly projections** used by the UI:

**Patient State Projection** (one per tenant + patient key)
- Latest patient snapshot
- Latest Proceed / Mode / Tasking values
- Timestamp of last System Response
- Acknowledgement summary (last submission time, user)
- Flags such as “needs acknowledgement”

**User Inbox Projection** (per user)
- Open assignments
- Reason codes
- Last updated timestamps

Firestore is optimized for:
- <1s live UI updates
- Multi‑tab and multi‑user synchronization
- Offline resume

### 12.3 Consistency model
1. Write authoritative data to PostgreSQL in a transaction
2. Emit an internal event
3. Update Firestore projections asynchronously
4. Clients subscribe to Firestore for realtime updates

Temporary projection lag is acceptable; PostgreSQL remains authoritative.

---

## Section 13 — Relational Schema (PostgreSQL) and Document Projections (Firestore)

> This section makes the data model **buildable** by specifying concrete tables, primary keys, and foreign-key relationships. The schema is intentionally **Patient-only** for Phase 1.

### 13.1 Design note: Patient Context vs Master Patient Repository
Mobius does **not** own the canonical patient record. A Patient may exist in a **master patient repository** (EHR/EMPI/CRM). Mobius stores a **Patient Context** as a stable, tenant-scoped binding to a tokenized patient key (and optionally a source-system reference), plus a **display snapshot** for UI.

- **Master Patient**: authoritative, external
- **Patient Context**: Mobius-owned binding + UI state anchor
- **Patient Snapshot**: non-authoritative display fields captured for the UI

### 13.2 PostgreSQL tables

#### 13.2.1 `tenant`
- **PK**: `tenant_id`
- Columns: `tenant_id`, `name`, `created_at`

#### 13.2.2 `role`
- **PK**: `role_id`
- Columns: `role_id`, `name`, `created_at`

#### 13.2.3 `app_user`
- **PK**: `user_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK**: `role_id` → `role.role_id`
- Columns: `user_id`, `tenant_id`, `role_id`, `status`, `created_at`, `last_login_at`

#### 13.2.4 `application`
- **PK**: `application_id`
- Columns: `application_id`, `display_name`, `created_at`

#### 13.2.5 `policy_config`
- **PK**: (`tenant_id`, `version`)
- **FK**: `tenant_id` → `tenant.tenant_id`
- Columns: `tenant_id`, `version`, `allowlist_rules_json`, `ui_variants_json`, `timeout_rules_json`, `notification_rules_json`, `created_at`

#### 13.2.6 `invocation`
Represents a single Mini instance (e.g., a tab).
- **PK**: `invocation_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK**: `user_id` → `app_user.user_id`
- **FK**: `application_id` → `application.application_id`
- Columns: `invocation_id`, `tenant_id`, `user_id`, `application_id`, `page_signature`, `surface_type` (mini/sidecar), `ui_variant_id`, `created_at`, `last_seen_at`, `status`

#### 13.2.7 `session`
Time-bounded activity within an invocation.
- **PK**: `session_id`
- **FK**: `invocation_id` → `invocation.invocation_id`
- Columns: `session_id`, `invocation_id`, `started_at`, `ended_at`, `end_reason`

#### 13.2.8 `patient_identity_ref`
Optional mapping to an external/master patient record. Use when you have a stable external identifier.
- **PK**: `patient_identity_ref_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- Columns: `patient_identity_ref_id`, `tenant_id`, `source_system` (e.g., EHR name), `external_patient_id_hash`, `created_at`

> `external_patient_id_hash` should be a one-way hash of the external ID (or a token) to reduce PHI exposure.

#### 13.2.9 `patient_context`
Mobius-owned anchor for UI state, scoped to tenant + patient key.
- **PK**: `patient_context_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK (optional)**: `patient_identity_ref_id` → `patient_identity_ref.patient_identity_ref_id`
- Columns: `patient_context_id`, `tenant_id`, `patient_key` (token), `patient_identity_ref_id` (nullable), `created_at`, `last_updated_at`
- **Uniqueness**: (`tenant_id`, `patient_key`) unique

#### 13.2.10 `patient_snapshot`
Display-only patient fields shown in the Mini; versioned.
- **PK**: `patient_snapshot_id`
- **FK**: `patient_context_id` → `patient_context.patient_context_id`
- Columns: `patient_snapshot_id`, `patient_context_id`, `snapshot_version`, `display_name` (nullable), `id_label` (nullable), `id_masked` (nullable), `dob` (nullable), `created_at`

#### 13.2.11 `system_response`
A system-emitted assessment for a patient context.
- **PK**: `system_response_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK**: `patient_context_id` → `patient_context.patient_context_id`
- Columns: `system_response_id`, `tenant_id`, `patient_context_id`, `surface_type`, `computed_at`, `proceed_indicator`, `execution_mode`, `tasking_summary`, `rationale` (nullable), `correlation_id` (nullable)
- **Index**: (`tenant_id`, `patient_context_id`, `computed_at` desc)

#### 13.2.12 `mini_submission`
Mini-specific acknowledgement via override submission.
- **PK**: `mini_submission_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK**: `patient_context_id` → `patient_context.patient_context_id`
- **FK**: `system_response_id` → `system_response.system_response_id`
- **FK**: `user_id` → `app_user.user_id`
- **FK (optional)**: `invocation_id` → `invocation.invocation_id`
- Columns: `mini_submission_id`, `tenant_id`, `patient_context_id`, `system_response_id`, `user_id`, `invocation_id` (nullable), `submitted_at`, `override_proceed` (nullable), `override_tasking` (nullable), `note_text`
- **Constraint**: at least one of `override_proceed` or `override_tasking` is non-null
- **Constraint**: `note_text` required (non-empty)

#### 13.2.13 `assignment`
Offline pickup / inbox item.
- **PK**: `assignment_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK**: `patient_context_id` → `patient_context.patient_context_id`
- **FK (optional)**: `assigned_to_user_id` → `app_user.user_id`
- **FK (optional)**: `assigned_to_role_id` → `role.role_id`
- Columns: `assignment_id`, `tenant_id`, `patient_context_id`, `reason_code`, `assigned_to_user_id` (nullable), `assigned_to_role_id` (nullable), `status`, `created_at`, `resolved_at` (nullable)

#### 13.2.14 `event_log`
Append-only audit ledger (PHI-safe payloads).
- **PK**: `event_id`
- **FK**: `tenant_id` → `tenant.tenant_id`
- **FK (optional)**: `patient_context_id` → `patient_context.patient_context_id`
- **FK (optional)**: `invocation_id` → `invocation.invocation_id`
- **FK (optional)**: `actor_user_id` → `app_user.user_id`
- Columns: `event_id`, `tenant_id`, `event_type`, `patient_context_id` (nullable), `invocation_id` (nullable), `actor_user_id` (nullable), `payload_json` (nullable), `created_at`, `correlation_id` (nullable)

---

### 13.3 Firestore projections (documents)

> Firestore holds **subscription-friendly current state**, not the system of record.

#### 13.3.1 Patient State Projection
- **Document key**: `tenants/{tenant_id}/patient_state/{patient_key}`
- Fields (denormalized):
  - `patient_key`
  - `snapshot`: { `display_name?`, `id_label?`, `id_masked?`, `dob?`, `snapshot_version`, `updated_at` }
  - `latest_system_response`: { `system_response_id`, `computed_at`, `proceed_indicator`, `execution_mode`, `tasking_summary`, `rationale?` }
  - `last_mini_submission`: { `mini_submission_id`, `submitted_at`, `user_id` }
  - `flags`: { `needs_ack?`, `open_assignment_count?` }
  - `updated_at`

#### 13.3.2 User Inbox Projection
- **Document key**: `tenants/{tenant_id}/user_inbox/{user_id}`
- Fields:
  - `open_assignments`: array of { `assignment_id`, `patient_key`, `reason_code`, `created_at`, `status` }
  - `updated_at`

#### 13.3.3 Invocation Presence (optional)
- **Document key**: `tenants/{tenant_id}/invocation_presence/{invocation_id}`
- Fields:
  - `user_id`, `application_id`, `page_signature`, `surface_type`
  - `status`, `last_seen_at`

---

### 13.4 PostgreSQL vs Firestore responsibilities (summary)
- **PostgreSQL**: authoritative history, audit, relational integrity (responses, submissions, assignments, event log)
- **Firestore**: fast, realtime UI subscriptions (patient state + user inbox)

---

## Status
This PRD version is **LOCKED** and intended as the canonical Phase 1 reference, including the Mini front‑end data model for Patient contexts. Edits should be made via controlled revision.

