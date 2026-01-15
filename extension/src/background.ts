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
