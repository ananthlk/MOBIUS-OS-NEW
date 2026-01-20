"""
Mock CRM/Scheduler page for testing the Mini extension.

Displays appointment scheduling, intake status, and reminder management
in multiple CRM-style layouts. The Mini extension must dynamically adapt
to different HTML structures.

Supported styles (via ?style= parameter):
- modern: Clean, card-based modern design
- classic: Traditional enterprise CRM look
- healthcare_first: Healthcare-specific with clinical colors
- efficiency: Compact, data-dense layout for power users
- random: Randomly selects a style (default)
"""

import uuid
import random
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, Response
from sqlalchemy import and_, or_

from app.db.postgres import get_db_session
from app.models.patient import PatientContext, PatientSnapshot
from app.models.patient_ids import PatientId
from app.models.appointment import Appointment, AppointmentReminder
from app.models.intake import IntakeForm, InsuranceVerification, IntakeChecklist

bp = Blueprint("mock_crm", __name__, url_prefix="/mock-crm")

# Default tenant ID for development
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Available CRM styles
CRM_STYLES = ["modern", "classic", "healthcare_first", "efficiency"]


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
    """Get CRM style from query params or random."""
    style = request.args.get("style", "").lower()
    if style in CRM_STYLES:
        return style
    return random.choice(CRM_STYLES)


def _get_today_appointments(db, tenant_id: uuid.UUID) -> list:
    """Get today's appointments with patient data."""
    today = date.today()
    
    appointments = db.query(Appointment).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.scheduled_date == today
        )
    ).order_by(Appointment.scheduled_time).all()
    
    result = []
    for appt in appointments:
        # Get patient info
        ctx = db.query(PatientContext).filter(
            PatientContext.patient_context_id == appt.patient_context_id
        ).first()
        
        snapshot = None
        mrn = None
        if ctx:
            snapshot = db.query(PatientSnapshot).filter(
                PatientSnapshot.patient_context_id == ctx.patient_context_id
            ).order_by(PatientSnapshot.snapshot_version.desc()).first()
            
            patient_ids = db.query(PatientId).filter(
                PatientId.patient_context_id == ctx.patient_context_id
            ).all()
            mrn = next((pid.id_value for pid in patient_ids if pid.id_type == "mrn"), None)
        
        # Get checklist status
        checklist = db.query(IntakeChecklist).filter(
            IntakeChecklist.appointment_id == appt.appointment_id
        ).first()
        
        result.append({
            "appointment_id": str(appt.appointment_id),
            "patient_context_id": str(appt.patient_context_id),
            "patient_name": snapshot.display_name if snapshot else "Unknown",
            "mrn": mrn,
            "dob": snapshot.dob.strftime("%m/%d/%Y") if snapshot and snapshot.dob else "",
            "scheduled_time": appt.scheduled_time.strftime("%I:%M %p") if appt.scheduled_time else "",
            "appointment_type": appt.appointment_type,
            "status": appt.status,
            "provider_name": appt.provider_name,
            "location": appt.location,
            "room": appt.room,
            "visit_reason": appt.visit_reason,
            "checked_in_at": appt.checked_in_at.strftime("%I:%M %p") if appt.checked_in_at else None,
            "wait_time_minutes": appt.wait_time_minutes,
            "needs_confirmation": appt.needs_confirmation,
            "needs_insurance_verification": appt.needs_insurance_verification,
            "intake_status": checklist.status if checklist else "unknown",
            "intake_items_complete": checklist.completed_items if checklist else 0,
            "intake_items_total": checklist.total_items if checklist else 8,
        })
    
    return result


def _get_pending_reminders(db, tenant_id: uuid.UUID) -> list:
    """Get pending reminders that need attention."""
    reminders = db.query(AppointmentReminder).join(
        Appointment, AppointmentReminder.appointment_id == Appointment.appointment_id
    ).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            AppointmentReminder.status.in_(["pending", "failed"])
        )
    ).order_by(AppointmentReminder.due_date).limit(20).all()
    
    result = []
    for rem in reminders:
        appt = db.query(Appointment).filter(
            Appointment.appointment_id == rem.appointment_id
        ).first()
        
        ctx = db.query(PatientContext).filter(
            PatientContext.patient_context_id == rem.patient_context_id
        ).first()
        
        snapshot = None
        if ctx:
            snapshot = db.query(PatientSnapshot).filter(
                PatientSnapshot.patient_context_id == ctx.patient_context_id
            ).order_by(PatientSnapshot.snapshot_version.desc()).first()
        
        result.append({
            "reminder_id": str(rem.reminder_id),
            "appointment_id": str(rem.appointment_id),
            "patient_context_id": str(rem.patient_context_id),
            "patient_name": snapshot.display_name if snapshot else "Unknown",
            "reminder_type": rem.reminder_type,
            "channel": rem.channel,
            "due_date": rem.due_date.strftime("%m/%d %I:%M %p") if rem.due_date else "",
            "status": rem.status,
            "attempt_count": rem.attempt_count,
            "appointment_date": appt.scheduled_date.strftime("%m/%d") if appt else "",
            "appointment_time": appt.scheduled_time.strftime("%I:%M %p") if appt and appt.scheduled_time else "",
        })
    
    return result


