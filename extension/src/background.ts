/**
 * Background service worker for Mobius OS extension
 */

import { AUTH_BASE_URL, CHAT_BASE_URL, API_V1_URL } from './config';

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Mobius OS] Extension installed');

  // Seed allowed domains for testing (only if unset).
  // This keeps production behavior "allowlist-driven" while making initial dev testing easier.
  const ALLOWED_DOMAINS_KEY = 'mobius.allowedDomains';
  chrome.storage.local.get([ALLOWED_DOMAINS_KEY], (result) => {
    const existing = result[ALLOWED_DOMAINS_KEY];
    const current = Array.isArray(existing) ? (existing as string[]) : [];

    // Keep this list conservative; user can toggle sites in the popup.
    // Ensure entries exist even if the allowlist was already created.
    const defaults = [
      'localhost',
      '127.0.0.1',
      'example.com',
      'google.com',
      'www.google.com',
    ];

    const next = new Set(current.map((d) => String(d).toLowerCase()).filter(Boolean));
    for (const d of defaults) next.add(d);

    chrome.storage.local.set({ [ALLOWED_DOMAINS_KEY]: Array.from(next).sort() }, () => {
      console.log('[Mobius OS] Ensured allowlist entries for testing:', defaults);
    });
  });
});

// Keys that should persist across browser sessions (stored in local storage)
const PERSISTENT_KEYS = [
  'mobius.auth.refreshToken',
  'mobius.auth.userProfile',
];

/** Best-effort filename for a fetched document: last path segment, else a
 *  content-type-derived default. */
function filenameFromUrl(url: string, contentType: string): string {
  try {
    const path = new URL(url).pathname;
    const last = decodeURIComponent(path.split('/').filter(Boolean).pop() || '');
    if (last && /\.[a-z0-9]{2,5}$/i.test(last)) return last;
    const ext = contentType.includes('pdf')
      ? 'pdf'
      : contentType.includes('html')
        ? 'html'
        : contentType.includes('plain')
          ? 'txt'
          : 'bin';
    const base = (last || new URL(url).hostname.replace(/^www\./, '') || 'document').slice(0, 60);
    return `${base}.${ext}`;
  } catch {
    return 'document.bin';
  }
}

