/**
 * Chat Service — asks the shared mobius-chat pipeline.
 *
 * No-PHI general assistant: sends ONLY the text the user typed. Never
 * attaches page-scraped, patient, or EMR context. mobius-chat's server-side
 * PHI gate is the backstop — a 422 phi_blocked response is surfaced to the
 * user as-is, with no override.
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
  onProgress?: (status: string) => void
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
        message,
        ...(threadId ? { thread_id: threadId } : {}),
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
