/**
 * Trace log (Phase 2.3) — an in-memory, subscribable action trace.
 *
 * Every meaningful action the sidecar takes emits a trace event so the user
 * can see exactly what happened, in order: surface detection, sign-in, page
 * reads, consent decisions, authorizations (with their task_id), chat calls,
 * and errors. Rendered by the hidden SystemLog panel at the bottom of the
 * sidebar. In-memory ring buffer (last N), lives for the page session.
 *
 * PHI-safe: callers pass short, non-identifying messages (labels/actions),
 * never raw page text.
 */

export type TraceCategory =
  | 'auth'
  | 'surface'
  | 'read'
  | 'consent'
  | 'authz'
  | 'chat'
  | 'net'
  | 'action'
  | 'error';

export interface TraceEvent {
  ts: number;
  category: TraceCategory;
  message: string;
  /** Correlation id when the action is part of an invocation. */
  taskId?: string;
}

const MAX = 200;
const buffer: TraceEvent[] = [];
const listeners = new Set<(e: TraceEvent) => void>();

export function trace(category: TraceCategory, message: string, taskId?: string): void {
  const event: TraceEvent = { ts: Date.now(), category, message, taskId };
  buffer.push(event);
  if (buffer.length > MAX) buffer.shift();
  for (const fn of listeners) {
    try {
      fn(event);
    } catch {
      // a bad listener must not break tracing
    }
  }
}

export function getTrace(): TraceEvent[] {
  return buffer.slice();
}

export function onTrace(fn: (e: TraceEvent) => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/** Plain-text dump for copy-to-clipboard. */
export function formatTrace(): string {
  return buffer
    .map((e) => {
      const t = new Date(e.ts).toISOString().slice(11, 23);
      const id = e.taskId ? ` [${e.taskId}]` : '';
      return `${t}  ${e.category.toUpperCase().padEnd(7)}  ${e.message}${id}`;
    })
    .join('\n');
}
