## Mobius Mini + Sidecar (Phase 1) — Relationship Map (Visual)

- **PRD**: `PRDs/mobius_mini_sidecar_phase_1_prd.md`
- **Companion mapping**: `PRDs/mobius_mini_sidecar_phase_1_agent_map.md`

### System directory (agents vs modules)

```mermaid
flowchart TD
  %% External actors
  HostApp[HostApp_ThirdPartyApp]
  User[User]

  %% Decision agents
  RecordDetectionAgent[RecordDetectionAgent]
  ProceedDecisionAgent[ProceedDecisionAgent]
  ExecutionModeDecisionAgent[ExecutionModeDecisionAgent]
  TaskingDecisionAgent[TaskingDecisionAgent]
  PolicyDecisionAgent[PolicyDecisionAgent]
  OutcomeComputationAgent[OutcomeComputationAgent]
  AssignmentDecisionAgent[AssignmentDecisionAgent]

  %% Modules/services
  UIStripModule[UIStripAgent_Module]
  MiniSurfaceModule[MiniSurfaceModule]
  SidecarSurfaceModule[SidecarSurfaceModule]
  MiniAPI[MiniAPI_/api_v1_mini]
  SidecarAPI[SidecarAPI_/api_v1_sidecar]
  SharedCore[SharedPatientStateCore]
  PatientDataModule[PatientDataAgent_Module]
  BackendAPI[BackendAPIAndPersistenceModule]
  RealtimeProjection[RealtimeProjectionModule]
  EventLogAudit[EventLogAuditModule]
  SecurityCompliance[SecurityComplianceModule]

  %% Data stores
  Postgres[(PostgreSQL_SystemOfRecord)]
  Firestore[(Firestore_Projections)]

  %% UI surfaces
  Mini[Mini_UI]
  Sidecar[Sidecar_UI]

  %% Core domain concepts (as data)
  PatientKey[PatientKey_Tokenized]
  PatientContext[PatientContext]
  PatientSnapshot[PatientSnapshot_DisplayOnly]
  SystemResponse[SystemResponse_Latest]
  MiniSubmission[MiniSubmission_Acknowledgement]
  EventLog[EventLog_AppendOnly]
  Outcomes[DerivedOutcomes]
  Assignments[Assignments_OfflinePickup]
  UserInbox[UserInbox_Projection]

  %% Detection + policy gating
  HostApp -->|"context_signals"| RecordDetectionAgent
  PolicyDecisionAgent -->|"allowed_sources_showHide_uiVariants"| RecordDetectionAgent
  RecordDetectionAgent -->|"patient_key"| PatientKey

  %% Patient data
  PatientDataModule -->|"seed_snapshot_and_directory"| PatientSnapshot
  PatientKey --> SharedCore
  SharedCore --> BackendAPI
  BackendAPI -->|"upsert_or_load"| PatientContext
  BackendAPI -->|"load_display_snapshot"| PatientSnapshot

  %% System response decisioning
  PatientContext --> ProceedDecisionAgent
  PatientContext --> ExecutionModeDecisionAgent
  PatientContext --> TaskingDecisionAgent
  PolicyDecisionAgent -->|"policy_rules"| ProceedDecisionAgent
  PolicyDecisionAgent -->|"policy_rules"| ExecutionModeDecisionAgent
  PolicyDecisionAgent -->|"policy_rules"| TaskingDecisionAgent
  ProceedDecisionAgent --> SystemResponse
  ExecutionModeDecisionAgent --> SystemResponse
  TaskingDecisionAgent --> SystemResponse

  %% Persistence + audit (authoritative)
  SharedCore -->|"write_authoritative"| Postgres
  SharedCore -->|"append_events"| EventLogAudit
  SecurityCompliance -->|"PHI_safe_payloads"| EventLogAudit
  EventLogAudit --> EventLog
  EventLogAudit --> Postgres

  %% Realtime projection (denormalized)
  Postgres -->|"internal_events"| RealtimeProjection
  RealtimeProjection -->|"update_projections"| Firestore
  Firestore -->|"patient_state_doc"| SystemResponse
  Firestore -->|"patient_state_doc"| PatientSnapshot
  Firestore -->|"user_inbox_doc"| UserInbox

  %% UI consumption (separate surface paths, shared state)
  UIStripModule --> MiniSurfaceModule
  UIStripModule --> SidecarSurfaceModule
  MiniSurfaceModule --> Mini
  SidecarSurfaceModule --> Sidecar

  Mini -->|"call"| MiniAPI
  Sidecar -->|"call"| SidecarAPI
  MiniAPI -->|"delegate"| SharedCore
  SidecarAPI -->|"delegate"| SharedCore

  Mini -->|"subscribe"| Firestore
  Sidecar -->|"subscribe"| Firestore
  Firestore -->|"render"| Mini
  Firestore -->|"render"| Sidecar

  %% Acknowledgement (Send)
  User -->|"Send"| Mini
  User -->|"Send"| Sidecar
  Mini -->|"submit_ack"| MiniAPI
  Sidecar -->|"submit_ack"| SidecarAPI
  SharedCore -->|"persist_submission"| MiniSubmission
  SharedCore -->|"write"| Postgres
  EventLogAudit -->|"User.Acknowledged"| EventLog

  %% Outcomes + offline continuation
  EventLog --> OutcomeComputationAgent
  OutcomeComputationAgent --> Outcomes
  Outcomes --> AssignmentDecisionAgent
  PolicyDecisionAgent -->|"notification_assignment_rules"| AssignmentDecisionAgent
  AssignmentDecisionAgent --> Assignments
  BackendAPI -->|"persist_assignment"| Postgres
  RealtimeProjection -->|"project_inbox"| Firestore
  Firestore --> UserInbox
  UserInbox -->|"render"| Sidecar
```

### How to read this
- **Decision agents** produce computed decisions: `patient_key`, proceed, mode, tasking, outcomes, assignments.
- **Modules** provide execution: UI rendering, API/persistence, event log, realtime projections, PHI-safe enforcement.
- **Mini + Sidecar** use **separate surface paths** (`/api/v1/mini/*` and `/api/v1/sidecar/*`) that delegate to the same `SharedPatientStateCore`, so they remain two views over the same underlying patient state (authoritative in PostgreSQL; projected in Firestore; audited via append-only event log).

