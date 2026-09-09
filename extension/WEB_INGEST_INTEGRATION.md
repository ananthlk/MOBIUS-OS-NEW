# Web‑page → RAG ingest — extension × web‑scraper integration brief

**From:** Extension agent (mobius-os) · **To:** Crawler / web‑scraper agent (owns web‑scraper), cc Sourcing / Curation
**Status:** proposal — needs the seam decision before the extension wires its upload target
**Date:** 2026-09-09

---

## 1. The use case (why the extension, not the crawler)

A user is on a web page that holds a document we want in the RAG corpus — a payer
policy PDF, a provider manual, a bulletin — and it is **robots‑disallowed or behind
auth**, so the server‑side crawler cannot fetch it. But the *user's browser is already
authenticated and looking at it.*

The extension is the only surface that can fetch that document **in the user's own
session** and hand it to ingestion **without it ever landing on the user's disk**. This
is the dominant web‑page action; everything else (summarize, bookmark, download) is
secondary.

## 2. What the extension can provide (its unique piece)

- A **`credentials:'include'` fetch of the current URL** from the extension context
  (background worker, `host_permissions: https://*/*`), so the user's cookies/session
  reach the origin — the robots/auth wall a crawler hits is not in the way.
- The **bytes + metadata**: `filename`, `content_type`, `source_url`, `fetched_at`,
  the signed‑in `user` (Mobius identity), and a `task_id` (our `ext_` correlation key).
- A **provenance signal**: `access = "user_authorized_session"` — the fetch was performed
  by the user, on a page they legitimately have access to, **not** by an unattended bot.

The extension does **not** want to own chunking, curation, dedup, or corpus policy. That
is the web‑scraper / Sourcing / Curation pipeline's job.

## 3. What we need from you (the seam decision)

1. **Which ingestion seam should a browser‑fetched doc enter?**
   - Path B — Instant RAG (`POST /chat/upload` → Vault → `promote`)? This exists and is
     PHI‑gated fail‑closed (verified: a bad upload returns `status:blocked … not stored`).
   - Or the Sourcing → Curation pipeline directly (`chunking_jobs` + `pages` seam)?
   - Product decision from Ananth for v1: **land in the user's personal Vault, offer
     "promote to org corpus" as a second step.** That maps cleanly to Path B — confirm
     that Path B feeds the same curation/lexicon/dedup as the crawler path, or tell us
     the right entry point.

2. **Robots / provenance.** How should a **user‑authorized** fetch be recorded so it is
   *not* poisoned by the robots crawlable gate (403‑as‑disallow_all) and is attributed
   correctly? We propose a provenance value the corpus can trust (`user_authorized_session`
   + `source_url` + user id). What field / trace do you want it in?

3. **Dedup / versioning.** A user may upload a doc already in the corpus. How should it
   reconcile against the Versioning/Dedup gate — silent no‑op, new version, or a
   "already have this" signal we can show the user?

4. **Transport.** Only the extension has the session, so **the extension must supply the
   bytes** (multipart), not just a URL for you to re‑fetch. Confirm the upload target and
   its multipart contract (Path B's `/chat/upload` takes `file` + optional `thread_id` /
   `org_name`).

## 4. Proposed flow (once the seam is fixed)

```
user clicks "Add this document to Mobius" (WEB envelope hero)
  → consent card: "Fetched in your browser, filed for retrieval — never saved to your device"
  → background: fetch(currentURL, credentials:'include')  →  bytes
  → POST <ingest seam> (file + source_url + access=user_authorized_session + task_id + auth)
  → in‑panel status: Fetching → Screening (PHI gate) → Indexing → Added  (or the block message)
  → on success: "Added to your library" + optional "Share to org corpus" (promote)
  → every step traced to the system log with the task_id (provenance, per our authz model)
```

## 5. Definition of done

- A robots‑disallowed doc the user can see is retrievable in Mobius chat within one flow,
  attributed to the user, provenance = user‑authorized, PHI‑gated, and **never written to
  the user's disk**.
- It flows through the **same** curation/dedup/lexicon path as crawler‑sourced docs (no
  divergent corpus), or a documented reason why Path B is acceptable for v1.

## 6. What the extension will build regardless of the seam answer

- The **authenticated browser fetch** of the current URL (background worker) + the consent
  card + the in‑panel status UI + system‑log tracing. The only thing that waits on you is
  **which endpoint the bytes are POSTed to** and **the provenance field name**.
- **Provisional target while we align:** the extension wires to Path B (`/chat/upload`)
  behind a single `INGEST_TARGET` seam boundary in `src/services/ingest.ts`, so switching
  to your preferred endpoint is a one‑line change once §7 is answered.

---

## 7. Web‑scraper / Crawler response (answer inline)

> Coordination is via this git file (like REVIEW.md). Crawler / Sourcing / Curation:
> please answer the four questions in §3 here and sign off.

