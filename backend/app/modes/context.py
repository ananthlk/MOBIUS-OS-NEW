"""
Context Detection Endpoints for Mobius OS.

Provides endpoints for the Chrome extension to resolve detected patient
identifiers to internal Mobius patient context IDs (crosswalk).

Also returns tenant-specific detection pattern configurations.
"""

import uuid
from flask import Blueprint, request, jsonify

from app.services.crosswalk import get_crosswalk_service, CrosswalkService


bp = Blueprint("context", __name__, url_prefix="/api/v1/context")

# Default tenant ID for development (no auth yet)
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_tenant_id(data: dict) -> uuid.UUID:
    """Get tenant ID from request data or use default."""
    tenant_id = data.get("tenant_id")
    if tenant_id:
        try:
            return uuid.UUID(tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


@bp.route("/detect", methods=["POST"])
def detect_context():
    """
    Resolve a detected patient identifier to internal Mobius context.
    
    This is the crosswalk endpoint called by the Chrome extension when
    it detects a potential patient identifier on a webpage.
    
    Request Body:
        - id_type: str - Type of identifier ('mrn', 'insurance', 'patient_key', 'unknown')
        - id_value: str - The detected identifier value
        - source_hint: str (optional) - Hint about EMR system ('epic', 'cerner', etc.)
        - domain: str (optional) - Current page domain (for pattern config lookup)
        - tenant_id: str (optional) - Tenant UUID
    
    Response:
        - found: bool - Whether the patient was found
        - patient_context_id: str (if found) - Internal Mobius UUID
        - patient_key: str (if found) - Patient key
        - display_name: str (if found) - Display name for UI
        - id_masked: str (if found) - Masked ID for display
        - detection_config: object (optional) - Tenant-specific pattern overrides
    """
    data = request.json or {}
    
    # Extract and validate parameters
    id_type = (data.get("id_type") or "").strip().lower()
    id_value = (data.get("id_value") or "").strip()
    source_hint = (data.get("source_hint") or "").strip().lower() or None
    domain = (data.get("domain") or "").strip().lower() or None
    tenant_id = _get_tenant_id(data)
    
    if not id_value:
        return jsonify({"error": "id_value is required"}), 400
    
    # Default id_type if not provided
    if not id_type:
        id_type = "unknown"
    
    # Get crosswalk service
    service = get_crosswalk_service()
    
    # Resolve the patient identifier
    result = service.resolve_patient(
        id_type=id_type,
        id_value=id_value,
        tenant_id=tenant_id,
        source_hint=source_hint,
    )
    
    # Get tenant-specific detection config if available
    detection_config = None
    if domain:
        detection_config = service.get_merged_patterns(tenant_id, domain)
    
    # Build response
    response = result.to_dict()
    if detection_config:
        response["detection_config"] = detection_config
    
    return jsonify(response)


@bp.route("/config", methods=["GET"])
def get_detection_config():
    """
    Get detection configuration for a specific domain.
    
    Query Parameters:
        - domain: str - The domain to get configuration for
        - tenant_id: str (optional) - Tenant UUID
    
    Response:
        - domain: str - The requested domain
        - has_config: bool - Whether custom configuration exists
        - patterns: object (optional) - Merged pattern configuration
    """
    domain = (request.args.get("domain") or "").strip().lower()
    tenant_id_str = request.args.get("tenant_id")
    
    # Get tenant ID
    tenant_id = DEFAULT_TENANT_ID
    if tenant_id_str:
        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except ValueError:
            pass
    
    if not domain:
        return jsonify({"error": "domain query parameter is required"}), 400
    
    service = get_crosswalk_service()
    patterns = service.get_merged_patterns(tenant_id, domain)
    
    return jsonify({
        "domain": domain,
        "has_config": patterns is not None,
        "patterns": patterns,
    })


@bp.route("/lookup", methods=["GET"])
def lookup_patient():
    """
    Simple GET-based patient lookup by ID.
    
    Query Parameters:
        - id_type: str - Type of identifier
        - id_value: str - The identifier value
        - tenant_id: str (optional) - Tenant UUID
    
    Response:
        - Same as /detect endpoint
    """
    id_type = (request.args.get("id_type") or "").strip().lower()
    id_value = (request.args.get("id_value") or "").strip()
    tenant_id_str = request.args.get("tenant_id")
    
    if not id_value:
        return jsonify({"error": "id_value query parameter is required"}), 400
    
    # Default id_type if not provided
    if not id_type:
        id_type = "unknown"
    
    # Get tenant ID
    tenant_id = DEFAULT_TENANT_ID
    if tenant_id_str:
        try:
            tenant_id = uuid.UUID(tenant_id_str)
        except ValueError:
            pass
    
    service = get_crosswalk_service()
    result = service.resolve_patient(
        id_type=id_type,
        id_value=id_value,
        tenant_id=tenant_id,
    )
    
    return jsonify(result.to_dict())