/**
 * Auth Storage Message Handler
 * Content scripts cannot access chrome.storage.session directly,
 * so we proxy storage operations through the background script.
 * 
 * Storage strategy:
 * - Refresh token + user profile → chrome.storage.local (persists across sessions)
 * - Access token + expiresAt → chrome.storage.session (cleared on browser close)
 */
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type) return false;

  // Clear the toolbar badge (sent by the content script when the panel opens).
  if (message.type === 'mobius:badge:clear') {
    void chrome.action.setBadgeText({ text: '' });
    sendResponse({ ok: true });
    return false;
  }

  // Proxy auth API calls to the shared mobius-user service. Content scripts
  // fetch under the host page's origin and get blocked by mobius-user's CORS
  // allowlist; the background worker fetches in the extension context, which
  // host_permissions exempts from CORS. Only the auth service origin is
  // allowed — this is not a general-purpose fetch proxy.
  if (message.type === 'mobius:auth:fetch') {
    const url = String(message.url || '');
    const allowed =
      url.startsWith(`${AUTH_BASE_URL}/`) || url.startsWith(`${CHAT_BASE_URL}/`);
    if (!allowed) {
      sendResponse({ ok: false, error: 'URL not allowed' });
      return false;
    }
    const init: RequestInit = { method: String(message.method || 'GET') };
    if (message.headers && typeof message.headers === 'object') {
      init.headers = message.headers as Record<string, string>;
    }
    if (typeof message.body === 'string') {
      init.body = message.body;
    }
    fetch(url, init)
      .then(async (r) => {
        const json = await r.json().catch(() => null);
        sendResponse({ ok: true, status: r.status, json });
      })
      .catch((error) => {
        console.error('[Mobius Background] Auth fetch error:', error);
        sendResponse({ ok: false, error: String(error) });
      });
    return true; // Keep channel open for async response
  }

  // Fetch a document in the user's authenticated session and stream it to the
  // ingest target — the extension's unique capability: the bytes come from the
  // page the user is on (cookies included via host_permissions), reaching
  // robots/auth-blocked docs a server crawler can't, and go straight to the
  // corpus WITHOUT ever touching the user's disk. See WEB_INGEST_INTEGRATION.md.
  if (message.type === 'mobius:ingest:fetchUpload') {
    const docUrl = String(message.url || '');
    const uploadUrl = String(message.uploadUrl || '');
    // The upload target is allowlisted (not a general proxy); the doc URL is
    // the page the user is viewing, supplied by our own content script.
    if (!uploadUrl.startsWith(`${CHAT_BASE_URL}/`)) {
      sendResponse({ ok: false, error: 'upload target not allowed' });
      return false;
    }
    if (!/^https?:\/\//i.test(docUrl)) {
      sendResponse({ ok: false, error: 'invalid document url' });
      return false;
    }
    (async () => {
      try {
        // 1) Fetch the document bytes in-session (cookies included).
        const fetchedAt = new Date().toISOString(); // client FETCH clock (two-clocks rule)
        const docResp = await fetch(docUrl, { credentials: 'include' });
        if (!docResp.ok) {
          sendResponse({ ok: false, stage: 'fetch', status: docResp.status, error: `fetch failed (${docResp.status})` });
          return;
        }
        const blob = await docResp.blob();
        const contentType = docResp.headers.get('Content-Type') || blob.type || 'application/octet-stream';
        const filename = String(message.filename || filenameFromUrl(docUrl, contentType));

        // Content-Signals that ride ONLY in response headers are invisible to
        // the server (it receives bytes, not our response), so forward the raw
        // header lines verbatim — rag-side is the single normalizer that merges
        // these with the origin's robots.txt signals (Crawler §2.6, TODO-A).
        const signalHeaders: string[] = [];
        for (const h of ['x-robots-tag', 'content-signal', 'content-usage', 'tdm-reservation', 'tdm-policy']) {
          const v = docResp.headers.get(h);
          if (v) signalHeaders.push(`${h}: ${v}`);
        }

        // 2) Multipart POST to the ingest target (extension context = CORS-exempt).
        const fd = new FormData();
        fd.append('file', blob, filename);
        if (message.threadId) fd.append('thread_id', String(message.threadId));
        if (message.orgName) fd.append('org_name', String(message.orgName));
        // Provenance (WEB_INGEST_INTEGRATION.md §7, Crawler-approved). These
        // Form fields are additive; the chat hop + rag param that forward them
        // into documents.source_metadata are Chat/Master-RAG's to land — until
        // then they're harmlessly ignored, so no rework when they ship.
        fd.append('source_url', docUrl);
        fd.append('access', 'user_authorized_session');
        fd.append('fetched_at', fetchedAt);
        if (message.taskId) fd.append('task_id', String(message.taskId));
        if (signalHeaders.length) fd.append('signal_headers', signalHeaders.join('\n'));

        const headers: Record<string, string> = {};
        if (message.token) headers['Authorization'] = `Bearer ${message.token}`;

        const up = await fetch(uploadUrl, { method: 'POST', headers, body: fd });
        const json = await up.json().catch(() => null);
        sendResponse({ ok: true, status: up.status, bytes: blob.size, contentType, filename, json });
      } catch (error) {
        console.error('[Mobius Background] Ingest fetch/upload error:', error);
        sendResponse({ ok: false, stage: 'upload', error: String(error) });
      }
    })();
    return true; // async
  }

  // Handle auth storage operations
  if (message.type === 'mobius:auth:getStorage') {
    const keys = message.keys as string[];
    
    // Split keys by storage type
    const sessionKeys = keys.filter(k => !PERSISTENT_KEYS.includes(k));
    const localKeys = keys.filter(k => PERSISTENT_KEYS.includes(k));
    
    // Fetch from both storages and merge
    Promise.all([
      sessionKeys.length > 0 ? chrome.storage.session.get(sessionKeys) : Promise.resolve({}),
      localKeys.length > 0 ? chrome.storage.local.get(localKeys) : Promise.resolve({}),
    ]).then(([sessionData, localData]) => {
      sendResponse({ ok: true, data: { ...sessionData, ...localData } });
    }).catch((error) => {
      console.error('[Mobius Background] Storage get error:', error);
      sendResponse({ ok: false, error: String(error) });
    });
    return true; // Keep channel open for async response
  }

  if (message.type === 'mobius:auth:setStorage') {
    const items = message.items as Record<string, unknown>;
    
    // Split items by storage type
    const sessionItems: Record<string, unknown> = {};
    const localItems: Record<string, unknown> = {};
    
    for (const [key, value] of Object.entries(items)) {
      if (PERSISTENT_KEYS.includes(key)) {
        localItems[key] = value;
      } else {
        sessionItems[key] = value;
      }
    }
    
    // Store in appropriate storage
    Promise.all([
      Object.keys(sessionItems).length > 0 ? chrome.storage.session.set(sessionItems) : Promise.resolve(),
      Object.keys(localItems).length > 0 ? chrome.storage.local.set(localItems) : Promise.resolve(),
    ]).then(() => {
      sendResponse({ ok: true });
    }).catch((error) => {
      console.error('[Mobius Background] Storage set error:', error);
      sendResponse({ ok: false, error: String(error) });
    });
    return true;
  }

  if (message.type === 'mobius:auth:clearStorage') {
    const keys = message.keys as string[] | undefined;
    
    if (keys) {
      // Clear specific keys from appropriate storage
      const sessionKeys = keys.filter(k => !PERSISTENT_KEYS.includes(k));
      const localKeys = keys.filter(k => PERSISTENT_KEYS.includes(k));
      
      Promise.all([
        sessionKeys.length > 0 ? chrome.storage.session.remove(sessionKeys) : Promise.resolve(),
        localKeys.length > 0 ? chrome.storage.local.remove(localKeys) : Promise.resolve(),
      ]).then(() => {
        sendResponse({ ok: true });
      }).catch((error) => {
        console.error('[Mobius Background] Storage clear error:', error);
        sendResponse({ ok: false, error: String(error) });
      });
    } else {
      // Clear all auth data from both storages
      Promise.all([
        chrome.storage.session.clear(),
        chrome.storage.local.remove(PERSISTENT_KEYS),
      ]).then(() => {
        sendResponse({ ok: true });
      }).catch((error) => {
        console.error('[Mobius Background] Storage clear error:', error);
        sendResponse({ ok: false, error: String(error) });
      });
    }
    return true;
  }

  return false;
});


