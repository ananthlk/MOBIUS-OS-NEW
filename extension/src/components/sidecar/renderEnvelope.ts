/**
 * renderEnvelope — the lightweight adapter that renders a chat turn from the
 * assistant_envelope contract (see types/chatEnvelope). One renderer for both
 * `quick` and default modes: the block set is identical, so the surface just
 * walks blocks in order.
 *
 * Design notes:
 *  · The integrator repeats the "Key Points" bullets INSIDE direct_answer's
 *    markdown AND as a separate `bullets` block. We render direct_answer as
 *    the answer and drop bullet items already present in it (dedupe), so the
 *    surface never double-prints them.
 *  · `first_pass` (the ReAct draft + per-round trace) and `sources` render as
 *    collapsibles — available, not shouting.
 *  · Unknown block types are skipped, so a newer server never breaks us.
 */

import type { AssistantEnvelope, EnvelopeBlock, SourceRef, TraceRound, ChatTelemetry } from '../../types/chatEnvelope';
import { renderMarkdownLite } from './QuickChat';
import { ICONS } from './icons';

export function renderEnvelope(env: AssistantEnvelope, telemetry?: ChatTelemetry): HTMLElement {
  const root = document.createElement('div');
  root.className = 'sidecar-env';

  // Pull the direct_answer text once so we can dedupe repeated bullets.
  const answerText = (
    env.blocks.find((b) => b.type === 'direct_answer') as { markdown?: string } | undefined
  )?.markdown || '';

  // A compact header strip: mode badge + which tool answered.
  const header = buildHeader(env.blocks);
  if (header) root.appendChild(header);

  for (const block of env.blocks) {
    const el = renderBlock(block, answerText);
    if (el) root.appendChild(el);
  }

  if (telemetry) {
    const t = buildTelemetry(telemetry);
    if (t) root.appendChild(t);
  }
  return root;
}

function buildHeader(blocks: EnvelopeBlock[]): HTMLElement | null {
  const mode = (blocks.find((b) => b.type === 'mode_badge') as { mode?: string } | undefined)?.mode;
  const attr = blocks.find((b) => b.type === 'tool_attribution') as
    | { label?: string; tool_fired?: string }
    | undefined;
  if (!mode && !attr) return null;

  const head = document.createElement('div');
  head.className = 'sidecar-env-head';
  if (mode) {
    const badge = document.createElement('span');
    badge.className = 'sidecar-env-mode';
    badge.textContent = mode;
    head.appendChild(badge);
  }
  if (attr?.label) {
    const tool = document.createElement('span');
    tool.className = 'sidecar-env-tool';
    tool.innerHTML = ICONS.page;
    const t = document.createElement('span');
    t.textContent = attr.label;
    tool.appendChild(t);
    head.appendChild(tool);
  }
  return head;
}

function renderBlock(block: EnvelopeBlock, answerText: string): HTMLElement | null {
  switch (block.type) {
    case 'mode_badge':
    case 'tool_attribution':
      return null; // rendered in the header strip

    case 'direct_answer': {
      const md = (block as { markdown?: string }).markdown;
      if (!md) return null;
      const el = document.createElement('div');
      el.className = 'sidecar-env-answer';
      renderMarkdownLite(el, md);
      return el;
    }

    case 'bullets': {
      const b = block as { items?: string[]; label?: string };
      // Drop items already present in the answer to avoid double-printing.
      const items = (b.items || []).filter((it) => !answerContains(answerText, it));
      if (!items.length) return null;
      const wrap = document.createElement('div');
      wrap.className = 'sidecar-env-bullets';
      if (b.label) {
        const lbl = document.createElement('div');
        lbl.className = 'sidecar-env-bullets-lbl';
        lbl.textContent = b.label;
        wrap.appendChild(lbl);
      }
      for (const it of items) {
        const row = document.createElement('div');
        row.className = 'sidecar-env-bullet';
        renderMarkdownLite(row, `• ${it}`);
        wrap.appendChild(row);
      }
      return wrap;
    }

    case 'first_pass': {
      const fp = block as { draft_markdown?: string; trace_rounds?: TraceRound[]; collapsed_default?: boolean };
      if (!fp.draft_markdown && !(fp.trace_rounds && fp.trace_rounds.length)) return null;
      const n = fp.trace_rounds?.length || 0;
      const rounds = n ? ` · ${n} step${n === 1 ? '' : 's'}` : '';
      return buildCollapsible(`How Mobius got here${rounds}`, fp.collapsed_default !== false, (body) => {
        if (fp.trace_rounds?.length) body.appendChild(buildTrace(fp.trace_rounds));
        if (fp.draft_markdown) {
          const draft = document.createElement('div');
          draft.className = 'sidecar-env-draft';
          renderMarkdownLite(draft, fp.draft_markdown);
          body.appendChild(draft);
        }
      });
    }

    case 'sources': {
      const refs = (block as { refs?: SourceRef[] }).refs || [];
      if (!refs.length) return null;
      return buildCollapsible(`Sources · ${refs.length}`, true, (body) => {
        body.appendChild(buildSources(refs));
      });
    }

    default:
      return null; // forward-compat: unknown block types are skipped
  }
}

