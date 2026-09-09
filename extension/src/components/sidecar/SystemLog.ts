/**
 * SystemLog — the hidden action trace at the bottom of the sidebar.
 *
 * Almost invisible but available: a collapsed "System log" strip pinned at
 * the very bottom. Expand it to trace every action in order (surface, auth,
 * reads, consent, authorizations with task_ids, chat, errors), newest last.
 * Live-updates via onTrace; copy button dumps the buffer.
 */

import { getTrace, onTrace, formatTrace, TraceCategory, TraceEvent } from '../../services/traceLog';

const CAT_COLOR: Record<TraceCategory, string> = {
  auth: 'var(--mobius-accent, #3b82f6)',
  surface: 'var(--mobius-text-muted, #64748b)',
  read: 'var(--mobius-violet, #7c3aed)',
  consent: 'var(--mobius-warning, #f59e0b)',
  authz: 'var(--mobius-warning, #f59e0b)',
  chat: 'var(--mobius-success, #10b981)',
  net: 'var(--mobius-info, #0891b2)',
  action: 'var(--mobius-accent, #3b82f6)',
  error: 'var(--mobius-error, #dc2626)',
};

export function SystemLog(): HTMLElement {
  const root = document.createElement('div');
  root.className = 'sidecar-syslog';

  // Header (toggle)
  const header = document.createElement('button');
  header.type = 'button';
  header.className = 'sidecar-syslog-head';
  const chevron = document.createElement('span');
  chevron.className = 'sidecar-syslog-chevron';
  chevron.textContent = '⌃';
  const label = document.createElement('span');
  label.className = 'sidecar-syslog-label';
  label.textContent = 'System log';
  const count = document.createElement('span');
  count.className = 'sidecar-syslog-count';
  header.appendChild(chevron);
  header.appendChild(label);
  header.appendChild(count);

  const copyBtn = document.createElement('span');
  copyBtn.className = 'sidecar-syslog-copy';
  copyBtn.textContent = 'copy';
  copyBtn.title = 'Copy the log';
  header.appendChild(copyBtn);

  // Body (the log lines)
  const body = document.createElement('div');
  body.className = 'sidecar-syslog-body';

  const render = (events: TraceEvent[]) => {
    count.textContent = String(events.length);
  };

  const appendLine = (e: TraceEvent) => {
    const line = document.createElement('div');
    line.className = 'sidecar-syslog-line';
    const t = document.createElement('span');
    t.className = 'sidecar-syslog-t';
    t.textContent = new Date(e.ts).toISOString().slice(11, 19);
    const cat = document.createElement('span');
    cat.className = 'sidecar-syslog-cat';
    cat.style.color = CAT_COLOR[e.category] || 'var(--mobius-text-muted)';
    cat.textContent = e.category;
    const msg = document.createElement('span');
    msg.className = 'sidecar-syslog-msg';
    msg.textContent = e.message + (e.taskId ? `  ·  ${e.taskId}` : '');
    line.appendChild(t);
    line.appendChild(cat);
    line.appendChild(msg);
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
  };

  // seed with existing events
  for (const e of getTrace()) appendLine(e);
  render(getTrace());

  const unsub = onTrace((e) => {
    appendLine(e);
    render(getTrace());
  });
  // detach the listener when the node is removed
  const observer = new MutationObserver(() => {
    if (!root.isConnected) {
      unsub();
      observer.disconnect();
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  header.addEventListener('click', () => root.classList.toggle('open'));
  copyBtn.addEventListener('click', (ev) => {
    ev.stopPropagation();
    try {
      void navigator.clipboard.writeText(formatTrace());
      copyBtn.textContent = 'copied';
      setTimeout(() => (copyBtn.textContent = 'copy'), 1200);
    } catch {
      copyBtn.textContent = 'copy failed';
    }
  });

  root.appendChild(header);
  root.appendChild(body);
  return root;
}
