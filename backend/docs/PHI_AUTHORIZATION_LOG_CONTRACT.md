# PHI authorization log — integration contract (proposal)

**From:** Extension work (mobius-os) · 2026-09-09
**To:** PHI classifier agent (`mobius-skills/phi-classifier`) + DB seat (owns `compliance.hipaa_analysis_log`)
**Status:** extension + os-backend side BUILT; PHI-agent side PROPOSED (this doc)

## Problem

Every PHI authorization a user makes in the extension — turning the PHI
acknowledgement toggle on/off, accepting a per-read consent card, overriding a
server PHI block — must be **auditable with provenance**: who, what, which
site, which invocation. Today the classifier records *classification* checks
(`phi_classification_audit`), not *user authorizations*, and there is no id
tying an authorization to the invocation that produced it.

## Design — task id + two logs, one key

A single **`task_id`** (minted client-side, prefix `ext_`) is the correlation
key. Two records are written under it:

1. **Correlation record — mobius-os `authorization_log`** (BUILT, ours).
   The provenance source of truth. Owns extension-specific context.
2. **Attestation record — `compliance.hipaa_analysis_log`** (PROPOSED, PHI/DB).
   The authoritative compliance record, keyed by the same `task_id`.

They join on `task_id`.

## Flow

```
extension  ──POST /api/v1/authorizations──▶  mobius-os backend
  { task_id, action, surface, origin_host,        │  writes authorization_log
    origin_url, phi_present, phi_labels[],         │  (hashes origin_url, keeps host)
    chat_correlation_id? }                         │
                                                   └──POST (proposed)──▶ phi-classifier
                                                        /authorization-log
                                                        → writes compliance.hipaa_analysis_log
                                                        → returns { audit_ref }
                                                   ◀── audit_ref stored on our row
```

## `action` enum

`phi_ack_on` · `phi_ack_off` · `read_ack` · `read_auto` · `override_send` · `site_grant`

## What the PHI agent needs to add (the proposed endpoint)

`POST /authorization-log`  (or fold into an existing compliance writer)

```jsonc
// request (server-to-server from mobius-os; never from the browser)
{
  "task_id": "ext_…",              // correlation key
  "gate_source": "mobius_os_extension",
  "user_id": "…", "org": "…",       // provenance
  "action": "phi_ack_on",
  "phi_present": true,
  "phi_labels": ["MRN","Date of Birth"],   // MASKED labels only — never raw
  "origin_host": "mail.google.com",
  "origin_url_sha256": "…",          // hashed; raw URL never sent
  "occurred_at": "…"
}
→ 200 { "audit_ref": "…" }           // id of the hipaa_analysis_log row
```

**Requirements (align with the existing HIPAA-log discipline):**
- Append-only, fail-closed (the log's stated posture).
- PHI-safe by construction — masked labels + hashes only; reject if raw text/URL appears.
- Idempotent on `(task_id, action)`.

## Guarantees already met on our side

- The browser sends host + full URL; **the os-backend hashes the URL** and stores
  only the host + `origin_url_sha256`. Raw URL never persists.
- `phi_labels` are the classifier's own masked labels — never raw identifiers.
- The client call is best-effort/non-blocking; the os-backend write is the
  durable step. (A future hardening: make PHI acknowledgement *fail-closed* on
  the attestation — block the toggle if the compliance write fails.)

## Open questions for the PHI/DB seats

1. New `/authorization-log` endpoint, or extend `/message-check` with an
   `event_type` so authorizations and classifications share one writer?
2. Should PHI acknowledgement be **fail-closed** — refuse to grant if the
   attestation can't be written? (Recommended for real PHI.)
3. Confirm `compliance.hipaa_analysis_log` columns can carry `task_id` +
   `gate_source='mobius_os_extension'` + `origin_url_sha256`.

*Coordination note: filed as a doc because SendMessage to the PHI agent was
unavailable this session. Please review + reply with the endpoint shape.*
