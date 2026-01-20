"""
Mock EMR page for testing the Mini extension.

Displays patient data from the database in multiple EMR-style layouts.
The Mini extension must dynamically adapt to different HTML structures.

Supported styles (via ?style= parameter):
- epic: Epic-like blue theme with sidebar
- cerner: Cerner-like orange theme with tabs
- allscripts: Allscripts-like green traditional table
- athena: Athena-like purple card-based layout
- legacy: Classic minimal table layout
- random: Randomly selects a style (default)
"""

import uuid
import random
from flask import Blueprint, request, jsonify, Response
from sqlalchemy.orm import joinedload

from app.db.postgres import get_db_session
from app.models.patient import PatientContext, PatientSnapshot
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord

bp = Blueprint("mock_emr", __name__, url_prefix="/mock-emr")

# Default tenant ID for development
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Available EMR styles
EMR_STYLES = ["epic", "cerner", "allscripts", "athena", "legacy"]


def _get_tenant_id() -> uuid.UUID:
    """Get tenant ID from query params or use default."""
    tenant_id = request.args.get("tenant_id")
    if tenant_id:
        try:
            return uuid.UUID(tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


def _get_style() -> str:
    """Get EMR style from query params or random."""
    style = request.args.get("style", "").lower()
    if style in EMR_STYLES:
        return style
    # Default to random selection
    return random.choice(EMR_STYLES)


def _get_all_patients(db, tenant_id: uuid.UUID) -> list:
    """Get all patients with their IDs and clinical data."""
    contexts = db.query(PatientContext).filter(
        PatientContext.tenant_id == tenant_id
    ).all()
    
    patients = []
    for ctx in contexts:
        snapshot = db.query(PatientSnapshot).filter(
            PatientSnapshot.patient_context_id == ctx.patient_context_id
        ).order_by(PatientSnapshot.snapshot_version.desc()).first()
        
        if not snapshot:
            continue
        
        patient_ids = db.query(PatientId).filter(
            PatientId.patient_context_id == ctx.patient_context_id
        ).all()
        
        mrn = next((pid.id_value for pid in patient_ids if pid.id_type == "mrn"), None)
        insurance_id = next((pid.id_value for pid in patient_ids if pid.id_type == "insurance"), None)
        
        mock_emr = db.query(MockEmrRecord).filter(
            MockEmrRecord.patient_context_id == ctx.patient_context_id
        ).first()
        
        patients.append({
            "patient_key": ctx.patient_key,
            "patient_context_id": str(ctx.patient_context_id),
            "display_name": snapshot.display_name,
            "dob": snapshot.dob.strftime("%m/%d/%Y") if snapshot.dob else "",
            "id_masked": snapshot.id_masked,
            "mrn": mrn,
            "insurance_id": insurance_id,
            "verified": snapshot.verified,
            "data_complete": snapshot.data_complete,
            "critical_alert": snapshot.critical_alert,
            "needs_review": snapshot.needs_review,
            "warnings": snapshot.warnings or [],
            "all_ids": [pid.to_dict() for pid in patient_ids],
            "clinical": mock_emr.to_dict() if mock_emr else {},
        })
    
    return patients


@bp.route("/", methods=["GET"])
def mock_emr_page():
    """Render the mock EMR HTML page with selected style."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    style = _get_style()
    
    patients = _get_all_patients(db, tenant_id)
    
    # Select renderer based on style
    renderers = {
        "epic": _render_epic_style,
        "cerner": _render_cerner_style,
        "allscripts": _render_allscripts_style,
        "athena": _render_athena_style,
        "legacy": _render_legacy_style,
    }
    
    renderer = renderers.get(style, _render_epic_style)
    html = renderer(patients, style)
    
    return Response(html, mimetype="text/html")


@bp.route("/api/lookup", methods=["GET"])
def lookup_patient():
    """Look up a patient by ID."""
    db = get_db_session()
    
    id_type = request.args.get("id_type", "").strip()
    id_value = request.args.get("id_value", "").strip()
    
    if not id_type or not id_value:
        return jsonify({"error": "id_type and id_value are required"}), 400
    
    patient_id = db.query(PatientId).filter(
        PatientId.id_type == id_type,
        PatientId.id_value == id_value,
    ).first()
    
    if not patient_id:
        return jsonify({"found": False, "id_type": id_type, "id_value": id_value})
    
    context = db.query(PatientContext).filter(
        PatientContext.patient_context_id == patient_id.patient_context_id
    ).first()
    
    if not context:
        return jsonify({"found": False, "id_type": id_type, "id_value": id_value})
    
    snapshot = db.query(PatientSnapshot).filter(
        PatientSnapshot.patient_context_id == context.patient_context_id
    ).order_by(PatientSnapshot.snapshot_version.desc()).first()
    
    all_ids = db.query(PatientId).filter(
        PatientId.patient_context_id == context.patient_context_id
    ).all()
    
    return jsonify({
        "found": True,
        "id_type": id_type,
        "id_value": id_value,
        "patient_key": context.patient_key,
        "patient_context_id": str(context.patient_context_id),
        "display_name": snapshot.display_name if snapshot else None,
        "all_ids": [pid.to_dict() for pid in all_ids],
    })


@bp.route("/api/patients", methods=["GET"])
def list_patients():
    """List all patients with their data."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    patients = _get_all_patients(db, tenant_id)
    return jsonify({"ok": True, "count": len(patients), "patients": patients})


# =============================================================================
# EPIC-STYLE RENDERER (Blue theme, sidebar navigation)
# =============================================================================

def _render_epic_style(patients: list, style: str) -> str:
    """Render Epic-like EMR with blue theme and sidebar."""
    
    patient_items = []
    for p in patients:
        alert_class = "epic-alert" if p["critical_alert"] else ""
        patient_items.append(f'''
        <div class="epic-patient-item {alert_class}" 
             data-patient-mrn="{p['mrn'] or ''}"
             data-patient-name="{p['display_name'] or ''}"
             onclick="selectPatient(this, '{p['patient_key']}')">
            <div class="epic-patient-name">{p['display_name'] or 'Unknown'}</div>
            <div class="epic-patient-mrn">{p['mrn'] or 'N/A'}</div>
        </div>
        ''')
    
    detail_panels = _build_detail_panels(patients, "epic")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EpicCare - Electronic Health Record</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #e8f4fc; }}
        
        .epic-header {{
            background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
            color: white;
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .epic-logo {{ font-size: 24px; font-weight: bold; letter-spacing: 1px; }}
        .epic-header-info {{ font-size: 12px; opacity: 0.8; }}
        
        .epic-container {{ display: flex; height: calc(100vh - 52px); }}
        
        .epic-sidebar {{
            width: 280px;
            background: white;
            border-right: 1px solid #ccd9e8;
            overflow-y: auto;
        }}
        .epic-sidebar-header {{
            padding: 16px;
            background: #f0f7ff;
            border-bottom: 1px solid #ccd9e8;
            font-weight: 600;
            color: #1e3a5f;
        }}
        .epic-patient-item {{
            padding: 12px 16px;
            border-bottom: 1px solid #e8f0f8;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .epic-patient-item:hover {{ background: #f0f7ff; }}
        .epic-patient-item.active {{ background: #d0e8ff; border-left: 4px solid #2c5282; }}
        .epic-patient-item.epic-alert {{ border-left: 4px solid #dc3545; }}
        .epic-patient-name {{ font-weight: 500; color: #1e3a5f; }}
        .epic-patient-mrn {{ font-size: 12px; color: #6b7c93; font-family: monospace; }}
        
        .epic-main {{ flex: 1; padding: 24px; overflow-y: auto; }}
        .epic-detail {{ background: white; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
        .epic-detail-header {{ padding: 20px; background: #f0f7ff; border-radius: 8px 8px 0 0; border-bottom: 1px solid #ccd9e8; }}
        .epic-detail-header h2 {{ color: #1e3a5f; margin-bottom: 8px; }}
        .epic-section {{ padding: 20px; border-bottom: 1px solid #e8f0f8; }}
        .epic-section h3 {{ color: #2c5282; font-size: 14px; text-transform: uppercase; margin-bottom: 12px; }}
        .epic-badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 500; margin-right: 6px; }}
        .epic-badge-danger {{ background: #fce4e4; color: #c53030; }}
        .epic-badge-warning {{ background: #fef3c7; color: #b45309; }}
        .epic-badge-success {{ background: #d1fae5; color: #065f46; }}
        .epic-vitals {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
        .epic-vital {{ background: #f8fafc; padding: 12px; border-radius: 6px; text-align: center; }}
        .epic-vital-label {{ font-size: 11px; color: #6b7c93; text-transform: uppercase; }}
        .epic-vital-value {{ font-size: 18px; font-weight: 600; color: #1e3a5f; }}
        
        .epic-style-badge {{ position: fixed; bottom: 16px; right: 16px; background: #2c5282; color: white; padding: 8px 16px; border-radius: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <header class="epic-header">
        <div class="epic-logo">EpicCare</div>
        <div class="epic-header-info">Style: {style} | Patients: {len(patients)}</div>
    </header>
    <div class="epic-container">
        <aside class="epic-sidebar">
            <div class="epic-sidebar-header">Patient List</div>
            {"".join(patient_items)}
        </aside>
        <main class="epic-main">
            <div id="patient-detail">{detail_panels}</div>
        </main>
    </div>
    <div class="epic-style-badge">EMR Style: Epic</div>
    {_get_common_script()}
</body>
</html>'''


# =============================================================================
# CERNER-STYLE RENDERER (Orange theme, tabbed interface)
# =============================================================================

def _render_cerner_style(patients: list, style: str) -> str:
    """Render Cerner-like EMR with orange theme and tabs."""
    
    patient_rows = []
    for p in patients:
        status_icon = "🔴" if p["critical_alert"] else ("🟡" if p["needs_review"] else "🟢")
        patient_rows.append(f'''
        <tr class="cerner-row" 
            data-cerner-mrn="{p['mrn'] or ''}"
            data-cerner-patient="{p['display_name'] or ''}"
            onclick="selectPatient(this, '{p['patient_key']}')">
            <td>{status_icon}</td>
            <td class="cerner-name">{p['display_name'] or 'Unknown'}</td>
            <td class="cerner-id">{p['mrn'] or 'N/A'}</td>
            <td>{p['dob'] or 'N/A'}</td>
        </tr>
        ''')
    
    detail_panels = _build_detail_panels(patients, "cerner")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cerner PowerChart</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, Helvetica, sans-serif; background: #f5f5f5; }}
        
        .cerner-header {{
            background: linear-gradient(to right, #d35400, #e67e22);
            color: white;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .cerner-logo {{ font-size: 20px; font-weight: bold; }}
        .cerner-tabs {{
            background: #2c3e50;
            padding: 0 20px;
            display: flex;
            gap: 4px;
        }}
        .cerner-tab {{
            padding: 12px 20px;
            color: #bdc3c7;
            cursor: pointer;
            border-bottom: 3px solid transparent;
        }}
        .cerner-tab.active {{ color: white; border-bottom-color: #e67e22; background: #34495e; }}
        
        .cerner-container {{ display: flex; height: calc(100vh - 90px); }}
        .cerner-list {{ width: 50%; background: white; border-right: 2px solid #e67e22; overflow-y: auto; }}
        .cerner-table {{ width: 100%; border-collapse: collapse; }}
        .cerner-table th {{ background: #ecf0f1; padding: 12px; text-align: left; font-size: 12px; text-transform: uppercase; color: #7f8c8d; border-bottom: 2px solid #bdc3c7; }}
        .cerner-row {{ cursor: pointer; }}
        .cerner-row:hover {{ background: #fef6e4; }}
        .cerner-row.active {{ background: #fdebd0; }}
        .cerner-row td {{ padding: 10px 12px; border-bottom: 1px solid #ecf0f1; }}
        .cerner-name {{ font-weight: 500; }}
        .cerner-id {{ font-family: monospace; color: #7f8c8d; }}
        
        .cerner-detail {{ flex: 1; padding: 20px; overflow-y: auto; }}
        .cerner-card {{ background: white; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 16px; }}
        .cerner-card-header {{ padding: 12px 16px; background: #fef6e4; border-bottom: 1px solid #f0e0c0; font-weight: 600; color: #d35400; }}
        .cerner-card-body {{ padding: 16px; }}
        .cerner-alert {{ color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px; margin-left: 8px; }}
        .cerner-alert-red {{ background: #e74c3c; }}
        .cerner-alert-yellow {{ background: #f39c12; }}
        
        .cerner-style-badge {{ position: fixed; bottom: 16px; right: 16px; background: #e67e22; color: white; padding: 8px 16px; border-radius: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <header class="cerner-header">
        <div class="cerner-logo">Cerner PowerChart</div>
        <div>Style: {style} | Records: {len(patients)}</div>
    </header>
    <nav class="cerner-tabs">
        <div class="cerner-tab active">Patient List</div>
        <div class="cerner-tab">Orders</div>
        <div class="cerner-tab">Results</div>
        <div class="cerner-tab">Notes</div>
    </nav>
    <div class="cerner-container">
        <div class="cerner-list">
            <table class="cerner-table">
                <thead><tr><th></th><th>Patient Name</th><th>MRN</th><th>DOB</th></tr></thead>
                <tbody>{"".join(patient_rows)}</tbody>
            </table>
        </div>
        <div class="cerner-detail" id="patient-detail">{detail_panels}</div>
    </div>
    <div class="cerner-style-badge">EMR Style: Cerner</div>
    {_get_common_script()}
</body>
</html>'''


# =============================================================================
# ALLSCRIPTS-STYLE RENDERER (Green theme, traditional layout)
# =============================================================================

def _render_allscripts_style(patients: list, style: str) -> str:
    """Render Allscripts-like EMR with green theme."""
    
    patient_options = []
    for p in patients:
        patient_options.append(f'''
        <option value="{p['patient_key']}" 
                data-allscripts-id="{p['mrn'] or ''}"
                data-allscripts-name="{p['display_name'] or ''}">
            {p['display_name'] or 'Unknown'} - {p['mrn'] or 'N/A'}
        </option>
        ''')
    
    detail_panels = _build_detail_panels(patients, "allscripts")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Allscripts Professional EHR</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Verdana, Geneva, sans-serif; background: #f0f5f0; font-size: 13px; }}
        
        .allscripts-header {{
            background: linear-gradient(to bottom, #2e7d32, #1b5e20);
            color: white;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        .allscripts-logo {{ font-weight: bold; font-size: 16px; }}
        .allscripts-menu {{ display: flex; gap: 2px; }}
        .allscripts-menu-item {{ padding: 6px 12px; background: rgba(255,255,255,0.1); cursor: pointer; font-size: 12px; }}
        .allscripts-menu-item:hover {{ background: rgba(255,255,255,0.2); }}
        
        .allscripts-toolbar {{
            background: #e8f5e9;
            padding: 8px 16px;
            border-bottom: 1px solid #a5d6a7;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .allscripts-toolbar label {{ font-weight: bold; color: #1b5e20; }}
        .allscripts-select {{
            padding: 6px 12px;
            border: 1px solid #a5d6a7;
            border-radius: 3px;
            min-width: 300px;
        }}
        
        .allscripts-main {{ display: flex; height: calc(100vh - 80px); }}
        .allscripts-nav {{
            width: 180px;
            background: #c8e6c9;
            border-right: 1px solid #a5d6a7;
        }}
        .allscripts-nav-item {{
            padding: 10px 12px;
            border-bottom: 1px solid #a5d6a7;
            cursor: pointer;
            font-size: 12px;
        }}
        .allscripts-nav-item:hover {{ background: #b9dbb9; }}
        .allscripts-nav-item.active {{ background: #81c784; color: white; }}
        
        .allscripts-content {{ flex: 1; padding: 16px; overflow-y: auto; background: white; }}
        .allscripts-fieldset {{
            border: 1px solid #a5d6a7;
            border-radius: 4px;
            margin-bottom: 16px;
            padding: 12px;
        }}
        .allscripts-fieldset legend {{
            background: #2e7d32;
            color: white;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .allscripts-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }}
        .allscripts-field {{ display: flex; gap: 8px; }}
        .allscripts-field-label {{ font-weight: bold; color: #1b5e20; min-width: 100px; }}
        .allscripts-alert {{ background: #ffcdd2; border: 1px solid #ef5350; padding: 8px; margin-bottom: 12px; border-radius: 3px; color: #c62828; }}
        
        .allscripts-style-badge {{ position: fixed; bottom: 16px; right: 16px; background: #2e7d32; color: white; padding: 8px 16px; border-radius: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <header class="allscripts-header">
        <div class="allscripts-logo">Allscripts Professional</div>
        <nav class="allscripts-menu">
            <div class="allscripts-menu-item">Chart</div>
            <div class="allscripts-menu-item">Schedule</div>
            <div class="allscripts-menu-item">Messages</div>
            <div class="allscripts-menu-item">Reports</div>
        </nav>
    </header>
    <div class="allscripts-toolbar">
        <label>Select Patient:</label>
        <select class="allscripts-select" id="patient-select" onchange="selectPatientFromDropdown(this)">
            <option value="">-- Choose Patient --</option>
            {"".join(patient_options)}
        </select>
        <span>Total: {len(patients)} patients</span>
    </div>
    <div class="allscripts-main">
        <nav class="allscripts-nav">
            <div class="allscripts-nav-item active">Demographics</div>
            <div class="allscripts-nav-item">Problems</div>
            <div class="allscripts-nav-item">Medications</div>
            <div class="allscripts-nav-item">Allergies</div>
            <div class="allscripts-nav-item">Vitals</div>
            <div class="allscripts-nav-item">Lab Results</div>
        </nav>
        <div class="allscripts-content" id="patient-detail">{detail_panels}</div>
    </div>
    <div class="allscripts-style-badge">EMR Style: Allscripts</div>
    {_get_common_script()}
    <script>
        function selectPatientFromDropdown(sel) {{
            const opt = sel.options[sel.selectedIndex];
            const key = sel.value;
            if (key) {{
                document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
                const panel = document.getElementById('detail-' + key);
                if (panel) panel.style.display = 'block';
            }}
        }}
    </script>
</body>
</html>'''


# =============================================================================
# ATHENA-STYLE RENDERER (Purple theme, card-based)
# =============================================================================

def _render_athena_style(patients: list, style: str) -> str:
    """Render Athena-like EMR with purple card-based layout."""
    
    patient_cards = []
    for p in patients:
        alert_badge = '<span class="athena-critical">CRITICAL</span>' if p["critical_alert"] else ""
        patient_cards.append(f'''
        <div class="athena-patient-card" 
             data-athena-record-number="{p['mrn'] or ''}"
             data-athena-full-name="{p['display_name'] or ''}"
             onclick="selectPatient(this, '{p['patient_key']}')">
            <div class="athena-card-top">
                <span class="athena-name">{p['display_name'] or 'Unknown'}</span>
                {alert_badge}
            </div>
            <div class="athena-card-bottom">
                <span>MRN: {p['mrn'] or 'N/A'}</span>
                <span>DOB: {p['dob'] or 'N/A'}</span>
            </div>
        </div>
        ''')
    
    detail_panels = _build_detail_panels(patients, "athena")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>athenaOne - Patient Portal</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #f8f5ff; }}
        
        .athena-header {{
            background: linear-gradient(135deg, #6b21a8 0%, #9333ea 100%);
            color: white;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .athena-logo {{ font-size: 22px; font-weight: 300; letter-spacing: 2px; }}
        .athena-logo span {{ font-weight: 600; }}
        
        .athena-search {{
            padding: 16px 24px;
            background: white;
            border-bottom: 1px solid #e9d5ff;
        }}
        .athena-search input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e9d5ff;
            border-radius: 25px;
            font-size: 14px;
            outline: none;
        }}
        .athena-search input:focus {{ border-color: #9333ea; }}
        
        .athena-container {{ display: flex; height: calc(100vh - 120px); }}
        .athena-patients {{
            width: 320px;
            background: white;
            border-right: 1px solid #e9d5ff;
            padding: 16px;
            overflow-y: auto;
        }}
        .athena-patient-card {{
            background: #faf5ff;
            border: 1px solid #e9d5ff;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 12px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .athena-patient-card:hover {{ border-color: #9333ea; box-shadow: 0 4px 12px rgba(147, 51, 234, 0.15); }}
        .athena-patient-card.active {{ background: #ede9fe; border-color: #9333ea; }}
        .athena-card-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .athena-name {{ font-weight: 600; color: #581c87; }}
        .athena-critical {{ background: #dc2626; color: white; padding: 2px 8px; border-radius: 10px; font-size: 10px; }}
        .athena-card-bottom {{ font-size: 12px; color: #7c3aed; display: flex; justify-content: space-between; }}
        
        .athena-detail {{ flex: 1; padding: 24px; overflow-y: auto; }}
        .athena-detail-card {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(107, 33, 168, 0.1);
            overflow: hidden;
        }}
        .athena-detail-header {{
            background: linear-gradient(135deg, #7c3aed 0%, #9333ea 100%);
            color: white;
            padding: 24px;
        }}
        .athena-detail-header h2 {{ font-weight: 400; margin-bottom: 8px; }}
        .athena-section {{ padding: 20px 24px; border-bottom: 1px solid #f3e8ff; }}
        .athena-section h3 {{ color: #7c3aed; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }}
        .athena-pill {{ display: inline-block; background: #f3e8ff; color: #7c3aed; padding: 6px 14px; border-radius: 20px; margin: 4px; font-size: 13px; }}
        .athena-pill-danger {{ background: #fee2e2; color: #dc2626; }}
        
        .athena-style-badge {{ position: fixed; bottom: 16px; right: 16px; background: #9333ea; color: white; padding: 8px 16px; border-radius: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <header class="athena-header">
        <div class="athena-logo">athena<span>One</span></div>
        <div>Style: {style} | {len(patients)} Records</div>
    </header>
    <div class="athena-search">
        <input type="text" placeholder="Search patients by name or MRN..." id="athena-search" onkeyup="filterPatients(this.value)">
    </div>
    <div class="athena-container">
        <div class="athena-patients" id="patient-list">
            {"".join(patient_cards)}
        </div>
        <div class="athena-detail" id="patient-detail">{detail_panels}</div>
    </div>
    <div class="athena-style-badge">EMR Style: Athena</div>
    {_get_common_script()}
    <script>
        function filterPatients(query) {{
            const q = query.toLowerCase();
            document.querySelectorAll('.athena-patient-card').forEach(card => {{
                const name = card.dataset.athenaFullName.toLowerCase();
                const mrn = card.dataset.athenaRecordNumber.toLowerCase();
                card.style.display = (name.includes(q) || mrn.includes(q)) ? 'block' : 'none';
            }});
        }}
    </script>
</body>
</html>'''


# =============================================================================
# LEGACY-STYLE RENDERER (Classic minimal table)
# =============================================================================

def _render_legacy_style(patients: list, style: str) -> str:
    """Render legacy/classic minimal EMR layout."""
    
    patient_rows = []
    for i, p in enumerate(patients):
        bg = "#fff" if i % 2 == 0 else "#f9f9f9"
        alert = " [!]" if p["critical_alert"] else ""
        patient_rows.append(f'''
        <tr style="background:{bg}" 
            id="row-{p['patient_key']}"
            data-id="{p['mrn'] or ''}"
            data-name="{p['display_name'] or ''}"
            onclick="selectPatient(this, '{p['patient_key']}')">
            <td><input type="radio" name="patient" value="{p['patient_key']}"></td>
            <td><b>{p['display_name'] or 'Unknown'}</b>{alert}</td>
            <td><code>{p['mrn'] or 'N/A'}</code></td>
            <td>{p['dob'] or 'N/A'}</td>
            <td>{'Yes' if p['verified'] else 'No'}</td>
        </tr>
        ''')
    
    detail_panels = _build_detail_panels(patients, "legacy")
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Medical Records System v2.1</title>
    <style>
        body {{ font-family: "Courier New", monospace; font-size: 12px; margin: 0; padding: 0; background: #c0c0c0; }}
        .legacy-header {{ background: #000080; color: white; padding: 4px 8px; font-weight: bold; }}
        .legacy-menubar {{ background: #d4d0c8; padding: 2px; border-bottom: 2px solid #808080; }}
        .legacy-menu {{ display: inline-block; padding: 2px 8px; cursor: pointer; }}
        .legacy-menu:hover {{ background: #000080; color: white; }}
        
        .legacy-container {{ display: flex; height: calc(100vh - 50px); }}
        .legacy-list {{
            width: 50%;
            background: white;
            border: 2px inset #d4d0c8;
            overflow-y: scroll;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #000080; color: white; padding: 4px 8px; text-align: left; position: sticky; top: 0; }}
        td {{ padding: 4px 8px; border-bottom: 1px solid #d4d0c8; cursor: pointer; }}
        tr:hover {{ background: #ffffe0 !important; }}
        tr.selected {{ background: #000080 !important; color: white; }}
        
        .legacy-detail {{
            flex: 1;
            background: white;
            border: 2px inset #d4d0c8;
            margin-left: 4px;
            padding: 8px;
            overflow-y: scroll;
        }}
        .legacy-section {{ border: 1px solid #808080; margin-bottom: 8px; }}
        .legacy-section-title {{ background: #d4d0c8; padding: 2px 6px; font-weight: bold; border-bottom: 1px solid #808080; }}
        .legacy-section-body {{ padding: 6px; }}
        .legacy-field {{ margin-bottom: 4px; }}
        .legacy-label {{ display: inline-block; width: 120px; font-weight: bold; }}
        
        .legacy-style-badge {{ position: fixed; bottom: 8px; right: 8px; background: #808080; color: white; padding: 4px 12px; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="legacy-header">MEDICAL RECORDS SYSTEM v2.1 - {len(patients)} Records Loaded</div>
    <div class="legacy-menubar">
        <span class="legacy-menu">File</span>
        <span class="legacy-menu">Edit</span>
        <span class="legacy-menu">View</span>
        <span class="legacy-menu">Patient</span>
        <span class="legacy-menu">Reports</span>
        <span class="legacy-menu">Help</span>
    </div>
    <div class="legacy-container">
        <div class="legacy-list">
            <table>
                <thead><tr><th></th><th>Patient Name</th><th>MRN</th><th>DOB</th><th>Verified</th></tr></thead>
                <tbody>{"".join(patient_rows)}</tbody>
            </table>
        </div>
        <div class="legacy-detail" id="patient-detail">{detail_panels}</div>
    </div>
    <div class="legacy-style-badge">Style: Legacy</div>
    {_get_common_script()}
</body>
</html>'''


# =============================================================================
# SHARED HELPERS
# =============================================================================

def _build_detail_panels(patients: list, style: str) -> str:
    """Build detail panels for all patients."""
    panels = []
    
    for p in patients:
        clinical = p.get("clinical", {})
        
        # Allergies
        allergies = clinical.get("allergies", [])
        if style == "athena":
            allergy_html = " ".join([f'<span class="athena-pill athena-pill-danger">{a}</span>' for a in allergies]) if allergies else '<span class="athena-pill">None reported</span>'
        elif style == "epic":
            allergy_html = " ".join([f'<span class="epic-badge epic-badge-danger">{a}</span>' for a in allergies]) if allergies else "None reported"
        else:
            allergy_html = ", ".join(allergies) if allergies else "None reported"
        
        # Medications
        meds = clinical.get("medications", [])
        if meds:
            med_list = "<ul>" + "".join([f'<li>{m["name"]} {m["dose"]} - {m["frequency"]}</li>' for m in meds]) + "</ul>"
        else:
            med_list = "No current medications"
        
        # Vitals
        vitals = clinical.get("vitals", {})
        if style == "epic":
            vitals_html = f'''
            <div class="epic-vitals">
                <div class="epic-vital"><div class="epic-vital-label">BP</div><div class="epic-vital-value">{vitals.get("bp", "N/A")}</div></div>
                <div class="epic-vital"><div class="epic-vital-label">HR</div><div class="epic-vital-value">{vitals.get("hr", "N/A")}</div></div>
                <div class="epic-vital"><div class="epic-vital-label">Temp</div><div class="epic-vital-value">{vitals.get("temp", "N/A")}°F</div></div>
                <div class="epic-vital"><div class="epic-vital-label">Weight</div><div class="epic-vital-value">{vitals.get("weight_lbs", "N/A")} lbs</div></div>
            </div>
            '''
        else:
            vitals_html = f'BP: {vitals.get("bp", "N/A")} | HR: {vitals.get("hr", "N/A")} | Temp: {vitals.get("temp", "N/A")}°F | Wt: {vitals.get("weight_lbs", "N/A")} lbs'
        
        # Emergency contact
        ec = clinical.get("emergency_contact", {})
        ec_html = f'{ec.get("name", "N/A")} ({ec.get("relation", "")}) - {ec.get("phone", "N/A")}' if ec else "Not provided"
        
        # Build panel based on style
        if style == "epic":
            panel = f'''
            <div class="detail-panel epic-detail" id="detail-{p['patient_key']}" style="display:none">
                <div class="epic-detail-header">
                    <h2>{p['display_name'] or 'Unknown'}</h2>
                    <div>MRN: {p['mrn'] or 'N/A'} | DOB: {p['dob'] or 'N/A'} | Blood Type: {clinical.get('blood_type', 'N/A')}</div>
                </div>
                <div class="epic-section"><h3>Allergies</h3>{allergy_html}</div>
                <div class="epic-section"><h3>Vitals</h3>{vitals_html}</div>
                <div class="epic-section"><h3>Medications</h3>{med_list}</div>
                <div class="epic-section"><h3>Emergency Contact</h3>{ec_html}</div>
                <div class="epic-section"><h3>Primary Care Provider</h3>{clinical.get('primary_care_provider', 'N/A')}</div>
            </div>
            '''
        elif style == "cerner":
            panel = f'''
            <div class="detail-panel" id="detail-{p['patient_key']}" style="display:none">
                <div class="cerner-card">
                    <div class="cerner-card-header">Patient: {p['display_name'] or 'Unknown'}
                        {'<span class="cerner-alert cerner-alert-red">ALERT</span>' if p['critical_alert'] else ''}
                    </div>
                    <div class="cerner-card-body">
                        <p><b>MRN:</b> {p['mrn'] or 'N/A'} | <b>DOB:</b> {p['dob'] or 'N/A'} | <b>Blood Type:</b> {clinical.get('blood_type', 'N/A')}</p>
                    </div>
                </div>
                <div class="cerner-card"><div class="cerner-card-header">Allergies</div><div class="cerner-card-body">{allergy_html}</div></div>
                <div class="cerner-card"><div class="cerner-card-header">Vitals</div><div class="cerner-card-body">{vitals_html}</div></div>
                <div class="cerner-card"><div class="cerner-card-header">Medications</div><div class="cerner-card-body">{med_list}</div></div>
                <div class="cerner-card"><div class="cerner-card-header">Emergency Contact</div><div class="cerner-card-body">{ec_html}</div></div>
            </div>
            '''
        elif style == "allscripts":
            panel = f'''
            <div class="detail-panel" id="detail-{p['patient_key']}" style="display:none">
                {f'<div class="allscripts-alert">⚠️ CRITICAL ALERT - Review immediately</div>' if p['critical_alert'] else ''}
                <fieldset class="allscripts-fieldset">
                    <legend>Demographics</legend>
                    <div class="allscripts-grid">
                        <div class="allscripts-field"><span class="allscripts-field-label">Name:</span> {p['display_name'] or 'Unknown'}</div>
                        <div class="allscripts-field"><span class="allscripts-field-label">MRN:</span> {p['mrn'] or 'N/A'}</div>
                        <div class="allscripts-field"><span class="allscripts-field-label">DOB:</span> {p['dob'] or 'N/A'}</div>
                        <div class="allscripts-field"><span class="allscripts-field-label">Blood Type:</span> {clinical.get('blood_type', 'N/A')}</div>
                    </div>
                </fieldset>
                <fieldset class="allscripts-fieldset"><legend>Allergies</legend>{allergy_html}</fieldset>
                <fieldset class="allscripts-fieldset"><legend>Vitals</legend>{vitals_html}</fieldset>
                <fieldset class="allscripts-fieldset"><legend>Medications</legend>{med_list}</fieldset>
                <fieldset class="allscripts-fieldset"><legend>Emergency Contact</legend>{ec_html}</fieldset>
            </div>
            '''
        elif style == "athena":
            panel = f'''
            <div class="detail-panel athena-detail-card" id="detail-{p['patient_key']}" style="display:none">
                <div class="athena-detail-header">
                    <h2>{p['display_name'] or 'Unknown'}</h2>
                    <div>MRN: {p['mrn'] or 'N/A'} • DOB: {p['dob'] or 'N/A'} • Blood Type: {clinical.get('blood_type', 'N/A')}</div>
                </div>
                <div class="athena-section"><h3>Allergies</h3>{allergy_html}</div>
                <div class="athena-section"><h3>Current Vitals</h3>{vitals_html}</div>
                <div class="athena-section"><h3>Medications</h3>{med_list}</div>
                <div class="athena-section"><h3>Emergency Contact</h3>{ec_html}</div>
                <div class="athena-section"><h3>Care Team</h3>Primary: {clinical.get('primary_care_provider', 'N/A')}</div>
            </div>
            '''
        else:  # legacy
            panel = f'''
            <div class="detail-panel" id="detail-{p['patient_key']}" style="display:none">
                <div class="legacy-section">
                    <div class="legacy-section-title">PATIENT INFORMATION</div>
                    <div class="legacy-section-body">
                        <div class="legacy-field"><span class="legacy-label">Name:</span> {p['display_name'] or 'Unknown'}</div>
                        <div class="legacy-field"><span class="legacy-label">MRN:</span> {p['mrn'] or 'N/A'}</div>
                        <div class="legacy-field"><span class="legacy-label">DOB:</span> {p['dob'] or 'N/A'}</div>
                        <div class="legacy-field"><span class="legacy-label">Blood Type:</span> {clinical.get('blood_type', 'N/A')}</div>
                    </div>
                </div>
                <div class="legacy-section"><div class="legacy-section-title">ALLERGIES</div><div class="legacy-section-body">{allergy_html}</div></div>
                <div class="legacy-section"><div class="legacy-section-title">VITALS</div><div class="legacy-section-body">{vitals_html}</div></div>
                <div class="legacy-section"><div class="legacy-section-title">MEDICATIONS</div><div class="legacy-section-body">{med_list}</div></div>
                <div class="legacy-section"><div class="legacy-section-title">EMERGENCY CONTACT</div><div class="legacy-section-body">{ec_html}</div></div>
            </div>
            '''
        
        panels.append(panel)
    
    return "\n".join(panels)


def _get_common_script() -> str:
    """Return common JavaScript for patient selection."""
    return '''
    <script>
        let activeElement = null;
        
        function selectPatient(element, patientKey) {
            // Remove active class from previous
            if (activeElement) {
                activeElement.classList.remove('active', 'selected');
            }
            
            // Add active class to new element
            element.classList.add('active', 'selected');
            activeElement = element;
            
            // Hide all detail panels
            document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
            
            // Show selected detail panel
            const detail = document.getElementById('detail-' + patientKey);
            if (detail) {
                detail.style.display = 'block';
            }
            
            // Log for debugging
            console.log('[Mock EMR] Selected patient:', {
                patientKey: patientKey,
                mrn: element.dataset.patientMrn || element.dataset.cernerMrn || element.dataset.allscriptsId || element.dataset.athenaRecordNumber || element.dataset.id,
                name: element.dataset.patientName || element.dataset.cernerPatient || element.dataset.allscriptsName || element.dataset.athenaFullName || element.dataset.name
            });
        }
        
        // Auto-select first patient on load
        document.addEventListener('DOMContentLoaded', function() {
            const firstPatient = document.querySelector('[onclick^="selectPatient"]');
            if (firstPatient) {
                const match = firstPatient.getAttribute('onclick').match(/'([^']+)'/);
                if (match) {
                    selectPatient(firstPatient, match[1]);
                }
            }
        });
    </script>
    '''
