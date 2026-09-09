# Technical review request — Extension Phase 2 (+ compliance)

**From:** Extension work (mobius-os) · 2026-09-09
**To:** Technical Review Agent + Tech Review Architect (independent verify)
**Asking for:** review + blessing to proceed (2.4/2.5) and to harden the PHI path.

## Scope under review

Phase 2 rebuild of the extension side panel + the PHI-authorization audit trail.
Commits `0e47bb7 … d5b3c42` on `main` (MOBIUS-OS-NEW).

## The packet (read these)

- `PHASE2_SPEC.md` — locked product spec (the target).
- `src/types/sidebar.ts` — schema of record (SCHEMA_VERSION, PERSISTED_KEYS).
- `ARCHITECTURE.md` + `ARCHITECTURE.schematic.html` — module map (interactive,
  click-to-drill-down) + persistence flags. **Kept current** with each module.
- `backend/docs/PHI_AUTHORIZATION_LOG_CONTRACT.md` — the cross-team contract.

## What was built (each harness-verified)

- **2.1** Do/Save body: context strip · Do (promoted action) · Save · Suggested/
  Preferred drawer.
- **2.2** Recommendation banner (care-readiness folded in), permanent panel slot.
- **2.3** PHI acknowledgement toggle (off=ask per read, on=attested→no prompt) ·
  consent grants (decay) · shared consent-aware `beginPageCapture`.
- **Compliance**: `task_id` per invocation · `authorization_log` correlation
  table (POST /api/v1/authorizations) · masked, URL-hashed, attributed.
- **System log**: hidden action trace at the bottom.

## Verification evidence (what I actually ran)

- 2-mode toggle: two full laps stable.
- Sign-in via sidebar → content sidebar.
- PHI toggle: OFF asks; ON → no prompt, attaches directly; grant persists.
- Authorization round-trip: extension → POST → DB row; **URL hashed, 0 raw-token
  leaks**, masked labels, attributed to user.
- System log: 5 actions traced in order with task_ids.

## The bar — what I want verified / blessed

1. **PHI-safety of the audit path.** Confirm `authorization_log` can never hold
   raw URL/text (host + `origin_url_sha256` + masked labels only). Independent check.
2. **Fail-closed decision (needs a ruling).** PHI acknowledgement + the attestation
   forward are best-effort today. Should the toggle be **fail-closed** — refuse to
   grant if the compliance write fails? Recommended for real PHI.
3. **The two ◆ persistence surfaces** (Preferred pins, Consent grants) are in
   `chrome.storage.local` — should migrate to mobius-user. Bless the target.
4. **create_all / no-alembic** on the os-backend dev DB (no `alembic_version`
   table). The `authorization_log` table is create_all-managed. Is that acceptable,
   or should the backend adopt alembic properly? (Migration drift risk.)
5. **`system_context` blocker** (separate thread): the empty email-reply is blocked
   on the chat PHI gate covering `system_context` — cross-team with chat/PHI.

## Coordination note

Could not dispatch to the tech/PHI sessions live (SendMessage unavailable this
session). Please pick this up on Tech Day, or Ananth can relay. For an automated
first pass, `/code-review ultra` over this branch is available.