def _get_intake_queue(db, tenant_id: uuid.UUID) -> list:
    """Get patients with incomplete intake."""
    today = date.today()
    
    # Get appointments for today and tomorrow
    appointments = db.query(Appointment).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.scheduled_date >= today,
            Appointment.scheduled_date <= today + timedelta(days=1),
            Appointment.status.in_(["scheduled", "confirmed"])
        )
    ).order_by(Appointment.scheduled_time).all()
    
    result = []
    for appt in appointments:
        ctx = db.query(PatientContext).filter(
            PatientContext.patient_context_id == appt.patient_context_id
        ).first()
        
        snapshot = None
        mrn = None
        if ctx:
            snapshot = db.query(PatientSnapshot).filter(
                PatientSnapshot.patient_context_id == ctx.patient_context_id
            ).order_by(PatientSnapshot.snapshot_version.desc()).first()
            
            patient_ids = db.query(PatientId).filter(
                PatientId.patient_context_id == ctx.patient_context_id
            ).all()
            mrn = next((pid.id_value for pid in patient_ids if pid.id_type == "mrn"), None)
        
        # Get intake forms
        forms = db.query(IntakeForm).filter(
            IntakeForm.patient_context_id == appt.patient_context_id
        ).all()
        
        forms_complete = sum(1 for f in forms if f.status == "completed")
        forms_total = len(forms) if forms else 4  # Default expected forms
        
        # Get insurance verification
        verification = db.query(InsuranceVerification).filter(
            InsuranceVerification.appointment_id == appt.appointment_id
        ).first()
        
        # Get checklist
        checklist = db.query(IntakeChecklist).filter(
            IntakeChecklist.appointment_id == appt.appointment_id
        ).first()
        
        result.append({
            "appointment_id": str(appt.appointment_id),
            "patient_context_id": str(appt.patient_context_id),
            "patient_name": snapshot.display_name if snapshot else "Unknown",
            "mrn": mrn,
            "scheduled_date": appt.scheduled_date.strftime("%m/%d") if appt.scheduled_date else "",
            "scheduled_time": appt.scheduled_time.strftime("%I:%M %p") if appt.scheduled_time else "",
            "forms_complete": forms_complete,
            "forms_total": forms_total,
            "insurance_status": verification.status if verification else "pending",
            "insurance_eligible": verification.is_eligible if verification else None,
            "checklist_status": checklist.status if checklist else "incomplete",
            "checklist_items": checklist.completed_items if checklist else 0,
            "checklist_total": checklist.total_items if checklist else 8,
            "has_issues": checklist.has_issues if checklist else False,
        })
    
    return result


def _get_attention_items(db, tenant_id: uuid.UUID) -> dict:
    """Get counts of items needing attention."""
    today = date.today()
    
    # Pending pre-visit reminders
    pre_visit_count = db.query(AppointmentReminder).join(
        Appointment, AppointmentReminder.appointment_id == Appointment.appointment_id
    ).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            AppointmentReminder.reminder_type == "pre_visit",
            AppointmentReminder.status == "pending"
        )
    ).count()
    
    # Pending insurance verifications
    insurance_pending = db.query(InsuranceVerification).filter(
        and_(
            InsuranceVerification.tenant_id == tenant_id,
            InsuranceVerification.status == "pending"
        )
    ).count()
    
    # No-show follow-ups needed
    no_shows = db.query(Appointment).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.status == "no_show",
            Appointment.scheduled_date >= today - timedelta(days=7)
        )
    ).count()
    
    # Post-visit reminders pending
    post_visit_count = db.query(AppointmentReminder).join(
        Appointment, AppointmentReminder.appointment_id == Appointment.appointment_id
    ).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            AppointmentReminder.reminder_type == "post_visit",
            AppointmentReminder.status == "pending"
        )
    ).count()
    
    # Appointments needing confirmation
    needs_confirm = db.query(Appointment).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.scheduled_date >= today,
            Appointment.scheduled_date <= today + timedelta(days=3),
            Appointment.needs_confirmation == True
        )
    ).count()
    
    return {
        "pre_visit_reminders": pre_visit_count,
        "insurance_pending": insurance_pending,
        "no_show_followups": no_shows,
        "post_visit_reminders": post_visit_count,
        "needs_confirmation": needs_confirm,
    }


@bp.route("/", methods=["GET"])
def mock_crm_page():
    """Render the mock CRM HTML page with selected style."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    style = _get_style()
    
    appointments = _get_today_appointments(db, tenant_id)
    reminders = _get_pending_reminders(db, tenant_id)
    intake_queue = _get_intake_queue(db, tenant_id)
    attention = _get_attention_items(db, tenant_id)
    
    # Select renderer based on style
    renderers = {
        "modern": _render_modern_style,
        "classic": _render_classic_style,
        "healthcare_first": _render_healthcare_style,
        "efficiency": _render_efficiency_style,
    }
    
    renderer = renderers.get(style, _render_modern_style)
    html = renderer(appointments, reminders, intake_queue, attention, style)
    
    return Response(html, mimetype="text/html")


@bp.route("/api/appointments", methods=["GET"])
def list_appointments():
    """List appointments with optional date filter."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    date_str = request.args.get("date")
    if date_str:
        try:
            filter_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()
    
    appointments = db.query(Appointment).filter(
        and_(
            Appointment.tenant_id == tenant_id,
            Appointment.scheduled_date == filter_date
        )
    ).order_by(Appointment.scheduled_time).all()
    
    return jsonify({
        "ok": True,
        "date": filter_date.isoformat(),
        "count": len(appointments),
        "appointments": [a.to_dict() for a in appointments]
    })


@bp.route("/api/intake-queue", methods=["GET"])
def intake_queue():
    """Get patient intake queue."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    queue = _get_intake_queue(db, tenant_id)
    return jsonify({"ok": True, "count": len(queue), "queue": queue})


@bp.route("/api/reminders", methods=["GET"])
def list_reminders():
    """List pending reminders."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    reminders = _get_pending_reminders(db, tenant_id)
    return jsonify({"ok": True, "count": len(reminders), "reminders": reminders})


@bp.route("/api/reminder/<reminder_id>/complete", methods=["POST"])
def complete_reminder(reminder_id):
    """Mark a reminder as complete."""
    db = get_db_session()
    
    try:
        rem_uuid = uuid.UUID(reminder_id)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid reminder ID"}), 400
    
    reminder = db.query(AppointmentReminder).filter(
        AppointmentReminder.reminder_id == rem_uuid
    ).first()
    
    if not reminder:
        return jsonify({"ok": False, "error": "Reminder not found"}), 404
    
    reminder.status = "completed"
    reminder.completed_at = datetime.utcnow()
    db.commit()
    
    return jsonify({"ok": True, "reminder": reminder.to_dict()})


@bp.route("/api/checkin/<appointment_id>", methods=["POST"])
def checkin_patient(appointment_id):
    """Check in a patient for their appointment."""
    db = get_db_session()
    
    try:
        appt_uuid = uuid.UUID(appointment_id)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid appointment ID"}), 400
    
    appt = db.query(Appointment).filter(
        Appointment.appointment_id == appt_uuid
    ).first()
    
    if not appt:
        return jsonify({"ok": False, "error": "Appointment not found"}), 404
    
    appt.status = "checked_in"
    appt.checked_in_at = datetime.utcnow()
    db.commit()
    
    return jsonify({"ok": True, "appointment": appt.to_dict()})


