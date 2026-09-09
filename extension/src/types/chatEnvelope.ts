/**
 * Assistant render envelope — the chat pipeline's declared render contract.
 *
 * mobius-chat returns `assistant_envelope: { version, blocks[] }` alongside
 * the legacy card. It is the SOLE render source for a turn: an ordered list
 * of typed blocks the surface renders verbatim, so the extension never
 * re-derives structure from the raw card. Unknown block types render as a
 * safe fallback (or are skipped), so a server that adds a block never breaks
 * an older client.
 *
 * Shapes below are transcribed from live `quick`/default responses. Treat
 * every field as optional at the boundary — the server owns the contract and
 * the renderer must tolerate partial blocks.
 */

export interface AssistantEnvelope {
  version: number;
  blocks: EnvelopeBlock[];
}

export interface SourceRef {
  index?: number;
  title?: string;
  page?: number;
  snippet?: string;
  document_id?: string;
}

export interface TraceRound {
  round?: number;
  tool?: string | null;
  learned?: string;
  running_answer?: string;
  gaps_open?: string[];
  gaps_closed?: string[];
}

export type EnvelopeBlock =
  | { type: 'mode_badge'; mode?: string }
  | { type: 'tool_attribution'; tool_fired?: string; icon?: string; label?: string }
  | { type: 'direct_answer'; markdown?: string }
  | { type: 'bullets'; items?: string[]; label?: string }
  | {
      type: 'first_pass';
      collapsed_default?: boolean;
      draft_markdown?: string;
      trace_rounds?: TraceRound[];
    }
  | { type: 'sources'; refs?: SourceRef[] }
  // Forward-compat: any block type we don't know yet.
  | { type: string; [k: string]: unknown };

/** Invocation + cost telemetry from the response, surfaced subtly in the UI. */
export interface ChatTelemetry {
  model?: string;
  mode?: string;
  inputTokens?: number;
  outputTokens?: number;
  costUsd?: number;
  latencyMs?: number;
}

/** Narrow an envelope-shaped value defensively. */
export function asEnvelope(value: unknown): AssistantEnvelope | null {
  if (!value || typeof value !== 'object') return null;
  const v = value as { version?: unknown; blocks?: unknown };
  if (!Array.isArray(v.blocks)) return null;
  return {
    version: typeof v.version === 'number' ? v.version : 1,
    blocks: v.blocks.filter((b): b is EnvelopeBlock => !!b && typeof b === 'object' && typeof (b as EnvelopeBlock).type === 'string'),
  };
}
