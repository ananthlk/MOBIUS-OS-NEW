/**
 * Ingest service — fetch the current page's document in the user's session and
 * file it into RAG, without it ever touching the user's disk.
 *
 * The fetch + upload happen in the BACKGROUND worker (extension context):
 *  · the fetch carries the user's cookies (host_permissions), reaching
 *    robots/auth-blocked docs a server crawler can't;
 *  · the bytes go straight to the ingest target as multipart — never to disk.
 *
 * Ingestion is PHI-gated and fail-closed on the server (Instant-RAG HIPAA
 * gate): a blocked upload returns status:"blocked" and is NOT stored.
 *
 * SEAM: INGEST_TARGET is provisional (Path B: /chat/upload → Vault → promote)
 * pending the Crawler/Sourcing sign-off in WEB_INGEST_INTEGRATION.md §7. When
 * they name the seam, this one constant (and promote's base) is the only
 * change here.
 */

import { CHAT_BASE_URL } from '../config';
import { apiFetch, getAuthService } from './auth';
import { trace } from './traceLog';

// --- SEAM (see WEB_INGEST_INTEGRATION.md §7) ---------------------------------
const INGEST_TARGET = `${CHAT_BASE_URL}/chat/upload`;
const promoteUrl = (documentId: string) =>
  `${CHAT_BASE_URL}/chat/documents/${encodeURIComponent(documentId)}/promote`;
// ----------------------------------------------------------------------------

export interface IngestResult {
  ok: boolean;
  /** true when the server PHI gate blocked ingestion (fail-closed). */
  blocked?: boolean;
  /**
   * When `blocked`, WHY — each drives a different result card:
   *  - `phi`           → a genuine PHI detection (gate found identifiers, which
   *                      may be masked). "Not stored — flagged for PHI", no retry.
   *  - `indeterminate` → the gate couldn't return a verdict (`gate:"indeterminate"`
   *                      / `blocked_indeterminate` — a transient LLM/infra
   *                      fail-closed). Content isn't implicated; a retry typically
   *                      lands. "Safety check didn't finish — try again" + retry.
   *  - `unconfigured`  → the safety service isn't configured server-side
   *                      (`blocked_unconfigured`). An admin problem, NOT PHI and
   *                      NOT retryable. "Safety service unavailable — contact admin".
   *  - `publish_failed`→ the gate ruled (often clean) but rag's publish failed
   *                      (`blocked_publish_failed` — a transient storage/pkey
   *                      collision). NOT a PHI finding; a retry typically lands.
   *                      "Couldn't finish saving — try again" + retry.
   * Contract (classifier owner): `phi` iff `gate === "phi"` — the ONE guaranteed
   * genuine-PHI signal. Every other block is non-PHI and defaults to a soft
   * "try again" card, NEVER the PHI card ("not indeterminate" ≠ "PHI"; a storage
   * failure is neither). Holds for any future block type.
   */
  blockReason?: 'phi' | 'indeterminate' | 'unconfigured' | 'publish_failed';
  /** true when the doc is already in the corpus (409 duplicate_file). */
  duplicate?: boolean;
  documentId?: string;
  filename?: string;
  bytes?: number;
  /** Raw server status (e.g. "stored" / "processing" / "blocked"). */
  status?: string;
  /** User-facing message (block reason or success note). */
  message?: string;
  /** Which stage failed, when ok is false. */
  stage?: 'fetch' | 'upload';
}

interface BgResponse {
  ok: boolean;
  status?: number;
  bytes?: number;
  contentType?: string;
  filename?: string;
  json?: {
    status?: string;
    blocked?: boolean;
    document_id?: string;
    message?: string;
    // 409 duplicate_file shape (Crawler §7): error + original_filename.
    error?: string;
    original_filename?: string;
    phi_blocked?: boolean;
    // Gate verdict: "phi" (genuine detection) vs "indeterminate" (timeout /
    // infra fail-closed). `action_taken` mirrors it ("blocked_indeterminate").
    gate?: string;
    action_taken?: string;
    hipaa_diagnostics?: {
      reason?: string;
      identifier_labels?: string[];
      gate?: string;
      action_taken?: string;
    };
  } | null;
  stage?: 'fetch' | 'upload';
  error?: string;
}

function sendBg(message: Record<string, unknown>): Promise<BgResponse> {
  return new Promise((resolve) => {
    try {
      chrome.runtime.sendMessage(message, (resp) => {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
          return;
        }
        resolve((resp as BgResponse) || { ok: false, error: 'no response' });
      });
    } catch (e) {
      resolve({ ok: false, error: String(e) });
    }
  });
}

/**
 * Fetch the current page's document (in-session) and file it for retrieval.
 * `taskId` correlates every step in the system log (provenance model).
 */
