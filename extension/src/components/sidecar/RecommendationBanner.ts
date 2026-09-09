/**
 * RecommendationBanner — the proactive nudge (Phase 2.2).
 *
 * The most prominent alert type, with a permanent place at the top of the
 * panel body (below the context strip, above Do/Save). Care readiness is
 * surfaced HERE rather than as its own bar. One at a time; more queue.
 * Pure view — the caller places the returned element and injects behavior.
 */

import type { Recommendation } from '../../types/sidebar';
import { ICONS } from './icons';

export interface RecommendationBannerOpts {
  rec: Recommendation;
  onAct: () => void;
  onDismiss: () => void;
}

export function RecommendationBanner(opts: RecommendationBannerOpts): HTMLElement {
  const banner = document.createElement('div');
  banner.className = 'sidecar-reco' + (opts.rec.temper === 'correction' ? ' warn' : '');

  const icon = document.createElement('span');
  icon.className = 'sidecar-reco-icon';
  icon.innerHTML = opts.rec.temper === 'correction' ? ICONS.warning : ICONS.bulb;
  banner.appendChild(icon);

  const body = document.createElement('div');
  body.className = 'sidecar-reco-text';

  const lead = document.createElement('div');
  lead.className = 'sidecar-reco-lead';
  lead.textContent = opts.rec.temper === 'correction' ? 'Heads up' : 'Recommendation';
  body.appendChild(lead);

  const msg = document.createElement('div');
  msg.className = 'sidecar-reco-msg';
  msg.innerHTML = sanitize(opts.rec.message);
  body.appendChild(msg);

  const actions = document.createElement('div');
  actions.className = 'sidecar-reco-actions';
  const act = document.createElement('button');
  act.type = 'button';
  act.className = 'sidecar-reco-do';
  act.textContent = opts.rec.actionLabel;
  act.addEventListener('click', () => opts.onAct());
  const dismiss = document.createElement('button');
  dismiss.type = 'button';
  dismiss.className = 'sidecar-reco-x';
  dismiss.textContent = 'Dismiss';
  dismiss.addEventListener('click', () => {
    banner.remove();
    opts.onDismiss();
  });
  actions.appendChild(act);
  actions.appendChild(dismiss);
  body.appendChild(actions);

  banner.appendChild(body);
  return banner;
}

/** Allow only <b> emphasis; strip everything else. */
function sanitize(html: string): string {
  const escaped = html.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c] || c));
  return escaped.replace(/&lt;b&gt;/g, '<b>').replace(/&lt;\/b&gt;/g, '</b>');
}
