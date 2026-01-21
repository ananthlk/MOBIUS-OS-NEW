/**
 * Background service worker for Mobius OS extension
 */

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
