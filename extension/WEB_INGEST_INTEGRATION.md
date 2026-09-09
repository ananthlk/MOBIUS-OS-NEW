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

- [ ] **Seam** (Q3.1) — Path B (`/chat/upload` → Vault → promote) feeds the same
  curation/dedup/lexicon as the crawler path? ☐ yes  ☐ no → use: `__________`
- [ ] **Provenance** (Q3.2) — user‑authorized fetch recorded as: field `__________`,
  value `__________` (proposed: `access = "user_authorized_session"` + `source_url` + user id)
- [ ] **Dedup** (Q3.3) — on a duplicate upload the extension should expect: ☐ silent no‑op
  ☐ new version ☐ "already have this" signal (shape: `__________`)
- [ ] **Transport** (Q3.4) — confirm multipart contract: `file` + `__________`
- **Verdict:** ☐ approved  ☐ changes requested — _agent / date_
- **Notes:**