function buildTrace(rounds: TraceRound[]): HTMLElement {
  const wrap = document.createElement('div');
  wrap.className = 'sidecar-env-trace';
  rounds.forEach((r) => {
    const row = document.createElement('div');
    row.className = 'sidecar-env-trace-row';
    const head = document.createElement('div');
    head.className = 'sidecar-env-trace-head';
    const n = document.createElement('span');
    n.className = 'sidecar-env-trace-n';
    n.textContent = `R${r.round ?? '?'}`;
    head.appendChild(n);
    if (r.tool) {
      const tool = document.createElement('span');
      tool.className = 'sidecar-env-trace-tool';
      tool.textContent = r.tool;
      head.appendChild(tool);
    }
    row.appendChild(head);
    if (r.learned) {
      const learned = document.createElement('div');
      learned.className = 'sidecar-env-trace-learned';
      learned.textContent = r.learned;
      row.appendChild(learned);
    }
    wrap.appendChild(row);
  });
  return wrap;
}

function buildSources(refs: SourceRef[]): HTMLElement {
  const list = document.createElement('div');
  list.className = 'sidecar-env-sources';
  refs.forEach((r) => {
    const item = document.createElement('div');
    item.className = 'sidecar-env-source';
    const title = document.createElement('div');
    title.className = 'sidecar-env-source-title';
    const idx = typeof r.index === 'number' ? `${r.index}. ` : '';
    const page = typeof r.page === 'number' ? ` · p.${r.page}` : '';
    title.textContent = `${idx}${r.title || 'Source'}${page}`;
    item.appendChild(title);
    if (r.snippet) {
      const snip = document.createElement('div');
      snip.className = 'sidecar-env-source-snippet';
      snip.textContent = r.snippet.replace(/\s+/g, ' ').trim().slice(0, 180);
      item.appendChild(snip);
    }
    list.appendChild(item);
  });
  return list;
}

/** A collapsible section with a header toggle and a body. */
function buildCollapsible(
  label: string,
  collapsed: boolean,
  fill: (body: HTMLElement) => void
): HTMLElement {
  const wrap = document.createElement('div');
  wrap.className = 'sidecar-env-fold' + (collapsed ? '' : ' open');
  const head = document.createElement('button');
  head.type = 'button';
  head.className = 'sidecar-env-fold-head';
  const chev = document.createElement('span');
  chev.className = 'sidecar-env-fold-chev';
  chev.textContent = '▾';
  const txt = document.createElement('span');
  txt.textContent = label;
  head.appendChild(chev);
  head.appendChild(txt);
  const body = document.createElement('div');
  body.className = 'sidecar-env-fold-body';
  body.hidden = collapsed;
  fill(body);
  head.addEventListener('click', () => {
    const nowOpen = wrap.classList.toggle('open');
    body.hidden = !nowOpen;
  });
  wrap.appendChild(head);
  wrap.appendChild(body);
  return wrap;
}

function buildTelemetry(t: ChatTelemetry): HTMLElement | null {
  const parts: string[] = [];
  if (t.model) parts.push(t.model);
  if (typeof t.outputTokens === 'number') parts.push(`${formatTokens(t.inputTokens, t.outputTokens)}`);
  if (typeof t.costUsd === 'number') parts.push(`$${t.costUsd.toFixed(t.costUsd < 0.01 ? 4 : 3)}`);
  if (typeof t.latencyMs === 'number') parts.push(`${(t.latencyMs / 1000).toFixed(1)}s`);
  if (!parts.length) return null;
  const el = document.createElement('div');
  el.className = 'sidecar-env-meta';
  el.textContent = parts.join(' · ');
  return el;
}

function formatTokens(input?: number, output?: number): string {
  const fmt = (n: number) => (n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
  if (typeof input === 'number' && typeof output === 'number') return `${fmt(input)}→${fmt(output)} tok`;
  if (typeof output === 'number') return `${fmt(output)} tok`;
  return '';
}

/** Loose containment check used to dedupe repeated bullets. */
function answerContains(answer: string, item: string): boolean {
  const norm = (s: string) => s.replace(/[*_`]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
  const a = norm(answer);
  const it = norm(item);
  if (!it) return true;
  // Match on a solid prefix so minor punctuation differences don't defeat it.
  return a.includes(it) || a.includes(it.slice(0, Math.min(it.length, 60)));
}
