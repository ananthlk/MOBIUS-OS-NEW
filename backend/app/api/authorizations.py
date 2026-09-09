"""Authorizations API — POST /api/v1/authorizations

Records a PHI authorization/acknowledgement from the extension into the
`authorization_log` correlation table (provenance source of truth), keyed by
the client-minted task_id. Best-effort forwards the attestation to the PHI
agent's compliance log by the same task_id (see _forward_to_hipaa_log).

PHI-safe: stores host + a SHA-256 of the full origin URL + MASKED identifier
labels only. Never the raw URL (may carry identifiers) or raw text.

Auth is soft: a valid Bearer attributes the record to the user; an anonymous
call still records (surface provenance matters even pre-auth), but PHI
attestations SHOULD carry a user — the API flags that in the response.
"""
import hashlib
import os
from datetime import datetime

import requests
from flask import Blueprint, g, jsonify, request

from app.db.postgres import get_db_session
from app.models.authorization import AuthorizationLog
from app.services.auth_service import get_user_from_token

authorizations_bp = Blueprint("authorizations", __name__, url_prefix="/api/v1")

_PHI_LOG_URL = os.getenv("PHI_CLASSIFIER_URL", "https://mobius-phi-classifier-ortabkknqa-uc.a.run.app")


def _soft_user():
    """Return (user_id, tenant_id) from a Bearer token, or (None, None)."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None
    try:
        with get_db_session() as db:
            user = get_user_from_token(db, auth_header[7:])
            if user:
                return user.user_id, user.tenant_id
    except Exception as exc:
        print(f"[Authorizations] soft-auth error: {exc}")
    return None, None


def _forward_to_hipaa_log(record: dict) -> str | None:
    """Best-effort: forward the attestation to the PHI agent's compliance log.

    Interim: the PHI agent's authorization-record endpoint is not built yet
    (contract proposed in docs/PHI_AUTHORIZATION_LOG_CONTRACT.md). Until it
    exists, this is a no-op that returns None. Never blocks the write to our
    own correlation table.
    """
    endpoint = os.getenv("PHI_AUTHZ_LOG_ENDPOINT")  # unset until the PHI agent ships it
    if not endpoint:
        return None
    try:
        resp = requests.post(f"{_PHI_LOG_URL}{endpoint}", json=record, timeout=4)
        if resp.status_code == 200:
            return (resp.json() or {}).get("audit_ref")
    except Exception as exc:
        print(f"[Authorizations] hipaa-log forward failed (non-fatal): {exc}")
    return None


@authorizations_bp.route("/authorizations", methods=["POST"])
def record_authorization():
    data = request.get_json(silent=True) or {}
    task_id = (data.get("task_id") or "").strip()
    action = (data.get("action") or "").strip()

    if not task_id:
        return jsonify({"ok": False, "error": "task_id is required"}), 400
    if action not in AuthorizationLog.ACTIONS:
        return jsonify({"ok": False, "error": f"unknown action '{action}'"}), 400

    user_id, tenant_id = _soft_user()

    # Hash the full origin URL (may carry identifiers); keep host in the clear.
    origin_url = data.get("origin_url") or ""
    origin_host = (data.get("origin_host") or "").lower()[:255]
    url_sha = hashlib.sha256(origin_url.encode("utf-8")).hexdigest() if origin_url else None
    phi_labels = data.get("phi_labels")
    if not isinstance(phi_labels, list):
        phi_labels = None

    record = {
        "task_id": task_id[:64],
        "user_id": str(user_id) if user_id else None,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "surface": (data.get("surface") or "extension")[:32],
        "origin_host": origin_host or None,
        "origin_url_sha256": url_sha,
        "action": action,
        "phi_present": bool(data.get("phi_present")),
        "phi_labels": phi_labels,
        "chat_correlation_id": (data.get("chat_correlation_id") or None),
    }

    audit_ref = _forward_to_hipaa_log(record)

    try:
        with get_db_session() as db:
            row = AuthorizationLog(
                task_id=record["task_id"],
                user_id=user_id,
                tenant_id=tenant_id,
                surface=record["surface"],
                origin_host=record["origin_host"],
                origin_url_sha256=url_sha,
                action=action,
                phi_present=record["phi_present"],
                phi_labels=phi_labels,
                chat_correlation_id=record["chat_correlation_id"],
                phi_audit_ref=audit_ref,
                created_at=datetime.utcnow(),
            )
            db.merge(row)  # idempotent on task_id
            db.commit()
    except Exception as exc:
        print(f"[Authorizations] persist failed: {exc}")
        return jsonify({"ok": False, "error": "persist failed"}), 500

    return jsonify(
        {
            "ok": True,
            "task_id": record["task_id"],
            "attributed": user_id is not None,
            "hipaa_log_forwarded": audit_ref is not None,
        }
    )
