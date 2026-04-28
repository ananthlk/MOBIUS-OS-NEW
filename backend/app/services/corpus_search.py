"""
Corpus Search Service — calls mobius-rag POST /api/skills/v1/corpus_search.

This is the mobius-os side of the corpus search skill.  It is:

  - Used directly by decision agents (policy enrichment, task generation)
  - Exposed as POST /api/v1/skills/corpus_search for downstream consumers
    (mobius-chat, extension, etc.)

HTTP contract (RAG side, frozen at v1):
  Request:  { query, k, mode, filters, include_document_ids, assembly_strategy }
  Response: { chunks: [CorpusChunk], telemetry: {...} }

The full telemetry payload (pipeline_trace) is returned so callers can
render retrieval efficiency details or persist them for analytics.

Caller column:
  Pass caller="os_agent" for decision-agent calls, caller="os_api" for
  external HTTP callers (chat, extension).  Stored in search_events on
  the RAG side for cross-service attribution.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any

logger = logging.getLogger(__name__)

# Resolved once per process.  Override via RAG_API_URL env.
_RAG_API_URL: str = ""


def _base_url() -> str:
    global _RAG_API_URL
    if not _RAG_API_URL:
        _RAG_API_URL = (os.environ.get("RAG_API_URL") or "").rstrip("/")
    return _RAG_API_URL


# ── Public API ────────────────────────────────────────────────────────

def search(
    query: str,
    *,
    k: int = 10,
    mode: str = "corpus",               # corpus | precision | recall
    filters: dict[str, str] | None = None,
    include_document_ids: list[str] | None = None,
    assembly_strategy: str = "score",   # score | canonical_first | balanced
    canonical_floor: float = 0.5,
    caller: str = "os_api",
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Call the RAG corpus_search skill and return the full response.

    Returns a dict with:
      chunks         — list of CorpusChunk dicts (text, document_name, page_number,
                       rerank_score, confidence_label, jpd_tags, retrieval_arms, …)
      pipeline_trace — full telemetry envelope (timing, arm_hits, scoring_trace,
                       assembly, bm25_normalized_query, …)
      error          — str if the call failed, None otherwise
      ok             — bool

    Never raises.  On failure returns ok=False + error message.
    """
    base = _base_url()
    if not base:
        return _err("RAG_API_URL not set; corpus search unavailable")

    url = f"{base}/api/skills/v1/corpus_search"
    payload: dict[str, Any] = {
        "query":              query,
        "k":                  k,
        "mode":               mode,
        "assembly_strategy":  assembly_strategy,
        "canonical_floor":    canonical_floor,
        "caller":             caller,
    }
    if filters:
        payload["filters"] = filters
    if include_document_ids:
        payload["include_document_ids"] = include_document_ids

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")[:200]
        except Exception:
            pass
        logger.warning("corpus_search HTTP %s: %s", exc.code, detail)
        return _err(f"RAG service returned HTTP {exc.code}")
    except Exception as exc:
        logger.warning("corpus_search call failed: %s", exc)
        return _err(str(exc))

    chunks = data.get("chunks") or []
    telemetry = data.get("telemetry") or {}

    logger.info(
        "corpus_search: mode=%s k=%s → %d chunks  %.0fms",
        mode, k, len(chunks), telemetry.get("total_ms") or 0,
    )

    return {
        "ok":             True,
        "error":          None,
        "chunks":         chunks,
        "pipeline_trace": telemetry,
    }


def search_for_policy(
    payer: str,
    topic: str,
    *,
    state: str = "",
    program: str = "",
    k: int = 6,
) -> dict[str, Any]:
    """
    Convenience wrapper for decision-agent policy lookups.

    Runs in "corpus" (hybrid) mode with canonical_first assembly so
    contract_source_of_truth documents bubble to top.  Filters by payer
    and optionally by state/program so results are jurisdiction-scoped.

    Returns same shape as search().
    """
    filters: dict[str, str] = {"payer": payer}
    if state:
        filters["state"] = state
    if program:
        filters["program"] = program

    return search(
        query=topic,
        k=k,
        mode="corpus",
        filters=filters,
        assembly_strategy="canonical_first",
        caller="os_agent",
    )


# ── Helpers ───────────────────────────────────────────────────────────

def _err(msg: str) -> dict[str, Any]:
    return {"ok": False, "error": msg, "chunks": [], "pipeline_trace": {}}
