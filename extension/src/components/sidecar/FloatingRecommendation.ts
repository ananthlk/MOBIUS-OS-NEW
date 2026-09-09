/**
 * FloatingRecommendation — the proactive nudge (Phase 2.2).
 *
 * The most prominent alert type: a floating, draggable card sourced from
 * backend intelligence (care-readiness, missed-visit patterns, benefit
 * eligibility). Care readiness is surfaced HERE rather than as its own bar.
 * One at a time; position persists so the user can park it where they like.
 *
 * Rendered into document.body so it can float over the page independent of
 * the panel. Pure view — all behavior via injected callbacks.
 */

import type { Recommendation, FloatingPos } from '../../types/sidebar';
import { ICONS } from './icons';

const CARD_ID = 'mobius-floating-reco';

export interface FloatingRecommendationOpts {
  rec: Recommendation;
  onAct: () => void;
  onDismiss: () => void;
  initialPos?: FloatingPos | null;
  onMove?: (pos: FloatingPos) => void;
}

export function FloatingRecommendation(opts: FloatingRecommendationOpts): HTMLElement {
  // Single instance: replace any existing card.
  document.getElementById(CARD_ID)?.remove();

  const card = document.createElement('div');
  card.id = CARD_ID;
  card.className = 'mobius-reco-card' + (opts.rec.temper === 'correction' ? ' warn' : '');

  const pos = clampToViewport(opts.initialPos);
  card.style.left = `${pos.x}px`;
  card.style.top = `${pos.y}px`;

  const grip = document.createElement('div');
  grip.className = 'mobius-reco-grip';
  grip.title = 'Drag to move';
  grip.innerHTML = '<span></span><span></span>';
  card.appendChild(grip);

  const body = document.createElement('div');
  body.className = 'mobius-reco-body';

  const lead = document.createElement('div');
  lead.className = 'mobius-reco-lead';
  lead.innerHTML =
    (opts.rec.temper === 'correction' ? ICONS.warning : ICONS.bulb) +
    `<span>${opts.rec.temper === 'correction' ? 'Heads up' : 'Recommendation'}</span>`;
  body.appendChild(lead);

  const msg = document.createElement('div');
  msg.className = 'mobius-reco-msg';
  msg.innerHTML = sanitize(opts.rec.message);
  body.appendChild(msg);

  const actions = document.createElement('div');
  actions.className = 'mobius-reco-actions';
  const act = document.createElement('button');
  act.type = 'button';
  act.className = 'mobius-reco-do';
  act.textContent = opts.rec.actionLabel;
  act.addEventListener('click', () => opts.onAct());
  const dismiss = document.createElement('button');
  dismiss.type = 'button';
  dismiss.className = 'mobius-reco-x';
  dismiss.textContent = 'Dismiss';
  dismiss.addEventListener('click', () => {
    card.remove();
    opts.onDismiss();
  });
  actions.appendChild(act);
  actions.appendChild(dismiss);
  body.appendChild(actions);

  card.appendChild(body);
  wireDrag(card, grip, opts.onMove);
  document.body.appendChild(card);
  return card;
}

export function removeFloatingRecommendation(): void {
  document.getElementById(CARD_ID)?.remove();
}

// ── helpers ────────────────────────────────────────────────────────────────

function clampToViewport(pos?: FloatingPos | null): FloatingPos {
  const w = 300;
  const defaultX = Math.max(12, window.innerWidth - w - 424); // left of a 400px panel
  const p = pos ?? { x: defaultX, y: 96 };
  return {
    x: Math.min(Math.max(8, p.x), Math.max(8, window.innerWidth - w - 8)),
    y: Math.min(Math.max(8, p.y), Math.max(8, window.innerHeight - 120)),
  };
}

function wireDrag(card: HTMLElement, grip: HTMLElement, onMove?: (p: FloatingPos) => void): void {
  let startX = 0;
  let startY = 0;
  let originX = 0;
  let originY = 0;
  let dragging = false;

  const onDown = (e: MouseEvent) => {
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    originX = card.offsetLeft;
    originY = card.offsetTop;
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onUp);
    e.preventDefault();
  };
  const onMouseMove = (e: MouseEvent) => {
    if (!dragging) return;
    card.style.left = `${originX + (e.clientX - startX)}px`;
    card.style.top = `${originY + (e.clientY - startY)}px`;
  };
  const onUp = () => {
    dragging = false;
    document.removeEventListener('mousemove', onMouseMove);
    document.removeEventListener('mouseup', onUp);
    const clamped = clampToViewport({ x: card.offsetLeft, y: card.offsetTop });
    card.style.left = `${clamped.x}px`;
    card.style.top = `${clamped.y}px`;
    onMove?.(clamped);
  };
  grip.addEventListener('mousedown', onDown);
}

/** Allow only <b> emphasis; strip everything else. */
function sanitize(html: string): string {
  const escaped = html.replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c] || c));
  return escaped.replace(/&lt;b&gt;/g, '<b>').replace(/&lt;\/b&gt;/g, '</b>');
}
