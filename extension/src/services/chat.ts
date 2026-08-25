/**
 * Chat Service — asks the shared mobius-chat pipeline.
 *
 * Consent-gated context model: by default only the typed question is sent.
 * Page content can be attached ONLY through the explicit read-page flow —
 * captured on user action, screened locally (services/phiScreen, zero
 * egress), and acknowledged before anything leaves the browser. Attached
 * content rides inside the message body so mobius-chat's server-side PHI
 * gate (the authoritative, fail-closed layer) scans it; a server block is
 * surfaced for a second explicit acknowledgement before any override.
 *
 * Transport: POST /chat enqueues and returns {correlation_id, thread_id};
 * GET /chat/response/{cid} is polled until status leaves processing/pending.
 * All requests go through the background worker's fetch proxy (see
 * apiFetch) because chat's CORS origin allowlist cannot include host pages.
 */

import { CHAT_BASE_URL } from '../config';
import { apiFetch, getAuthService } from './auth';

const THREAD_STORAGE_KEY = 'mobius.chat.threadId';
const POLL_INTERVAL_MS = 1500;
const POLL_TIMEOUT_MS = 180000; // chat answers can take a while on cold paths

export interface ChatAnswer {
  ok: boolean;
  /** Markdown answer text (direct_answer) when ok. */
  answer?: string;
  /** Number of cited sources, when provided. */
  sourceCount?: number;
  /** Human-readable error / block message when not ok. */
  error?: string;
  /** True when the PHI gate blocked the message. */
  phiBlocked?: boolean;
  /** Identifier labels from the server PHI gate when blocked. */
  phiLabels?: string[];
}

/** Page content the user explicitly captured and acknowledged for sharing. */
export interface PageContext {
  text: string;
  url: string;
  title: string;
  /** Source-type hint so the server can apply type-specific extraction
   *  (email vs EMR vs RCM vs generic web). Today it rides in the message
   *  header; when chat grows a gated system_context envelope, the same
   *  field moves there with no FE change. */
  sourceType: 'email' | 'emr' | 'rcm' | 'web';
}

/** Cheap client-side source-type hint from the hostname. */
export function classifyPageSource(hostname: string): PageContext['sourceType'] {
  const h = hostname.toLowerCase();
  if (/mail\.google\.com|outlook\.|mail\./.test(h)) return 'email';
  if (/mock-emr|epic|cerner|athena|qualifacts|carelogic|myavatar|credible/.test(h)) return 'emr';
  if (/availity|waystar|claim|billing|rcm|clearinghouse/.test(h)) return 'rcm';
  return 'web';
}

export interface AskOptions {
  /** Acknowledged page content to attach. Rides INSIDE the message body so
   *  the server PHI gate scans it — never in unscanned side-channels. */
  pageContext?: PageContext;
  /** Set after the user explicitly acknowledged a PHI warning. */
  phiOverride?: boolean;
}

function storageGet(key: string): Promise<string | null> {
  return new Promise((resolve) => {
    chrome.storage.local.get([key], (items) => {
      resolve((items?.[key] as string) || null);
    });
  });
}

function storageSet(key: string, value: string): Promise<void> {
  return new Promise((resolve) => {
    chrome.storage.local.set({ [key]: value }, () => resolve());
  });
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Ask mobius-chat a question. Reports progress ("Mobius is thinking…"
 * style lines from the pipeline's thinking log) via onProgress.
 */
export async function askMobius(
  message: string,
  onProgress?: (status: string) => void,
  opts: AskOptions = {}
): Promise<ChatAnswer> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  // Auth is optional on chat; attach the Mobius identity when present so
  // the turn is attributed to the signed-in user.
  try {
    const token = await getAuthService().getAccessToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  } catch {
    // Unauthenticated is fine.
  }

  // One rolling thread for the extension surface (deliberately NOT
  // patient-scoped — this assistant is not tied to the EMR).
  const threadId = await storageGet(THREAD_STORAGE_KEY);

  let post;
  try {
    post = await apiFetch(`${CHAT_BASE_URL}/chat`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message: opts.pageContext
          ? `${message}\n\n[Attached page (${opts.pageContext.sourceType}): ${opts.pageContext.title} — ${opts.pageContext.url}]\n${opts.pageContext.text}`
          : message,
        ...(threadId ? { thread_id: threadId } : {}),
        ...(opts.phiOverride ? { phi_override: true } : {}),
      }),
    });
  } catch (e) {
    return { ok: false, error: 'Could not reach Mobius chat' };
  }

  const postData = await post.json();
  if (post.status === 422 && postData?.detail?.phi_blocked) {
    return {
      ok: false,
      phiBlocked: true,
      phiLabels: Array.isArray(postData.detail.identifier_labels)
        ? postData.detail.identifier_labels
        : [],
      error:
        postData.detail.message ||
        'Message looks like it contains PHI — please rephrase without identifiers.',
    };
  }
  if (!post.ok || !postData?.correlation_id) {
    return { ok: false, error: 'Chat request was rejected' };
  }

  if (postData.thread_id) {
    await storageSet(THREAD_STORAGE_KEY, String(postData.thread_id));
  }

  const cid = String(postData.correlation_id);
  const deadline = Date.now() + POLL_TIMEOUT_MS;
  let lastStatus = '';

  while (Date.now() < deadline) {
    await sleep(POLL_INTERVAL_MS);
    let poll;
    try {
      poll = await apiFetch(`${CHAT_BASE_URL}/chat/response/${cid}`);
    } catch {
      continue; // transient — keep polling until the deadline
    }
    if (!poll.ok) continue;
    const data = await poll.json();
    const status = String(data?.status || '');

    if (status === 'completed') {
      return parseCompleted(data);
    }
    if (status === 'error' || status === 'failed') {
      return { ok: false, error: 'Mobius could not answer that one' };
    }
    // processing / pending — surface the latest thinking step
    const log = data?.thinking_log;
    const latest = Array.isArray(log) && log.length ? String(log[log.length - 1]) : '';
    if (latest && latest !== lastStatus) {
      lastStatus = latest;
      onProgress?.(latest);
    }
  }

  return { ok: false, error: 'Mobius is taking too long — try again in a moment' };
}

function parseCompleted(data: any): ChatAnswer {
  // message is a JSON-encoded card: {mode, direct_answer, sections, ...}
  let answer = '';
  try {
    const card = typeof data.message === 'string' ? JSON.parse(data.message) : data.message;
    answer = String(card?.direct_answer || '');
  } catch {
    answer = typeof data.message === 'string' ? data.message : '';
  }
  if (!answer) {
    return { ok: false, error: 'Mobius returned an empty answer' };
  }
  const sources = Array.isArray(data.sources) ? data.sources.length : undefined;
  return { ok: true, answer, sourceCount: sources };
}
