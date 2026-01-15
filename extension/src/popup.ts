/**
 * Popup entry point for Mobius OS extension
 */

import './styles/popup.css';
type StorageItems = { [key: string]: unknown };

const STORAGE_KEYS = {
  allowedDomains: 'mobius.allowedDomains',
} as const;

function parseHostname(url: string): string | null {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return null;
  }
}

async function storageGet(keys: string[]): Promise<StorageItems> {
  return new Promise((resolve) => chrome.storage.local.get(keys, (items) => resolve(items)));
}

async function storageSet(items: StorageItems): Promise<void> {
  return new Promise((resolve) => chrome.storage.local.set(items, () => resolve()));
}

async function getAllowedDomains(): Promise<string[]> {
  const items = await storageGet([STORAGE_KEYS.allowedDomains]);
  const list = items[STORAGE_KEYS.allowedDomains];
  return Array.isArray(list) ? (list as string[]) : [];
}

async function setAllowed(hostname: string, allowed: boolean): Promise<void> {
  const host = (hostname || '').toLowerCase();
  if (!host) return;
  const current = await getAllowedDomains();
  const set = new Set(current.map((d) => String(d).toLowerCase()).filter(Boolean));
  if (allowed) set.add(host);
  else set.delete(host);
  await storageSet({ [STORAGE_KEYS.allowedDomains]: Array.from(set).sort() });
}

async function sendToTab(tabId: number, message: unknown): Promise<{ ok: boolean; error?: string }> {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (resp) => {
      const err = chrome.runtime.lastError?.message;
      if (err) resolve({ ok: false, error: err });
      else resolve(resp || { ok: true });
    });
  });
}

function renderPopup(app: HTMLElement, opts: { hostname?: string; enabled?: boolean; error?: string }) {
  app.innerHTML = '';

  const wrap = document.createElement('div');
  wrap.style.cssText = 'padding: 12px 12px; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial, sans-serif;';

  const title = document.createElement('div');
  title.textContent = 'Mobius OS';
  title.style.cssText = 'font-weight: 700; font-size: 13px; margin-bottom: 10px;';
  wrap.appendChild(title);

  if (opts.error) {
    const err = document.createElement('div');
    err.textContent = opts.error;
    err.style.cssText = 'font-size: 12px; color: #b3261e; margin-bottom: 10px;';
    wrap.appendChild(err);
  }

  const host = document.createElement('div');
  host.textContent = opts.hostname ? `Site: ${opts.hostname}` : 'Site: (unavailable)';
  host.style.cssText = 'font-size: 12px; color: #5f6368; margin-bottom: 12px;';
  wrap.appendChild(host);

  const row = document.createElement('div');
  row.style.cssText = 'display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom: 12px;';

  const label = document.createElement('div');
  label.textContent = 'Enable mini on this site';
  label.style.cssText = 'font-size: 12px; font-weight: 600;';

  const toggle = document.createElement('input');
  toggle.type = 'checkbox';
  toggle.checked = Boolean(opts.enabled);
  toggle.style.cssText = 'width: 16px; height: 16px;';

  row.appendChild(label);
  row.appendChild(toggle);
  wrap.appendChild(row);

  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:flex; gap:8px;';

  const openBtn = document.createElement('button');
  openBtn.textContent = 'Open sidebar';
  openBtn.style.cssText = 'flex:1; padding:8px 10px; border-radius:10px; border:1px solid rgba(60,64,67,0.18); background:#fff; cursor:pointer; font-size:12px; font-weight:700;';

  const closeBtn = document.createElement('button');
  closeBtn.textContent = 'Collapse';
  closeBtn.style.cssText = openBtn.style.cssText;

  btnRow.appendChild(openBtn);
  btnRow.appendChild(closeBtn);
  wrap.appendChild(btnRow);

  app.appendChild(wrap);

  return { toggle, openBtn, closeBtn };
}

// Initialize popup UI
async function init() {
  const app = document.getElementById('app');
  if (!app) return;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url) {
    renderPopup(app, { error: 'No active tab found.' });
    return;
  }

  const blockedSchemes = ['chrome://', 'chrome-extension://', 'edge://', 'about:'];
  if (blockedSchemes.some((s) => tab.url!.startsWith(s))) {
    renderPopup(app, { error: `Not available on this page.`, hostname: tab.url });
    return;
  }

  const hostname = parseHostname(tab.url);
  if (!hostname) {
    renderPopup(app, { error: 'Could not parse hostname.', hostname: tab.url });
    return;
  }

  const allowed = await getAllowedDomains();
  const enabled = allowed.map((d) => d.toLowerCase()).includes(hostname);

  const ui = renderPopup(app, { hostname, enabled });

  ui.toggle.addEventListener('change', async () => {
    const next = ui.toggle.checked;
    await setAllowed(hostname, next);
    await sendToTab(tab.id!, { type: 'mobius:setDomainAllowed', hostname, allowed: next });
  });

  ui.openBtn.addEventListener('click', async () => {
    // If the user hasn't enabled this site yet, enable it first so expand works.
    if (!ui.toggle.checked) {
      ui.toggle.checked = true;
      await setAllowed(hostname, true);
      await sendToTab(tab.id!, { type: 'mobius:setDomainAllowed', hostname, allowed: true });
    }

    const resp = await sendToTab(tab.id!, { type: 'mobius:expand' });
    if (!resp.ok) {
      renderPopup(app, { hostname, enabled: ui.toggle.checked, error: resp.error || 'Failed to open.' });
    } else {
      window.close();
    }
  });

  ui.closeBtn.addEventListener('click', async () => {
    const resp = await sendToTab(tab.id!, { type: 'mobius:collapse' });
    if (!resp.ok) {
      renderPopup(app, { hostname, enabled: ui.toggle.checked, error: resp.error || 'Failed to collapse.' });
    }
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
