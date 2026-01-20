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

/**
 * Auth Storage Message Handler
 * Content scripts cannot access chrome.storage.session directly,
 * so we proxy storage operations through the background script.
 */
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type) return false;

  // Handle auth storage operations
  if (message.type === 'mobius:auth:getStorage') {
    const keys = message.keys as string[];
    chrome.storage.session.get(keys).then((result) => {
      sendResponse({ ok: true, data: result });
    }).catch((error) => {
      console.error('[Mobius Background] Storage get error:', error);
      sendResponse({ ok: false, error: String(error) });
    });
    return true; // Keep channel open for async response
  }

  if (message.type === 'mobius:auth:setStorage') {
    const items = message.items as Record<string, unknown>;
    chrome.storage.session.set(items).then(() => {
      sendResponse({ ok: true });
    }).catch((error) => {
      console.error('[Mobius Background] Storage set error:', error);
      sendResponse({ ok: false, error: String(error) });
    });
    return true;
  }

  if (message.type === 'mobius:auth:clearStorage') {
    const keys = message.keys as string[] | undefined;
    const clearPromise = keys 
      ? chrome.storage.session.remove(keys)
      : chrome.storage.session.clear();
    
    clearPromise.then(() => {
      sendResponse({ ok: true });
    }).catch((error) => {
      console.error('[Mobius Background] Storage clear error:', error);
      sendResponse({ ok: false, error: String(error) });
    });
    return true;
  }

  return false;
});