// =============================================================================
// Toolbar icon: click toggles the panel on the active tab.
// (No default_popup in the manifest, so chrome.action.onClicked fires.)
// Clicking on a site that isn't allowlisted yet allowlists it first — the
// click is the explicit per-site opt-in gesture.
// =============================================================================

const ALLOWED_DOMAINS_KEY = 'mobius.allowedDomains';

async function ensureDomainAllowed(hostname: string): Promise<void> {
  const items = await chrome.storage.local.get([ALLOWED_DOMAINS_KEY]);
  const current: string[] = Array.isArray(items[ALLOWED_DOMAINS_KEY])
    ? (items[ALLOWED_DOMAINS_KEY] as string[])
    : [];
  const next = new Set(current.map((d) => String(d).toLowerCase()));
  if (!next.has(hostname)) {
    next.add(hostname);
    await chrome.storage.local.set({ [ALLOWED_DOMAINS_KEY]: Array.from(next).sort() });
  }
}

function sendToTab(tabId: number, message: unknown): Promise<boolean> {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, () => {
      resolve(!chrome.runtime.lastError);
    });
  });
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id || !tab.url) return;
  let hostname = '';
  try {
    hostname = new URL(tab.url).hostname.toLowerCase();
  } catch {
    return;
  }
  if (!hostname || tab.url.startsWith('chrome://')) return;

  await ensureDomainAllowed(hostname);

  let delivered = await sendToTab(tab.id, { type: 'mobius:toggle-panel' });
  if (!delivered) {
    // Content script not present (tab predates the extension load) — inject it.
    try {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['content.js'] });
      await new Promise((r) => setTimeout(r, 150));
      delivered = await sendToTab(tab.id, { type: 'mobius:toggle-panel' });
    } catch (e) {
      console.error('[Mobius Background] Could not inject content script:', e);
    }
  }
});

// =============================================================================
// Alerts → toolbar badge. Polls the backend on an alarm (survives service
// worker sleep) using the stored access token; unread count shows on the
// pinned icon. Cleared when the panel opens ('mobius:badge:clear').
// =============================================================================

const ALERTS_ALARM = 'mobius-alerts-poll';

async function pollAlertsBadge(): Promise<void> {
  try {
    const items = await chrome.storage.session.get(['mobius.auth.accessToken']);
    const token = items['mobius.auth.accessToken'] as string | undefined;
    if (!token) {
      await chrome.action.setBadgeText({ text: '' });
      return;
    }
    const resp = await fetch(`${API_V1_URL}/user/alerts`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) return;
    const data = await resp.json();
    const alerts: Array<{ read?: boolean }> = Array.isArray(data?.alerts) ? data.alerts : [];
    const unread = alerts.filter((a) => !a.read).length;
    await chrome.action.setBadgeBackgroundColor({ color: '#3b82f6' });
    await chrome.action.setBadgeText({ text: unread > 0 ? (unread > 9 ? '9+' : String(unread)) : '' });
  } catch (e) {
    console.error('[Mobius Background] Alerts badge poll failed:', e);
  }
}

chrome.alarms.create(ALERTS_ALARM, { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALERTS_ALARM) void pollAlertsBadge();
});
void pollAlertsBadge();
