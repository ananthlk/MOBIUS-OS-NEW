/**
 * SaveOffer — the scope offer the Save verb opens: "what does Save mean here?"
 * resolved by a small offer, not a form. Two forms of Save:
 *   • corpus  — the bytes, fetched in-session and filed for retrieval (the
 *               built fetch-to-RAG lane). PHI-gated, org-retrievable.
 *   • bookmark — a pointer only (URL + title + provenance), no bytes fetched,
 *                scoped for me / a patient / the system.
 * Live scopes come from the envelope's `save`-group actions; bookmark scopes
 * are shown as the proposed next tier so the taxonomy is visible on the page.
 *
 * Rendered with the shared confirm-overlay chrome (see sidebar.css
 * `.mobius-confirm-*` + `.mobius-save-offer*`).
 */

import type { EnvelopeAction } from '../../types/sidebar';

export type SaveOfferRow =
  | { kind: 'live'; action: EnvelopeAction }
  | { kind: 'soon'; label: string; sublabel: string };

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c] || c));
}

export function showSaveOffer(rows: SaveOfferRow[], onPick: (action: EnvelopeAction) => void): void {
  document.getElementById('mobius-confirm-overlay')?.remove();
  const overlay = document.createElement('div');
  overlay.id = 'mobius-confirm-overlay';
  overlay.className = 'mobius-confirm-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');

  const card = document.createElement('div');
  card.className = 'mobius-confirm-card mobius-save-offer';

  const h = document.createElement('div');
  h.className = 'mobius-confirm-title';
  h.textContent = 'Save this page';
  card.appendChild(h);

  const sub = document.createElement('div');
  sub.className = 'mobius-confirm-body';
  sub.textContent = 'Where should it go?';
  card.appendChild(sub);

  const close = () => {
    document.removeEventListener('keydown', onKey, true);
    overlay.remove();
  };
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  };

  const list = document.createElement('div');
  list.className = 'mobius-save-offer-list';
  for (const r of rows) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'mobius-save-offer-item' + (r.kind === 'soon' ? ' soon' : '');
    const label = r.kind === 'live' ? r.action.label : r.label;
    const sublabel = r.kind === 'live' ? r.action.sublabel || '' : r.sublabel;
    item.innerHTML =
      `<span class="mso-label">${escapeHtml(label)}</span>` +
      (sublabel ? `<span class="mso-sub">${escapeHtml(sublabel)}</span>` : '') +
      (r.kind === 'soon' ? `<span class="mso-soon">Soon</span>` : '');
    if (r.kind === 'live') {
      item.addEventListener('click', () => {
        close();
        onPick(r.action);
      });
    } else {
      item.disabled = true;
    }
    list.appendChild(item);
  }
  card.appendChild(list);

  overlay.appendChild(card);
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener('keydown', onKey, true);
  document.body.appendChild(overlay);
  list.querySelector<HTMLButtonElement>('.mobius-save-offer-item:not(.soon)')?.focus();
}