export async function ingestCurrentPage(opts: {
  url: string;
  taskId: string;
  threadId?: string;
}): Promise<IngestResult> {
  let token: string | undefined;
  try {
    token = (await getAuthService().getAccessToken()) || undefined;
  } catch {
    token = undefined;
  }

  trace('action', `fetching document in session — ${hostOf(opts.url)}`, opts.taskId);
  const resp = await sendBg({
    type: 'mobius:ingest:fetchUpload',
    url: opts.url,
    uploadUrl: INGEST_TARGET,
    token,
    taskId: opts.taskId,
    threadId: opts.threadId,
  });

  if (!resp.ok) {
    trace('error', `ingest ${resp.stage || ''} failed: ${resp.error || 'unknown'}`, opts.taskId);
    return {
      ok: false,
      stage: resp.stage,
      message:
        resp.stage === 'fetch'
          ? 'Could not fetch this page in your session.'
          : 'Could not upload to Mobius.',
    };
  }

  const j = resp.json || {};
  const documentId = j.document_id;

  // 409 duplicate_file — the doc is already in the corpus (Crawler §7). A
  // PHI-blocked duplicate rides the same 409 with phi_blocked:true → show the
  // block message, not "already have this".
  if (resp.status === 409 || j.error === 'duplicate_file') {
    if (j.phi_blocked) {
      trace('error', `ingest duplicate but PHI-blocked`, opts.taskId);
      return { ok: false, blocked: true, documentId, message: j.message || 'This document was blocked by the safety gate.' };
    }
    trace('net', `ingest duplicate — already in corpus · ${(documentId || '').slice(0, 8)}`, opts.taskId);
    return { ok: false, duplicate: true, documentId, message: 'This document is already in Mobius.' };
  }

  const blocked = j.blocked === true || j.status === 'blocked';
  if (blocked) {
    const blockReason = classifyBlock(j);
    trace(
      'error',
      `ingest blocked (${blockReason}) — ${j.hipaa_diagnostics?.reason || j.action_taken || j.gate || 'blocked'}`,
      opts.taskId
    );
    const fallbackMsg =
      blockReason === 'indeterminate'
        ? 'The safety check didn’t finish — nothing was stored. Try again in a moment.'
        : blockReason === 'unconfigured'
          ? 'The safety service isn’t available right now — nothing was stored. Contact your administrator.'
          : blockReason === 'publish_failed'
            ? 'Couldn’t finish saving this document — try again in a moment.'
            : 'This document couldn’t be verified for safety and was not stored.';
    return {
      ok: false,
      blocked: true,
      blockReason,
      documentId,
      status: j.status,
      message: j.message || fallbackMsg,
    };
  }

  trace('net', `ingest stored ✓ · ${resp.filename} · ${fmtBytes(resp.bytes)}`, opts.taskId);
  return {
    ok: true,
    documentId,
    filename: resp.filename,
    bytes: resp.bytes,
    status: j.status,
    message: j.message,
  };
}

/** Promote a personal-Vault upload into the shared org corpus. */
export async function promoteDocument(documentId: string, taskId: string): Promise<boolean> {
  try {
    const r = await apiFetch(promoteUrl(documentId), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
    const ok = r.ok;
    trace(ok ? 'net' : 'error', `promote to org corpus ${ok ? '✓' : 'failed'} · ${documentId.slice(0, 8)}`, taskId);
    return ok;
  } catch (e) {
    trace('error', `promote failed: ${String(e)}`, taskId);
    return false;
  }
}

/**
 * Why a fail-closed block happened, from the server's explicit verdict only.
 *
 * Deliberately conservative: anything not explicitly `indeterminate` or
 * `unconfigured` falls back to `phi` — the safe card. The PHI classifier masks
 * its evidence (recall-over-precision), so a genuine PHI block can carry empty
 * `identifier_labels`; we must never infer "just retry" from a thin finding set
 * and invite a retry of a truly-PHI doc. Only the server naming the reason
 * flips us off the PHI card.
 */
function classifyBlock(
  j: NonNullable<BgResponse['json']>
): 'phi' | 'indeterminate' | 'unconfigured' | 'publish_failed' {
  const gate = j.gate || j.hipaa_diagnostics?.gate;
  const action = j.action_taken || j.hipaa_diagnostics?.action_taken;
  // THE CONTRACT (per the PHI classifier owner): show the PHI card if and ONLY
  // if gate === "phi". That is the single guaranteed genuine-PHI signal
  // (gate === "phi" ⟺ phi_flag ⟺ PHI actually detected); a real detection is
  // NEVER emitted as any other gate value. Crucially, "not indeterminate" is
  // NOT "PHI" — a storage failure (blocked_publish_failed, which preserves the
  // real gate === "clean") is neither. So every non-"phi" block defaults to a
  // soft "couldn't finish — try again" card, never the alarming PHI card. This
  // stays correct for any future block type we don't yet name.
  if (gate === 'phi') return 'phi';
  if (action === 'blocked_unconfigured') return 'unconfigured';
  if (action === 'blocked_publish_failed') return 'publish_failed';
  // Explicit indeterminate, catch-all, or anything unknown → soft/retry.
  return 'indeterminate';
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url.slice(0, 40);
  }
}

function fmtBytes(n?: number): string {
  if (!n) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
