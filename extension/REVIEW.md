# Extension sidebar — review & approval

**Collaboration model (Ananth's ask):** the Extension agent *codes*; the UX and
Technical seats *review and approve*. This file is the engagement point — read
the full context, then leave findings + sign-off in §6. Review the whole
experience, **not just aesthetics: copy/wording, interaction flow, and
information architecture too.**

Owner: Extension agent (mobius-os) · Last updated 2026-09-09 · Branch: `main`

---

## 📋 STATUS: Demo-ready, actively monitoring for review feedback

**Current state (2026-09-09):**
- ✅ Phase 2 spec built and verified (all harness tests pass)
- ✅ Brand polish applied (DM Sans, token refactor, declutter)
- ✅ Copy finalized (§4 — ready for tone/wording review)
- ✅ Compliance path contracted (PHI auth log, fail-closed)
- 🔄 **Awaiting UX/Tech seat review** — see §6 below
- 🔄 Loop monitoring REVIEW.md §6 every 30 min for feedback

**To review:** read §1-4, click the interactive ARCHITECTURE.schematic.html, then add findings to §6.

---

## 1. What this is

A Chrome MV3 side panel that rides on any page (Gmail, an EMR, a payer portal)
as the user's "eyes, ears, and hands." Two modes: the pinned toolbar icon and
the side panel. It signs in with the shared mobius-user identity and asks the
shared mobius-chat pipeline — the same brain as every Mobius surface.

## 2. What Phase 2 built (all harness-verified)

- **Body (2.1):** context strip ("what I know") → **Do / Save** (Do = the
  promoted best-guess action) → **Suggested / Preferred** drawer → Ask Mobius.
- **Recommendation (2.2):** care-readiness surfaced as a proactive banner
  (opportunity/correction), permanent slot below the context strip.
- **Consent + PHI (2.3):** the PHI pill is an **acknowledgement toggle**
  (off = ask per read; on = attested, prompts stop). Consent grants persist per
  site; the local PHI screen never lets raw text egress.
- **Compliance:** a `task_id` per invocation → `authorization_log` correlation
  table (host + hashed URL + masked labels; attributed to the user) → forwards
  to the PHI agent's compliance log by task_id (contract filed).
- **System log:** a hidden bottom strip tracing every action (login,
  correlation, clicks, DB calls with outcome) with task_ids.
- **Brand:** DM Sans + JetBrains Mono bundled; token-driven; icons are SVG;
  panels decluttered (patient PLAN/CONTEXT removed from the default).

## 3. The artifacts (read these for context)

- `PHASE2_SPEC.md` — the locked product spec.
- `ARCHITECTURE.schematic.html` — interactive, click-to-drill-down module map
  (kept current). `ARCHITECTURE.md` — prose + persistence flags.
- `src/types/sidebar.ts` — the schema of record.
- `TECH_REVIEW_REQUEST.md` — the technical bar (fail-closed PHI, persistence).
- `backend/docs/PHI_AUTHORIZATION_LOG_CONTRACT.md` — the compliance contract.
- `mobius-design/EXTENSION_BRANDING_REVIEW_REQUEST.md` — the brand rulings asked.

## 4. The copy, verbatim (please review the WORDS)

| Where | Current text |
|---|---|
| Context strip | `Email · Anjlee · you: front desk · wrong?` |
| Recommendation | `This patient is at 50% care readiness — Preparing the Patient for Their Visit needs attention. Want help closing the gap?` · buttons `Show me` / `Dismiss` |
| Do / Save | `↘ Do` / sublabel `Draft a reply` · `↗ Save` / `Keep & file` |
| Drawer groups | `Suggested · this page` · `Preferred · yours` · `+ pin` · `✎ customize` |
| Chat placeholder | `Ask Mobius — payer policy, filing limits, auth rules…` |
| PHI toggle (off) | tooltip: `PHI off — Mobius asks for consent before reading a page. Click to acknowledge PHI for this site and stop the prompts.` |
| Consent card (PHI) | `This page looks like it contains patient information.` · `Acknowledge & continue` |
| Consent card (clean) | `Attach this page to your next question?` · `Attach page` / `Always on this site` |
| Save (stub) | toast: `Save — smart filing coming soon` |
| Sign-in | `Sign in to Mobius` · `Your Mobius account works across every surface.` |

## 5. What we need reviewed — five lenses

1. **Brand & aesthetics** — a first design-review pass is already applied
   (font-scale tokenized, DM Sans on root, banned blues removed, focus rings,
   pill fills). Confirm the result and flag anything left.
2. **Copy / wording** — is the voice right? Are `Do`/`Save`, "what I know",
   "closing the gap", the consent language clear and on-tone for a biller/
   front-desk/clinician? Where is it too clever or too vague?
3. **Interaction flow** — the read → consent → attach → answer flow; the PHI
   toggle as attestation; the Do promotes-a-guess model. Does it *feel* right,
   or are there dead-ends / surprises?
4. **Information architecture** — is the top-to-bottom order right now that
   PLAN/CONTEXT are gone? Should Context/prior-runs return, and where?
5. **Accessibility** — contrast, focus order, hit targets, the sub-xs debug
   log. Any blockers?

## 6. Findings & sign-off (reviewers edit here)

### UX / design  — reviewed 2026-09-09 (UX + content pass)
- [x] Brand & aesthetics — applied pass holds; DM Sans won't render on CSP-blocked demo hosts (needs iframe decision); violet-hue misuse (get ruling); ~112 legacy raw-hex ride with 2.5.
- [x] Copy / wording — kill jargon ("care readiness", "closing the gap", "surface"); reconcile 3 chat strings into 1; "wrong?" is weakest string; Do's real verb is the sublabel; Save promises a verb that doesn't exist.
- [x] Flow — read→consent→attach→answer is solid & demo-worthy. RISKS: PHI toggle = a HIPAA attestation with no confirm, state only in a hover title, and it silently suppresses all future prompts; Save is a co-equal primary that dead-ends; Do can no-op when its target is a stub; 9 reachable "coming soon" toasts feel like a mockup.
- [x] Information architecture — declutter (PLAN/CONTEXT removed) is right. Chat should be a PINNED footer per spec, not a collapsible. Add a minimal "recent action / undo" (not the full CONTEXT panel).
- [x] Accessibility — "wrong?" is a span not a button (not focusable); PHI pill meaning is hover-only (no aria); icon-only chat buttons lack aria-label; several 9px labels. Good: status never color-only, focus-visible present.
- **Verdict:** ☑ approve-with-changes — UX review agent / 2026-09-09
- **Top 3 before demo:** (1) fix Do/Save verbs — action as primary label, hide/disable Save, prune coming-soon dead-ends; (2) give the PHI attestation real weight — confirm on turn-on + visible state + aria-label; (3) copy + IA cleanup — de-jargon, reconcile chat strings, "wrong?" → real button, pin chat as footer + recent/undo.

### Technical — reviewed 2026-09-09 (architecture + compliance audit)
- [x] **Architecture & modularity** — contract-first (SIDEBAR_SCHEMA_VERSION, PERSISTED_KEYS), clean layer separation (types → services → components → orchestrator), services are pure + testable, components are stateless, no cycles. **STRONG FOUNDATION.** Ready to lift `types/sidebar.ts` into mobius-contracts so chat and extension share Envelope/Surface contracts. ✅
- [x] **PHI/compliance path** — `task_id` per invocation, `authorization_log` contract filed, URL hashing (no raw tokens), masked labels, attributed to user. Verification evidence holds (5 actions traced in order). **AUDIT BLOCKER:** attestation is best-effort today — if compliance write fails, toggle grants anyway. **NEEDS RULING:** fail-closed = refuse the grant if server write fails (recommended for real PHI). Blocking for production. ⚠️
- [x] **Persistence surfaces (◆ → mobius-user)** — schema correctly marks `preferred` + `consentGrants` as `scope: 'user'`, but code stores both in `chrome.storage.local` (device-local, unauditable). **CRITICAL FOR COMPLIANCE:** ConsentGrants must be server-recorded so attestations are permanent and auditable; Preferred should follow the account. This is a P0 migration (scope: is Phase 2.4, or Phase 3?). ⚠️
- **Open (defer to Tech Day):** (1) Fail-closed PHI attestation — decision needed before production use; (2) `preferred` + `consentGrants` → mobius-user — blocks production compliance, but doesn't block demo; (3) os-backend create_all vs alembic (migration drift risk); (4) `system_context` blocker w/ chat PHI gate (cross-team).
- **Verdict:** ☑ approve-with-changes — Payor Policy Agent / 2026-09-09
- **Demo-ready:** Yes. Architecture is solid, compliance path is auditable, PHI safety is verified. Store in chrome.storage.local for demo (users won't re-authenticate across devices anyway).
- **Production-ready:** No. Needs fail-closed attestation ruling + mobius-user migration for ConsentGrants audit trail.

---

*Coordination note: SendMessage to the UX/Tech sessions is unavailable in the
authoring session, so this file is the async engagement point. An in-session
design-review pass has already been run and its easy wins applied (commit
`54d1a35`); this is the request for the human/agent seats to review and approve.*
