"""
Mini widget endpoints for Mobius OS.

This module is intentionally lightweight and independent from chat mode so the
mini UI can evolve without impacting the full sidebar chat workflow.
"""

from flask import Blueprint, request, jsonify

bp = Blueprint("mini", __name__, url_prefix="/api/v1/mini")

_SAMPLE_PATIENTS = [
    {"name": "Jane Doe", "id": "1234567890"},
    {"name": "John Smith", "id": "9876543210"},
    {"name": "Janet Doe", "id": "1234500000"},
    {"name": "Jimmy Dean", "id": "5551200001"},
]


@bp.route("/status", methods=["POST"])
def status():
    """
    Return proceed/tasking status for the mini widget.

    v1: Stubbed response. In later iterations this will incorporate record detection
    and backend-side task/proceed computations.
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    # Defaults (no detection yet)
    return jsonify(
        {
            "ok": True,
            "session_id": session_id,
            "proceed": {
                "color": "grey",
                "text": "Proceed: Not assessed",
            },
            "tasking": {
                "color": "grey",
                "text": "Tasking: Not applicable",
            },
        }
    )


@bp.route("/note", methods=["POST"])
def note():
    """
    Accept a note submission from the mini widget.

    v1: Echo/ack only (no persistence).
    """
    data = request.json or {}
    session_id = (data.get("session_id") or "").strip()
    note_text = (data.get("note") or "").strip()

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400
    if not note_text:
        return jsonify({"error": "note is required"}), 400

    return jsonify(
        {
            "ok": True,
            "session_id": session_id,
            "note": note_text,
        }
    )


@bp.route("/patient/search", methods=["GET"])
def patient_search():
    """
    Patient search endpoint for the mini's correction modal.

    v1: Returns empty results. Later iterations will integrate with a real patient
    directory or on-page adapters.
    """
    q = (request.args.get("q") or "").strip()
    try:
        limit = int(request.args.get("limit") or "8")
    except ValueError:
        limit = 8

    if not q:
        return jsonify({"ok": True, "q": q, "results": []})

    ql = q.lower()
    results = []
    for p in _SAMPLE_PATIENTS:
        if ql in p["name"].lower() or ql in p["id"]:
            results.append(p)
        if len(results) >= max(1, min(limit, 25)):
            break

    return jsonify({"ok": True, "q": q, "results": results})

