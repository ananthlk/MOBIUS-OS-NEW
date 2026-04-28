"""
Skills API Blueprint — POST /api/v1/skills/corpus_search

Exposes the corpus search skill to downstream consumers:
  - mobius-chat  (replaces its own two-arm BM25/vector stack for this skill)
  - Browser extension sidecar (direct policy lookup)
  - Future: other OS surfaces (mini, resolution planner)

The endpoint is a thin proxy to app.services.corpus_search.search().
It passes the caller="os_api" tag so search_events on the RAG side can
distinguish OS-mediated calls from direct RAG API calls.

Pipeline trace:
  The full telemetry envelope from the RAG service is returned verbatim
  under "pipeline_trace".  Chat's SearchTracePanel and the OS sidecar
  can render it directly — same shape, no translation needed.
"""
from __future__ import annotations

import logging
from flask import Blueprint, request, jsonify, g
from functools import wraps

from app.services import corpus_search as _cs
from app.services.auth_service import get_user_from_token
from app.db.postgres import get_db_session

logger = logging.getLogger(__name__)

skills_bp = Blueprint("skills", __name__, url_prefix="/api/v1/skills")


# ── Optional auth (soft — returns 401 only when token present but invalid) ──

def _soft_auth(f):
    """Attach user to g if token present; allow unauthenticated through."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            try:
                with get_db_session() as db:
                    user = get_user_from_token(db, token)
                    if user:
                        g.user_id = user.user_id
                        g.tenant_id = user.tenant_id
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated


# ── POST /api/v1/skills/corpus_search ─────────────────────────────────

@skills_bp.route("/corpus_search", methods=["POST"])
@_soft_auth
def corpus_search_endpoint():
    """
    Run corpus search via the RAG skill and return chunks + pipeline trace.

    Request body (all optional except query):
      query               str   — the search question
      k                   int   — max chunks to return (default 10)
      mode                str   — corpus | precision | recall
      filters             obj   — { payer, state, program, authority_level }
      include_document_ids list  — restrict to specific document UUIDs
      assembly_strategy   str   — score | canonical_first | balanced
      canonical_floor     float — min authoritative fraction (balanced only)

    Response:
      {
        "ok":             true,
        "chunks":         [...],      # CorpusChunk list
        "pipeline_trace": {...},      # full telemetry envelope
        "returned":       N
      }

    On error:
      { "ok": false, "error": "..." }
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({"ok": False, "error": "query is required"}), 400

    # Caller attribution: prefer explicit header, fall back to auth user
    caller_header = (request.headers.get("X-Caller") or "").strip()
    caller = caller_header or "os_api"

    result = _cs.search(
        query=query,
        k=int(data.get("k") or 10),
        mode=str(data.get("mode") or "corpus"),
        filters=data.get("filters") or None,
        include_document_ids=data.get("include_document_ids") or None,
        assembly_strategy=str(data.get("assembly_strategy") or "score"),
        canonical_floor=float(data.get("canonical_floor") or 0.5),
        caller=caller,
    )

    if not result["ok"]:
        return jsonify({"ok": False, "error": result["error"]}), 502

    return jsonify({
        "ok":             True,
        "chunks":         result["chunks"],
        "pipeline_trace": result["pipeline_trace"],
        "returned":       len(result["chunks"]),
    })