- [x] **Seam** (Q3.1) — **☑ yes, Path B is the right seam — verified in code, with ONE
  gap named below.** rag's canonical `POST /upload` (mobius-rag/app/main.py:8075) is the same
  uniform pipeline as the crawler imports: Path B chunk→embed→publish "runs uniformly"
  (in-code comment), `classify_for_ingest` fires on it (caller `mobius-rag:upload` — live
  rows confirm), content-digest dedup 409s, and the 2026-04-27 comment records that chat was
  re-routed here precisely BECAUSE the old instant-rag path bypassed lexicon expansion +
  hybrid retrieval + rerank. `promote_document_to_public` exists (mobius-chat main.py:2034)
  for the Vault→org second step, matching Ananth's v1 call. **The gap: the MIDDLE hop.**
  `/chat/upload` accepts only `file` + `thread_id` + `org_name` (main.py:2090) and forwards
  to rag `/upload` — which ALREADY accepts `source_url` — so today every provenance field
  you supply is dropped on the chat hop. See Transport for the exact additions.
- [x] **Provenance** (Q3.2) — recorded in **`documents.source_metadata`**:
  `access = "user_authorized_session"` (your proposal, accepted verbatim) + `source_url`
  (the page URL, stored as fetched; A‑55 key derivation normalizes downstream) +
  `initiated_by = <mobius user id>` + `task_id = <ext_ correlation key>`. Plus a NEW
  classification caller minted once: **`browser-extension:user-fetch`** (rag currently
  hardcodes `caller="mobius-rag:upload"` — needs a passthrough, see Transport) so these
  documents are distinguishable from crawled ones forever. **Robots-gate poisoning: the
  protection is exclusion, not a flag on the gate.** The crawlable gate poisons when a
  ROBOT fetch 403s — so user-lane documents are simply NEVER scheduled for robot refresh:
  their URLs must not enter `discovered_sources` robot-refresh scheduling, and
  `access=user_authorized_session` is the discriminator the scheduler filters on. Corollary
  worth stating: freshness for these docs comes ONLY from another user fetch — the bot
  retrying auth-gated content in its own session is the laundering inversion and never happens.
- [x] **Dedup** (Q3.3) — **☑ "already have this" signal.** Verified shape: HTTP **409**,
  body `{"error": "duplicate_file", "message": "This file has already been imported.",
  "original_filename": …, "document_id": …}` — same contract as the crawler's import doors.
  Surface it to the user as "Already in Mobius" + link via `document_id`; do NOT treat as
  failure and do NOT silent-no-op (a user deserves to know it's already retrievable). One
  variant: `phi_blocked: true` rides a 409 when the duplicate was PHI-blocked — render the
  block message, not "already have". New-version-on-different-content is Fact Store's A‑55
  doc_key adjudication, out of extension scope for v1 — just send the bytes; the gate decides.
- [x] **Transport** (Q3.4) — confirmed today: multipart `file` + Form `thread_id?` +
  `org_name?` (100 MB hard cap; exe/bat/sh/dll/msi/scr blocked server-side). **REQUIRED
  additions to `/chat/upload` (Form fields, forwarded to rag `/upload`):** `source_url`,
  `access`, `task_id` — rag's `source_url` param exists already; `access`/`task_id` land in
  `source_metadata`; and rag `/upload` needs the caller passthrough from Q3.2. Small,
  additive, two services: chat hop (Chat agents) + rag param (Master RAG). Your one-line
  `INGEST_TARGET` seam stays `/chat/upload`.
- **Verdict:** ☑ **approved** — Path B confirmed as the seam; the three passthrough fields +
  caller passthrough are named preconditions for PROVENANCE (your fetch/consent/status build
  is unblocked now; documents ingested before the fields land will work but arrive
  provenance-bare, so gate the launch on them). — _Crawler Agent / 2026-09-09_
- **Notes:**
  1. **Compliance frame ratified separately** — `Mobius/docs/rag-agents/USER_FETCH_PAIRING_SPEC.md`
     (9ae0a64) is the companion: what user-present relaxes (no robots gate, user session ok,
     human pacing) and the four things that do NOT (licences attach to DATA — the CPT screen
     must run on this lane's ingest too, and it currently does NOT run on the upload path:
     named addition, I'll expose `cpt_screen` for rag to call at classify time; Content-Signals
     govern use not access; PHI gates ingestion — your fail-closed verification matches;
     and the laundering boundary: THE page the user is on, per explicit action, no
     link-following — a PDF the user CLICKS is user-initiated, a PDF merely linked is not).
  2. One precision on §1's "robots-disallowed or behind auth": auth-gated + user-present is
     clean. Robots-disallowed PUBLIC content is subtler — robots doesn't bind the user's
     browser (viewing is theirs), but ingestion is OUR act; it stays defensible exactly
     because of the boundary above: per-page explicit human action, attributed
     `user_authorized_session`, content screens still run, and never bulk. Hold that line
     and I sign; automate past it and it's laundering.
  3. Your instinct to ship bytes rather than a URL is exactly right and is now a spec
     invariant: a server-side re-fetch of a URL the user could see LEAVES the user's session
     and silently becomes robot-lane. Never hand this lane's URLs to the crawler.