# =============================================================================
# MODERN STYLE RENDERER (Clean, card-based design)
# =============================================================================

def _render_modern_style(appointments, reminders, intake_queue, attention, style):
    """Render modern card-based CRM layout."""
    
    # Build appointment cards
    appt_cards = []
    for appt in appointments:
        status_class = f"status-{appt['status'].replace('_', '-')}"
        badge_color = {
            "scheduled": "#3b82f6",
            "confirmed": "#10b981",
            "checked_in": "#8b5cf6",
            "in_progress": "#f59e0b",
            "completed": "#6b7280",
            "no_show": "#ef4444",
            "cancelled": "#9ca3af"
        }.get(appt['status'], "#6b7280")
        
        intake_pct = int((appt['intake_items_complete'] / appt['intake_items_total']) * 100) if appt['intake_items_total'] > 0 else 0
        
        appt_cards.append(f'''
        <div class="appointment-card {status_class}"
             data-patient-id="{appt['mrn'] or ''}"
             data-patient-name="{appt['patient_name']}"
             data-appointment-id="{appt['appointment_id']}"
             data-appointment-time="{appt['scheduled_time']}"
             data-crm-system="scheduler"
             onclick="selectAppointment(this, '{appt['appointment_id']}')">
            <div class="appt-header">
                <span class="appt-time">{appt['scheduled_time']}</span>
                <span class="appt-status" style="background:{badge_color}">{appt['status'].replace('_', ' ').title()}</span>
            </div>
            <div class="appt-patient">{appt['patient_name']}</div>
            <div class="appt-meta">
                <span class="appt-mrn">MRN: {appt['mrn'] or 'N/A'}</span>
                <span class="appt-type">{appt['appointment_type'].replace('_', ' ').title()}</span>
            </div>
            <div class="appt-provider">{appt['provider_name'] or 'Unassigned'} • {appt['location'] or 'TBD'}</div>
            <div class="appt-intake">
                <div class="intake-bar">
                    <div class="intake-fill" style="width:{intake_pct}%"></div>
                </div>
                <span class="intake-label">{appt['intake_items_complete']}/{appt['intake_items_total']} intake</span>
            </div>
        </div>
        ''')
    
    # Build attention items
    attention_items = []
    if attention['pre_visit_reminders'] > 0:
        attention_items.append(f'<div class="attention-item warning"><span class="att-icon">📞</span><span>{attention["pre_visit_reminders"]} pre-visit reminders pending</span></div>')
    if attention['insurance_pending'] > 0:
        attention_items.append(f'<div class="attention-item alert"><span class="att-icon">🔍</span><span>{attention["insurance_pending"]} insurance verifications pending</span></div>')
    if attention['no_show_followups'] > 0:
        attention_items.append(f'<div class="attention-item danger"><span class="att-icon">❌</span><span>{attention["no_show_followups"]} no-show follow-ups needed</span></div>')
    if attention['needs_confirmation'] > 0:
        attention_items.append(f'<div class="attention-item info"><span class="att-icon">✓</span><span>{attention["needs_confirmation"]} appointments need confirmation</span></div>')
    
    # Build intake queue rows
    intake_rows = []
    for item in intake_queue[:10]:
        ins_status_class = "verified" if item['insurance_eligible'] else ("pending" if item['insurance_status'] == "pending" else "failed")
        intake_rows.append(f'''
        <tr class="intake-row"
            data-patient-id="{item['mrn'] or ''}"
            data-patient-name="{item['patient_name']}"
            data-crm-system="scheduler">
            <td class="patient-cell">{item['patient_name']}</td>
            <td>{item['scheduled_date']} {item['scheduled_time']}</td>
            <td>{item['forms_complete']}/{item['forms_total']}</td>
            <td class="ins-{ins_status_class}">{item['insurance_status'].title()}</td>
            <td class="status-{item['checklist_status']}">{item['checklist_status'].title()}</td>
        </tr>
        ''')
    
    # Build reminder rows
    reminder_rows = []
    for rem in reminders[:8]:
        type_icon = "📞" if rem['reminder_type'] == "pre_visit" else "📋"
        channel_icon = {"sms": "💬", "email": "📧", "phone_call": "📱"}.get(rem['channel'], "📨")
        reminder_rows.append(f'''
        <tr class="reminder-row"
            data-reminder-id="{rem['reminder_id']}"
            data-patient-name="{rem['patient_name']}">
            <td>{type_icon} {rem['reminder_type'].replace('_', ' ').title()}</td>
            <td>{rem['patient_name']}</td>
            <td>{channel_icon} {rem['channel'].upper()}</td>
            <td>{rem['due_date']}</td>
            <td class="status-{rem['status']}">{rem['status'].title()}</td>
            <td><button class="action-btn" onclick="completeReminder('{rem['reminder_id']}')">✓</button></td>
        </tr>
        ''')
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Front Desk CRM - Modern</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            min-height: 100vh;
        }}
        
        .crm-header {{
            background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
            color: white;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            box-shadow: 0 4px 20px rgba(30, 64, 175, 0.3);
        }}
        .crm-logo {{ font-size: 20px; font-weight: 700; display: flex; align-items: center; gap: 10px; }}
        .crm-logo svg {{ width: 28px; height: 28px; }}
        .header-nav {{ display: flex; gap: 8px; }}
        .nav-btn {{ 
            padding: 8px 16px; 
            border: none; 
            background: rgba(255,255,255,0.15); 
            color: white; 
            border-radius: 8px; 
            cursor: pointer; 
            font-weight: 500;
            transition: background 0.2s;
        }}
        .nav-btn:hover {{ background: rgba(255,255,255,0.25); }}
        .nav-btn.active {{ background: white; color: #1e40af; }}
        .search-box {{
            padding: 8px 16px;
            border: none;
            border-radius: 8px;
            width: 280px;
            font-size: 14px;
            background: rgba(255,255,255,0.9);
        }}
        
        .crm-container {{ display: grid; grid-template-columns: 1fr 320px; gap: 20px; padding: 20px; max-width: 1600px; margin: 0 auto; }}
        
        .main-content {{ display: flex; flex-direction: column; gap: 20px; }}
        
        .section-card {{
            background: white;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .section-header {{
            padding: 16px 20px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .section-title {{ font-size: 16px; font-weight: 600; color: #1e293b; }}
        .section-badge {{ 
            background: #3b82f6; 
            color: white; 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 12px; 
            font-weight: 600; 
        }}
        .section-body {{ padding: 16px 20px; }}
        
        .appointments-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }}
        
        .appointment-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .appointment-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }}
        .appointment-card.active {{ border-color: #3b82f6; background: #eff6ff; }}
        .appt-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .appt-time {{ font-size: 13px; font-weight: 600; color: #1e40af; }}
        .appt-status {{ font-size: 10px; padding: 3px 8px; border-radius: 6px; color: white; font-weight: 600; text-transform: uppercase; }}
        .appt-patient {{ font-size: 15px; font-weight: 600; color: #1e293b; margin-bottom: 4px; }}
        .appt-meta {{ display: flex; gap: 12px; font-size: 12px; color: #64748b; margin-bottom: 4px; }}
        .appt-provider {{ font-size: 12px; color: #64748b; margin-bottom: 8px; }}
        .appt-intake {{ display: flex; align-items: center; gap: 8px; }}
        .intake-bar {{ flex: 1; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; }}
        .intake-fill {{ height: 100%; background: linear-gradient(90deg, #10b981, #3b82f6); border-radius: 2px; }}
        .intake-label {{ font-size: 11px; color: #64748b; white-space: nowrap; }}
        
        .sidebar {{ display: flex; flex-direction: column; gap: 20px; }}
        
        .attention-card {{ background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
        .attention-header {{ padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }}
        .attention-title {{ font-size: 14px; font-weight: 600; color: #dc2626; display: flex; align-items: center; gap: 8px; }}
        .attention-body {{ padding: 12px; }}
        .attention-item {{ 
            display: flex; 
            align-items: center; 
            gap: 10px; 
            padding: 10px 12px; 
            border-radius: 8px; 
            margin-bottom: 8px; 
            font-size: 13px;
            font-weight: 500;
        }}
        .attention-item:last-child {{ margin-bottom: 0; }}
        .attention-item.warning {{ background: #fef3c7; color: #92400e; }}
        .attention-item.alert {{ background: #fce7f3; color: #9d174d; }}
        .attention-item.danger {{ background: #fee2e2; color: #991b1b; }}
        .attention-item.info {{ background: #dbeafe; color: #1e40af; }}
        .att-icon {{ font-size: 16px; }}
        
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 10px 12px; font-size: 11px; text-transform: uppercase; color: #64748b; background: #f8fafc; font-weight: 600; }}
        td {{ padding: 12px; border-bottom: 1px solid #f1f5f9; font-size: 13px; color: #334155; }}
        tr:hover {{ background: #f8fafc; }}
        .patient-cell {{ font-weight: 500; color: #1e293b; }}
        .ins-verified {{ color: #059669; font-weight: 500; }}
        .ins-pending {{ color: #d97706; font-weight: 500; }}
        .ins-failed {{ color: #dc2626; font-weight: 500; }}
        .status-ready, .status-completed {{ color: #059669; }}
        .status-incomplete, .status-pending {{ color: #d97706; }}
        .status-issues, .status-failed {{ color: #dc2626; }}
        
        .action-btn {{
            padding: 6px 10px;
            border: none;
            background: #3b82f6;
            color: white;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
        }}
        .action-btn:hover {{ background: #2563eb; }}
        
        .crm-style-badge {{ 
            position: fixed; 
            bottom: 16px; 
            right: 16px; 
            background: #1e40af; 
            color: white; 
            padding: 8px 16px; 
            border-radius: 20px; 
            font-size: 12px;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <header class="crm-header">
        <div class="crm-logo">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            Front Desk CRM
        </div>
        <nav class="header-nav">
            <button class="nav-btn active">Today</button>
            <button class="nav-btn">Week</button>
            <button class="nav-btn">Month</button>
            <input type="search" class="search-box" placeholder="Search patients, appointments...">
        </nav>
    </header>
    
    <div class="crm-container">
        <main class="main-content">
            <div class="section-card">
                <div class="section-header">
                    <span class="section-title">Today's Appointments</span>
                    <span class="section-badge">{len(appointments)} scheduled</span>
                </div>
                <div class="section-body">
                    <div class="appointments-grid">
                        {''.join(appt_cards) if appt_cards else '<div style="color:#64748b;padding:20px;text-align:center;">No appointments scheduled for today</div>'}
                    </div>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-header">
                    <span class="section-title">Intake Queue</span>
                    <span class="section-badge">{len(intake_queue)} patients</span>
                </div>
                <div class="section-body" style="padding:0;">
                    <table>
                        <thead><tr><th>Patient</th><th>Appointment</th><th>Forms</th><th>Insurance</th><th>Status</th></tr></thead>
                        <tbody>{''.join(intake_rows) if intake_rows else '<tr><td colspan="5" style="text-align:center;color:#64748b;">No patients in intake queue</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
            
            <div class="section-card">
                <div class="section-header">
                    <span class="section-title">Pending Reminders</span>
                    <span class="section-badge">{len(reminders)} pending</span>
                </div>
                <div class="section-body" style="padding:0;">
                    <table>
                        <thead><tr><th>Type</th><th>Patient</th><th>Channel</th><th>Due</th><th>Status</th><th></th></tr></thead>
                        <tbody>{''.join(reminder_rows) if reminder_rows else '<tr><td colspan="6" style="text-align:center;color:#64748b;">No pending reminders</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
        </main>
        
        <aside class="sidebar">
            <div class="attention-card">
                <div class="attention-header">
                    <div class="attention-title">⚠️ Needs Attention</div>
                </div>
                <div class="attention-body">
                    {''.join(attention_items) if attention_items else '<div style="color:#64748b;text-align:center;padding:20px;">All caught up!</div>'}
                </div>
            </div>
        </aside>
    </div>
    
    <div class="crm-style-badge">CRM Style: Modern</div>
    
    {_get_crm_common_script()}
</body>
</html>'''


# =============================================================================
# CLASSIC STYLE RENDERER (Traditional enterprise CRM)
# =============================================================================

def _render_classic_style(appointments, reminders, intake_queue, attention, style):
    """Render classic enterprise CRM layout."""
    
    appt_rows = []
    for i, appt in enumerate(appointments):
        bg = "#ffffff" if i % 2 == 0 else "#f9fafb"
        status_color = {
            "scheduled": "#0284c7", "confirmed": "#059669", "checked_in": "#7c3aed",
            "in_progress": "#d97706", "completed": "#6b7280", "no_show": "#dc2626", "cancelled": "#9ca3af"
        }.get(appt['status'], "#6b7280")
        
        appt_rows.append(f'''
        <tr style="background:{bg}" 
            data-patient-id="{appt['mrn'] or ''}"
            data-patient-name="{appt['patient_name']}"
            data-appointment-id="{appt['appointment_id']}"
            data-crm-system="scheduler"
            onclick="selectAppointment(this, '{appt['appointment_id']}')">
            <td style="font-weight:600">{appt['scheduled_time']}</td>
            <td><strong>{appt['patient_name']}</strong><br><small style="color:#6b7280">MRN: {appt['mrn'] or 'N/A'}</small></td>
            <td>{appt['appointment_type'].replace('_', ' ').title()}</td>
            <td>{appt['provider_name'] or 'Unassigned'}</td>
            <td><span style="background:{status_color};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{appt['status'].replace('_', ' ').upper()}</span></td>
            <td>{appt['intake_items_complete']}/{appt['intake_items_total']}</td>
            <td>
                <button class="classic-btn" onclick="event.stopPropagation();checkinPatient('{appt['appointment_id']}')">Check In</button>
            </td>
        </tr>
        ''')
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CRM Scheduler - Classic View</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: Arial, Helvetica, sans-serif; background: #f1f5f9; font-size: 13px; }}
        
        .classic-header {{
            background: linear-gradient(to bottom, #475569, #334155);
            color: white;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .classic-logo {{ font-weight: bold; font-size: 16px; }}
        .classic-toolbar {{
            background: #e2e8f0;
            padding: 8px 16px;
            border-bottom: 1px solid #cbd5e1;
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        .toolbar-btn {{
            padding: 6px 12px;
            border: 1px solid #94a3b8;
            background: white;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }}
        .toolbar-btn:hover {{ background: #f8fafc; }}
        
        .classic-container {{ display: flex; height: calc(100vh - 80px); }}
        
        .classic-sidebar {{
            width: 200px;
            background: white;
            border-right: 1px solid #e2e8f0;
        }}
        .sidebar-section {{ border-bottom: 1px solid #e2e8f0; }}
        .sidebar-header {{ padding: 10px 12px; background: #f8fafc; font-weight: bold; font-size: 11px; text-transform: uppercase; color: #475569; }}
        .sidebar-item {{ padding: 8px 12px; cursor: pointer; display: flex; justify-content: space-between; }}
        .sidebar-item:hover {{ background: #f8fafc; }}
        .sidebar-item.active {{ background: #dbeafe; color: #1d4ed8; }}
        .sidebar-count {{ background: #ef4444; color: white; padding: 1px 6px; border-radius: 10px; font-size: 10px; }}
        
        .classic-main {{ flex: 1; padding: 16px; overflow: auto; }}
        .classic-panel {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            margin-bottom: 16px;
        }}
        .panel-header {{
            padding: 10px 14px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
        }}
        .panel-body {{ padding: 0; }}
        
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 10px 12px; background: #f1f5f9; border-bottom: 2px solid #e2e8f0; font-size: 11px; text-transform: uppercase; color: #475569; }}
        td {{ padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }}
        tr:hover {{ background: #f8fafc; cursor: pointer; }}
        tr.selected {{ background: #dbeafe; }}
        
        .classic-btn {{
            padding: 4px 10px;
            border: 1px solid #3b82f6;
            background: white;
            color: #3b82f6;
            border-radius: 4px;
            cursor: pointer;
            font-size: 11px;
        }}
        .classic-btn:hover {{ background: #3b82f6; color: white; }}
        
        .crm-style-badge {{ position: fixed; bottom: 12px; right: 12px; background: #475569; color: white; padding: 6px 12px; border-radius: 4px; font-size: 11px; }}
    </style>
</head>
<body>
    <header class="classic-header">
        <div class="classic-logo">📋 CRM Scheduler</div>
        <div>Style: {style} | {len(appointments)} Appointments Today</div>
    </header>
    <div class="classic-toolbar">
        <button class="toolbar-btn">📅 Today</button>
        <button class="toolbar-btn">◀ Previous</button>
        <button class="toolbar-btn">Next ▶</button>
        <span style="flex:1"></span>
        <button class="toolbar-btn">➕ New Appointment</button>
        <button class="toolbar-btn">🔄 Refresh</button>
    </div>
    
    <div class="classic-container">
        <aside class="classic-sidebar">
            <div class="sidebar-section">
                <div class="sidebar-header">Quick Actions</div>
                <div class="sidebar-item active">Today's Schedule</div>
                <div class="sidebar-item">Intake Queue</div>
                <div class="sidebar-item">Reminders <span class="sidebar-count">{len(reminders)}</span></div>
                <div class="sidebar-item">No-Shows <span class="sidebar-count">{attention['no_show_followups']}</span></div>
            </div>
            <div class="sidebar-section">
                <div class="sidebar-header">Attention Required</div>
                <div class="sidebar-item">Insurance Pending <span class="sidebar-count">{attention['insurance_pending']}</span></div>
                <div class="sidebar-item">Pre-Visit Calls <span class="sidebar-count">{attention['pre_visit_reminders']}</span></div>
                <div class="sidebar-item">Post-Visit F/U <span class="sidebar-count">{attention['post_visit_reminders']}</span></div>
            </div>
        </aside>
        
        <main class="classic-main">
            <div class="classic-panel">
                <div class="panel-header">
                    <span>Today's Appointments ({len(appointments)})</span>
                    <span style="font-weight:normal;color:#64748b">{datetime.now().strftime('%A, %B %d, %Y')}</span>
                </div>
                <div class="panel-body">
                    <table>
                        <thead><tr><th>Time</th><th>Patient</th><th>Type</th><th>Provider</th><th>Status</th><th>Intake</th><th>Actions</th></tr></thead>
                        <tbody>{''.join(appt_rows) if appt_rows else '<tr><td colspan="7" style="text-align:center;padding:30px;color:#64748b">No appointments scheduled</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>
    
    <div class="crm-style-badge">CRM Style: Classic</div>
    {_get_crm_common_script()}
</body>
</html>'''


# =============================================================================
# HEALTHCARE FIRST STYLE (Clinical colors, healthcare-focused)
# =============================================================================

def _render_healthcare_style(appointments, reminders, intake_queue, attention, style):
    """Render healthcare-focused CRM layout with clinical styling."""
    
    appt_cards = []
    for appt in appointments:
        status_bg = {
            "scheduled": "#e0f2fe", "confirmed": "#dcfce7", "checked_in": "#f3e8ff",
            "in_progress": "#fef3c7", "completed": "#f3f4f6", "no_show": "#fee2e2", "cancelled": "#f3f4f6"
        }.get(appt['status'], "#f3f4f6")
        status_color = {
            "scheduled": "#0369a1", "confirmed": "#166534", "checked_in": "#7c3aed",
            "in_progress": "#92400e", "completed": "#4b5563", "no_show": "#991b1b", "cancelled": "#6b7280"
        }.get(appt['status'], "#6b7280")
        
        appt_cards.append(f'''
        <div class="hc-appt-card" style="border-left-color:{status_color}"
             data-patient-id="{appt['mrn'] or ''}"
             data-patient-name="{appt['patient_name']}"
             data-appointment-id="{appt['appointment_id']}"
             data-crm-system="scheduler">
            <div class="hc-appt-time">{appt['scheduled_time']}</div>
            <div class="hc-appt-patient">{appt['patient_name']}</div>
            <div class="hc-appt-mrn">MRN: {appt['mrn'] or 'N/A'} | DOB: {appt['dob'] or 'N/A'}</div>
            <div class="hc-appt-meta">
                <span class="hc-status" style="background:{status_bg};color:{status_color}">{appt['status'].replace('_', ' ').title()}</span>
                <span class="hc-type">{appt['appointment_type'].replace('_', ' ').title()}</span>
            </div>
            <div class="hc-appt-provider">👨‍⚕️ {appt['provider_name'] or 'Unassigned'}</div>
            {f'<div class="hc-wait-alert">⏱️ Waiting: {appt["wait_time_minutes"]} min</div>' if appt['wait_time_minutes'] else ''}
        </div>
        ''')
    
    reminder_items = []
    for rem in reminders[:6]:
        icon = "📱" if rem['reminder_type'] == "pre_visit" else "📋"
        reminder_items.append(f'''
        <div class="hc-reminder-item">
            <span class="hc-rem-icon">{icon}</span>
            <div class="hc-rem-content">
                <div class="hc-rem-patient">{rem['patient_name']}</div>
                <div class="hc-rem-type">{rem['reminder_type'].replace('_', ' ').title()} • {rem['channel'].upper()}</div>
            </div>
            <button class="hc-rem-action" onclick="completeReminder('{rem['reminder_id']}')">Complete</button>
        </div>
        ''')
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Healthcare CRM - Front Desk</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f0fdf4; min-height: 100vh; }}
        
        .hc-header {{
            background: linear-gradient(135deg, #166534 0%, #22c55e 100%);
            color: white;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .hc-logo {{ font-size: 20px; font-weight: 600; display: flex; align-items: center; gap: 10px; }}
        .hc-nav {{ display: flex; gap: 16px; }}
        .hc-nav-item {{ color: rgba(255,255,255,0.8); cursor: pointer; padding: 4px 0; border-bottom: 2px solid transparent; }}
        .hc-nav-item:hover {{ color: white; }}
        .hc-nav-item.active {{ color: white; border-bottom-color: white; }}
        
        .hc-container {{ max-width: 1400px; margin: 0 auto; padding: 20px; display: grid; grid-template-columns: 1fr 340px; gap: 20px; }}
        
        .hc-section {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(22, 101, 52, 0.1);
            overflow: hidden;
        }}
        .hc-section-header {{
            padding: 14px 18px;
            background: linear-gradient(to right, #dcfce7, #f0fdf4);
            border-bottom: 1px solid #bbf7d0;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .hc-section-title {{ font-size: 15px; font-weight: 600; color: #166534; }}
        .hc-section-badge {{ background: #166534; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; }}
        .hc-section-body {{ padding: 16px 18px; }}
        
        .hc-appointments {{ display: flex; flex-direction: column; gap: 12px; }}
        .hc-appt-card {{
            background: #fafafa;
            border: 1px solid #e5e7eb;
            border-left: 4px solid #166534;
            border-radius: 8px;
            padding: 12px 14px;
            cursor: pointer;
            transition: all 0.2s;
        }}
        .hc-appt-card:hover {{ background: #f0fdf4; border-color: #86efac; }}
        .hc-appt-time {{ font-size: 12px; font-weight: 600; color: #166534; margin-bottom: 4px; }}
        .hc-appt-patient {{ font-size: 15px; font-weight: 600; color: #1f2937; }}
        .hc-appt-mrn {{ font-size: 12px; color: #6b7280; margin-bottom: 8px; }}
        .hc-appt-meta {{ display: flex; gap: 8px; margin-bottom: 6px; }}
        .hc-status {{ padding: 3px 10px; border-radius: 6px; font-size: 11px; font-weight: 500; }}
        .hc-type {{ font-size: 12px; color: #4b5563; }}
        .hc-appt-provider {{ font-size: 12px; color: #4b5563; }}
        .hc-wait-alert {{ font-size: 12px; color: #dc2626; margin-top: 6px; font-weight: 500; }}
        
        .hc-sidebar {{ display: flex; flex-direction: column; gap: 16px; }}
        
        .hc-alert-box {{
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 12px;
            padding: 14px;
        }}
        .hc-alert-title {{ font-size: 13px; font-weight: 600; color: #991b1b; margin-bottom: 10px; }}
        .hc-alert-item {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; color: #7f1d1d; }}
        .hc-alert-count {{ font-weight: 600; }}
        
        .hc-reminder-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: #f8fafc;
            border-radius: 8px;
            margin-bottom: 8px;
        }}
        .hc-rem-icon {{ font-size: 20px; }}
        .hc-rem-content {{ flex: 1; }}
        .hc-rem-patient {{ font-size: 13px; font-weight: 500; color: #1f2937; }}
        .hc-rem-type {{ font-size: 11px; color: #6b7280; }}
        .hc-rem-action {{
            padding: 5px 10px;
            border: 1px solid #166534;
            background: white;
            color: #166534;
            border-radius: 6px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 500;
        }}
        .hc-rem-action:hover {{ background: #166534; color: white; }}
        
        .crm-style-badge {{ position: fixed; bottom: 16px; right: 16px; background: #166534; color: white; padding: 8px 16px; border-radius: 20px; font-size: 12px; }}
    </style>
</head>
<body>
    <header class="hc-header">
        <div class="hc-logo">🏥 Healthcare CRM</div>
        <nav class="hc-nav">
            <span class="hc-nav-item active">Schedule</span>
            <span class="hc-nav-item">Intake</span>
            <span class="hc-nav-item">Reminders</span>
            <span class="hc-nav-item">Reports</span>
        </nav>
    </header>
    
    <div class="hc-container">
        <main>
            <div class="hc-section">
                <div class="hc-section-header">
                    <span class="hc-section-title">Today's Schedule</span>
                    <span class="hc-section-badge">{len(appointments)} appointments</span>
                </div>
                <div class="hc-section-body">
                    <div class="hc-appointments">
                        {''.join(appt_cards) if appt_cards else '<div style="text-align:center;color:#6b7280;padding:30px">No appointments today</div>'}
                    </div>
                </div>
            </div>
        </main>
        
        <aside class="hc-sidebar">
            <div class="hc-alert-box">
                <div class="hc-alert-title">⚠️ Action Required</div>
                <div class="hc-alert-item"><span>Pre-visit reminders</span><span class="hc-alert-count">{attention['pre_visit_reminders']}</span></div>
                <div class="hc-alert-item"><span>Insurance pending</span><span class="hc-alert-count">{attention['insurance_pending']}</span></div>
                <div class="hc-alert-item"><span>No-show follow-ups</span><span class="hc-alert-count">{attention['no_show_followups']}</span></div>
                <div class="hc-alert-item"><span>Need confirmation</span><span class="hc-alert-count">{attention['needs_confirmation']}</span></div>
            </div>
            
            <div class="hc-section">
                <div class="hc-section-header">
                    <span class="hc-section-title">Pending Reminders</span>
                </div>
                <div class="hc-section-body">
                    {''.join(reminder_items) if reminder_items else '<div style="text-align:center;color:#6b7280">All caught up!</div>'}
                </div>
            </div>
        </aside>
    </div>
    
    <div class="crm-style-badge">CRM Style: Healthcare First</div>
    {_get_crm_common_script()}
</body>
</html>'''


# =============================================================================
# EFFICIENCY STYLE (Compact, data-dense for power users)
# =============================================================================

def _render_efficiency_style(appointments, reminders, intake_queue, attention, style):
    """Render compact, data-dense CRM for power users."""
    
    appt_rows = []
    for appt in appointments:
        status_icon = {
            "scheduled": "📅", "confirmed": "✅", "checked_in": "🏥",
            "in_progress": "⏳", "completed": "✔️", "no_show": "❌", "cancelled": "🚫"
        }.get(appt['status'], "•")
        
        appt_rows.append(f'''
        <tr data-patient-id="{appt['mrn'] or ''}"
            data-patient-name="{appt['patient_name']}"
            data-appointment-id="{appt['appointment_id']}"
            data-crm-system="scheduler">
            <td class="eff-time">{appt['scheduled_time']}</td>
            <td class="eff-status">{status_icon}</td>
            <td class="eff-patient">{appt['patient_name']}</td>
            <td class="eff-mrn">{appt['mrn'] or '-'}</td>
            <td class="eff-type">{appt['appointment_type'][:3].upper()}</td>
            <td class="eff-provider">{(appt['provider_name'] or '-')[:12]}</td>
            <td class="eff-intake">{appt['intake_items_complete']}/{appt['intake_items_total']}</td>
            <td><kbd class="eff-key" onclick="checkinPatient('{appt['appointment_id']}')">C</kbd></td>
        </tr>
        ''')
    
    intake_rows = []
    for item in intake_queue[:8]:
        ins_status = "✓" if item['insurance_eligible'] else ("⏳" if item['insurance_status'] == "pending" else "✗")
        intake_rows.append(f'''
        <tr data-patient-id="{item['mrn'] or ''}" data-patient-name="{item['patient_name']}" data-crm-system="scheduler">
            <td>{item['patient_name'][:15]}</td>
            <td>{item['scheduled_time']}</td>
            <td>{item['forms_complete']}/{item['forms_total']}</td>
            <td>{ins_status}</td>
            <td>{item['checklist_items']}/{item['checklist_total']}</td>
        </tr>
        ''')
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CRM - Efficiency Mode</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; background: #0f172a; color: #e2e8f0; font-size: 12px; }}
        
        .eff-header {{
            background: #1e293b;
            padding: 8px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #334155;
        }}
        .eff-logo {{ color: #22d3ee; font-weight: 600; }}
        .eff-stats {{ display: flex; gap: 16px; font-size: 11px; }}
        .eff-stat {{ color: #94a3b8; }}
        .eff-stat-value {{ color: #22d3ee; font-weight: 600; }}
        
        .eff-container {{ display: grid; grid-template-columns: 1fr 280px; height: calc(100vh - 40px); }}
        
        .eff-main {{ overflow: auto; }}
        .eff-sidebar {{ background: #1e293b; border-left: 1px solid #334155; padding: 12px; overflow: auto; }}
        
        .eff-panel {{ margin-bottom: 16px; }}
        .eff-panel-header {{ 
            padding: 6px 10px; 
            background: #334155; 
            color: #22d3ee; 
            font-size: 10px; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
            display: flex;
            justify-content: space-between;
        }}
        .eff-panel-count {{ color: #f59e0b; }}
        
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ 
            text-align: left; 
            padding: 6px 8px; 
            background: #1e293b; 
            color: #64748b; 
            font-size: 10px; 
            text-transform: uppercase;
            position: sticky;
            top: 0;
        }}
        td {{ padding: 6px 8px; border-bottom: 1px solid #1e293b; }}
        tr:hover {{ background: #1e293b; }}
        
        .eff-time {{ color: #22d3ee; font-weight: 500; }}
        .eff-status {{ text-align: center; }}
        .eff-patient {{ color: #f8fafc; font-weight: 500; }}
        .eff-mrn {{ color: #64748b; font-family: monospace; }}
        .eff-type {{ color: #a78bfa; font-size: 10px; }}
        .eff-provider {{ color: #94a3b8; }}
        .eff-intake {{ color: #fbbf24; }}
        
        .eff-key {{
            background: #334155;
            color: #22d3ee;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            cursor: pointer;
            border: 1px solid #475569;
        }}
        .eff-key:hover {{ background: #22d3ee; color: #0f172a; }}
        
        .eff-alert {{ padding: 8px 10px; background: #7f1d1d; border-radius: 4px; margin-bottom: 8px; }}
        .eff-alert-title {{ color: #fca5a5; font-size: 10px; text-transform: uppercase; margin-bottom: 4px; }}
        .eff-alert-items {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .eff-alert-item {{ color: #fecaca; font-size: 11px; }}
        .eff-alert-num {{ color: #f87171; font-weight: 600; }}
        
        .crm-style-badge {{ position: fixed; bottom: 12px; right: 12px; background: #22d3ee; color: #0f172a; padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 600; }}
        
        /* Keyboard shortcuts hint */
        .eff-shortcuts {{ font-size: 10px; color: #64748b; padding: 8px 10px; }}
        .eff-shortcuts kbd {{ background: #334155; padding: 1px 4px; border-radius: 2px; margin-right: 4px; }}
    </style>
</head>
<body>
    <header class="eff-header">
        <span class="eff-logo">⚡ CRM EFFICIENCY MODE</span>
        <div class="eff-stats">
            <span class="eff-stat">APPT: <span class="eff-stat-value">{len(appointments)}</span></span>
            <span class="eff-stat">QUEUE: <span class="eff-stat-value">{len(intake_queue)}</span></span>
            <span class="eff-stat">ALERTS: <span class="eff-stat-value" style="color:#f87171">{sum(attention.values())}</span></span>
        </div>
    </header>
    
    <div class="eff-container">
        <main class="eff-main">
            <div class="eff-panel">
                <div class="eff-panel-header">
                    <span>Appointments</span>
                    <span class="eff-panel-count">{len(appointments)}</span>
                </div>
                <table>
                    <thead><tr><th>Time</th><th></th><th>Patient</th><th>MRN</th><th>Type</th><th>Provider</th><th>Intake</th><th></th></tr></thead>
                    <tbody>{''.join(appt_rows) if appt_rows else '<tr><td colspan="8" style="text-align:center;color:#64748b">No appointments</td></tr>'}</tbody>
                </table>
            </div>
            
            <div class="eff-panel">
                <div class="eff-panel-header">
                    <span>Intake Queue</span>
                    <span class="eff-panel-count">{len(intake_queue)}</span>
                </div>
                <table>
                    <thead><tr><th>Patient</th><th>Time</th><th>Forms</th><th>Ins</th><th>Check</th></tr></thead>
                    <tbody>{''.join(intake_rows) if intake_rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">Queue empty</td></tr>'}</tbody>
                </table>
            </div>
        </main>
        
        <aside class="eff-sidebar">
            <div class="eff-alert">
                <div class="eff-alert-title">⚠ Action Required</div>
                <div class="eff-alert-items">
                    <span class="eff-alert-item">Pre-visit: <span class="eff-alert-num">{attention['pre_visit_reminders']}</span></span>
                    <span class="eff-alert-item">Insurance: <span class="eff-alert-num">{attention['insurance_pending']}</span></span>
                    <span class="eff-alert-item">No-show: <span class="eff-alert-num">{attention['no_show_followups']}</span></span>
                    <span class="eff-alert-item">Confirm: <span class="eff-alert-num">{attention['needs_confirmation']}</span></span>
                </div>
            </div>
            
            <div class="eff-shortcuts">
                <kbd>C</kbd> Check-in | <kbd>R</kbd> Reminder | <kbd>I</kbd> Intake | <kbd>/</kbd> Search
            </div>
        </aside>
    </div>
    
    <div class="crm-style-badge">EFFICIENCY</div>
    {_get_crm_common_script()}
</body>
</html>'''


# =============================================================================
# COMMON JAVASCRIPT
# =============================================================================

def _get_crm_common_script():
    """Return common JavaScript for CRM interactions."""
    return '''
    <script>
        let activeElement = null;
        
        function selectAppointment(element, appointmentId) {
            if (activeElement) {
                activeElement.classList.remove('active', 'selected');
            }
            element.classList.add('active', 'selected');
            activeElement = element;
            
            console.log('[Mock CRM] Selected appointment:', {
                appointmentId: appointmentId,
                patientId: element.dataset.patientId,
                patientName: element.dataset.patientName,
                appointmentTime: element.dataset.appointmentTime,
                crmSystem: element.dataset.crmSystem
            });
        }
        
        async function completeReminder(reminderId) {
            try {
                const response = await fetch(`/mock-crm/api/reminder/${reminderId}/complete`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.ok) {
                    alert('Reminder marked as complete!');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('Failed to complete reminder:', err);
                alert('Failed to complete reminder');
            }
        }
        
        async function checkinPatient(appointmentId) {
            try {
                const response = await fetch(`/mock-crm/api/checkin/${appointmentId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (data.ok) {
                    alert('Patient checked in!');
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                console.error('Failed to check in patient:', err);
                alert('Failed to check in patient');
            }
        }
        
        // Keyboard shortcuts for efficiency mode
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && !e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                const searchBox = document.querySelector('.search-box, input[type="search"]');
                if (searchBox) searchBox.focus();
            }
        });
    </script>
    '''
