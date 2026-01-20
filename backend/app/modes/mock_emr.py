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
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, Response
from sqlalchemy.orm import joinedload
from sqlalchemy import and_, or_

from app.db.postgres import get_db_session
from app.models.patient import PatientContext, PatientSnapshot
from app.models.patient_ids import PatientId
from app.models.mock_emr import MockEmrRecord
from app.models.appointment import Appointment, AppointmentReminder
from app.models.scheduling import Provider, ProviderSchedule, TimeSlot, ScheduleException
from app.models.orders import ClinicalOrder, LabOrder, ImagingOrder, MedicationOrder, ReferralOrder
from app.models.billing import PatientInsurance, Charge, Claim, Payment, PatientStatement
from app.models.messages import MessageThread, Message

bp = Blueprint("mock_emr", __name__, url_prefix="/mock-emr")

# Default tenant ID for development
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Available EMR styles
EMR_STYLES = ["epic", "cerner", "allscripts", "athena", "legacy", "netsmart", "qualifacts"]


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


def _get_scheduling_data(db, tenant_id: uuid.UUID) -> dict:
    """Get scheduling data for the EMR."""
    today = date.today()
    
    # Get providers
    providers = db.query(Provider).filter(
        Provider.tenant_id == tenant_id,
        Provider.is_active == True
    ).all()
    
    # Get today's appointments
    appointments = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.scheduled_date == today
    ).order_by(Appointment.scheduled_time).all()
    
    # Get available slots for today and next 7 days
    slots = db.query(TimeSlot).filter(
        TimeSlot.tenant_id == tenant_id,
        TimeSlot.slot_date >= today,
        TimeSlot.slot_date <= today + timedelta(days=7)
    ).order_by(TimeSlot.slot_date, TimeSlot.start_time).all()
    
    # Build provider map
    provider_map = {p.provider_id: p for p in providers}
    
    return {
        "providers": [p.to_dict() for p in providers],
        "provider_map": provider_map,
        "today_appointments": appointments,
        "slots": slots,
        "today": today,
    }


def _get_orders_data(db, tenant_id: uuid.UUID) -> dict:
    """Get orders data for the EMR."""
    # Get recent orders (last 90 days)
    cutoff_date = date.today() - timedelta(days=90)
    
    orders = db.query(ClinicalOrder).filter(
        ClinicalOrder.tenant_id == tenant_id,
        ClinicalOrder.ordered_at >= datetime.combine(cutoff_date, datetime.min.time())
    ).order_by(ClinicalOrder.ordered_at.desc()).limit(100).all()
    
    # Organize by type
    lab_orders = [o for o in orders if o.order_type == "lab"]
    imaging_orders = [o for o in orders if o.order_type == "imaging"]
    medication_orders = [o for o in orders if o.order_type == "medication"]
    referral_orders = [o for o in orders if o.order_type == "referral"]
    
    # Get counts by status
    pending_count = len([o for o in orders if o.status == "pending"])
    in_progress_count = len([o for o in orders if o.status == "in_progress"])
    completed_count = len([o for o in orders if o.status == "completed"])
    
    return {
        "all_orders": orders,
        "lab_orders": lab_orders,
        "imaging_orders": imaging_orders,
        "medication_orders": medication_orders,
        "referral_orders": referral_orders,
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
    }


def _get_billing_data(db, tenant_id: uuid.UUID) -> dict:
    """Get billing data for the EMR."""
    # Get recent claims
    claims = db.query(Claim).filter(
        Claim.tenant_id == tenant_id
    ).order_by(Claim.created_at.desc()).limit(50).all()
    
    # Get recent charges
    charges = db.query(Charge).filter(
        Charge.tenant_id == tenant_id
    ).order_by(Charge.service_date.desc()).limit(100).all()
    
    # Get recent payments
    payments = db.query(Payment).filter(
        Payment.tenant_id == tenant_id
    ).order_by(Payment.payment_date.desc()).limit(50).all()
    
    # Calculate totals
    total_charges = sum(float(c.total_charge or 0) for c in charges)
    total_payments = sum(float(p.amount or 0) for p in payments)
    
    # Claims by status
    claims_pending = len([c for c in claims if c.status in ["pending", "submitted"]])
    claims_paid = len([c for c in claims if c.status == "paid"])
    claims_denied = len([c for c in claims if c.status == "denied"])
    
    return {
        "claims": claims,
        "charges": charges,
        "payments": payments,
        "total_charges": total_charges,
        "total_payments": total_payments,
        "claims_pending": claims_pending,
        "claims_paid": claims_paid,
        "claims_denied": claims_denied,
    }


def _get_messages_data(db, tenant_id: uuid.UUID) -> dict:
    """Get messages data for the EMR."""
    # Get message threads
    threads = db.query(MessageThread).filter(
        MessageThread.tenant_id == tenant_id
    ).order_by(MessageThread.last_message_at.desc()).limit(50).all()
    
    # Get unread count
    unread_threads = len([t for t in threads if t.unread_count > 0])
    
    # Get threads by status
    open_threads = [t for t in threads if t.status == "open"]
    closed_threads = [t for t in threads if t.status == "closed"]
    
    # Get threads by category
    threads_by_category = {}
    for t in threads:
        cat = t.category or "general"
        if cat not in threads_by_category:
            threads_by_category[cat] = []
        threads_by_category[cat].append(t)
    
    return {
        "threads": threads,
        "open_threads": open_threads,
        "closed_threads": closed_threads,
        "unread_count": unread_threads,
        "threads_by_category": threads_by_category,
    }


@bp.route("/", methods=["GET"])
def mock_emr_page():
    """Render the unified EMR HTML page with selected style."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    style = _get_style()
    
    # Get patient data
    patients = _get_all_patients(db, tenant_id)
    
    # Get scheduling data
    scheduling_data = _get_scheduling_data(db, tenant_id)
    
    # Get orders data
    orders_data = _get_orders_data(db, tenant_id)
    
    # Get billing data
    billing_data = _get_billing_data(db, tenant_id)
    
    # Get messages data
    messages_data = _get_messages_data(db, tenant_id)
    
    # Select renderer based on style - now uses unified tabbed layout
    renderers = {
        "epic": _render_unified_epic_style,
        "cerner": _render_unified_cerner_style,
        "allscripts": _render_unified_allscripts_style,
        "athena": _render_unified_athena_style,
        "legacy": _render_unified_legacy_style,
        "netsmart": _render_unified_netsmart_style,
        "qualifacts": _render_unified_qualifacts_style,
    }
    
    renderer = renderers.get(style, _render_unified_epic_style)
    html = renderer(patients, scheduling_data, orders_data, billing_data, messages_data, style)
    
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
# SCHEDULING API ENDPOINTS
# =============================================================================

@bp.route("/api/schedule/providers", methods=["GET"])
def list_providers():
    """List all providers with their schedules."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    providers = db.query(Provider).filter(
        Provider.tenant_id == tenant_id,
        Provider.is_active == True
    ).all()
    
    return jsonify({
        "ok": True,
        "count": len(providers),
        "providers": [p.to_dict() for p in providers]
    })


@bp.route("/api/schedule/calendar", methods=["GET"])
def get_calendar():
    """Get calendar data for a date range."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    # Parse date parameters
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    provider_id_str = request.args.get("provider_id")
    view_type = request.args.get("view", "week")  # day, week, month
    
    # Default to today + 7 days
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = start_date + timedelta(days=7)
    else:
        # Set end date based on view type
        if view_type == "day":
            end_date = start_date
        elif view_type == "month":
            end_date = start_date + timedelta(days=30)
        else:
            end_date = start_date + timedelta(days=7)
    
    # Build query
    query = db.query(TimeSlot).filter(
        TimeSlot.tenant_id == tenant_id,
        TimeSlot.slot_date >= start_date,
        TimeSlot.slot_date <= end_date
    )
    
    # Filter by provider if specified
    if provider_id_str:
        try:
            provider_id = uuid.UUID(provider_id_str)
            query = query.filter(TimeSlot.provider_id == provider_id)
        except ValueError:
            pass
    
    slots = query.order_by(TimeSlot.slot_date, TimeSlot.start_time).all()
    
    # Get provider info for enrichment
    provider_ids = set(s.provider_id for s in slots)
    providers = db.query(Provider).filter(Provider.provider_id.in_(provider_ids)).all()
    provider_map = {p.provider_id: p for p in providers}
    
    # Get appointments for booked slots
    appointment_ids = [s.appointment_id for s in slots if s.appointment_id]
    appointments = db.query(Appointment).filter(Appointment.appointment_id.in_(appointment_ids)).all()
    appointment_map = {a.appointment_id: a for a in appointments}
    
    # Build calendar data
    calendar_data = []
    for slot in slots:
        provider = provider_map.get(slot.provider_id)
        appointment = appointment_map.get(slot.appointment_id) if slot.appointment_id else None
        
        # Get patient info if booked
        patient_name = None
        patient_mrn = None
        if appointment:
            snapshot = db.query(PatientSnapshot).filter(
                PatientSnapshot.patient_context_id == appointment.patient_context_id
            ).order_by(PatientSnapshot.snapshot_version.desc()).first()
            if snapshot:
                patient_name = snapshot.display_name
            
            patient_id = db.query(PatientId).filter(
                PatientId.patient_context_id == appointment.patient_context_id,
                PatientId.id_type == "mrn"
            ).first()
            if patient_id:
                patient_mrn = patient_id.id_value
        
        calendar_data.append({
            "slot_id": str(slot.slot_id),
            "provider_id": str(slot.provider_id),
            "provider_name": provider.provider_name if provider else None,
            "provider_credentials": provider.credentials if provider else None,
            "slot_date": slot.slot_date.isoformat(),
            "start_time": slot.start_time.strftime("%H:%M") if slot.start_time else None,
            "end_time": slot.end_time.strftime("%H:%M") if slot.end_time else None,
            "duration_minutes": slot.duration_minutes,
            "status": slot.status,
            "location": slot.location,
            "room": slot.room,
            "appointment_id": str(slot.appointment_id) if slot.appointment_id else None,
            "appointment_type": appointment.appointment_type if appointment else None,
            "appointment_status": appointment.status if appointment else None,
            "patient_name": patient_name,
            "patient_mrn": patient_mrn,
            "visit_reason": appointment.visit_reason if appointment else None,
        })
    
    return jsonify({
        "ok": True,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "view_type": view_type,
        "count": len(calendar_data),
        "slots": calendar_data
    })


@bp.route("/api/schedule/slots", methods=["GET"])
def get_available_slots():
    """Get available time slots for booking."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    # Parse parameters
    provider_id_str = request.args.get("provider_id")
    date_str = request.args.get("date")
    appointment_type = request.args.get("appointment_type")
    
    if not date_str:
        target_date = date.today() + timedelta(days=1)
    else:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today() + timedelta(days=1)
    
    # Build query for available slots
    query = db.query(TimeSlot).filter(
        TimeSlot.tenant_id == tenant_id,
        TimeSlot.slot_date == target_date,
        TimeSlot.status == "available"
    )
    
    if provider_id_str:
        try:
            provider_id = uuid.UUID(provider_id_str)
            query = query.filter(TimeSlot.provider_id == provider_id)
        except ValueError:
            pass
    
    slots = query.order_by(TimeSlot.start_time).all()
    
    # Get provider info
    provider_ids = set(s.provider_id for s in slots)
    providers = db.query(Provider).filter(Provider.provider_id.in_(provider_ids)).all()
    provider_map = {p.provider_id: p for p in providers}
    
    # Build response
    available_slots = []
    for slot in slots:
        provider = provider_map.get(slot.provider_id)
        available_slots.append({
            "slot_id": str(slot.slot_id),
            "provider_id": str(slot.provider_id),
            "provider_name": provider.provider_name if provider else None,
            "provider_credentials": provider.credentials if provider else None,
            "specialty": provider.specialty if provider else None,
            "slot_date": slot.slot_date.isoformat(),
            "start_time": slot.start_time.strftime("%I:%M %p") if slot.start_time else None,
            "end_time": slot.end_time.strftime("%I:%M %p") if slot.end_time else None,
            "duration_minutes": slot.duration_minutes,
            "location": slot.location,
            "room": slot.room,
        })
    
    return jsonify({
        "ok": True,
        "date": target_date.isoformat(),
        "count": len(available_slots),
        "slots": available_slots
    })


@bp.route("/api/schedule/book", methods=["POST"])
def book_appointment():
    """Book an appointment in an available slot."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    data = request.get_json() or {}
    
    slot_id_str = data.get("slot_id")
    patient_context_id_str = data.get("patient_context_id")
    appointment_type = data.get("appointment_type", "follow_up")
    visit_reason = data.get("visit_reason", "")
    
    # Validate required fields
    if not slot_id_str:
        return jsonify({"ok": False, "error": "slot_id is required"}), 400
    if not patient_context_id_str:
        return jsonify({"ok": False, "error": "patient_context_id is required"}), 400
    
    try:
        slot_id = uuid.UUID(slot_id_str)
        patient_context_id = uuid.UUID(patient_context_id_str)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid UUID format"}), 400
    
    # Get the slot
    slot = db.query(TimeSlot).filter(
        TimeSlot.slot_id == slot_id,
        TimeSlot.tenant_id == tenant_id
    ).first()
    
    if not slot:
        return jsonify({"ok": False, "error": "Slot not found"}), 404
    
    if slot.status != "available":
        return jsonify({"ok": False, "error": "Slot is not available"}), 409
    
    # Get provider info
    provider = db.query(Provider).filter(
        Provider.provider_id == slot.provider_id
    ).first()
    
    # Create appointment
    appointment = Appointment(
        tenant_id=tenant_id,
        patient_context_id=patient_context_id,
        scheduled_date=slot.slot_date,
        scheduled_time=slot.start_time,
        duration_minutes=slot.duration_minutes,
        appointment_type=appointment_type,
        status="scheduled",
        provider_name=provider.provider_name if provider else None,
        provider_id=provider.provider_id if provider else None,
        location=slot.location,
        room=slot.room,
        visit_reason=visit_reason,
        needs_confirmation=True,
        created_at=datetime.utcnow(),
    )
    
    db.add(appointment)
    db.flush()  # Get appointment ID
    
    # Update slot status
    slot.status = "booked"
    slot.appointment_id = appointment.appointment_id
    slot.updated_at = datetime.utcnow()
    
    db.commit()
    
    return jsonify({
        "ok": True,
        "appointment": appointment.to_dict(),
        "slot": slot.to_dict()
    })


@bp.route("/api/schedule/reschedule", methods=["PUT"])
def reschedule_appointment():
    """Reschedule an existing appointment to a new slot."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    data = request.get_json() or {}
    
    appointment_id_str = data.get("appointment_id")
    new_slot_id_str = data.get("new_slot_id")
    
    if not appointment_id_str or not new_slot_id_str:
        return jsonify({"ok": False, "error": "appointment_id and new_slot_id are required"}), 400
    
    try:
        appointment_id = uuid.UUID(appointment_id_str)
        new_slot_id = uuid.UUID(new_slot_id_str)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid UUID format"}), 400
    
    # Get appointment
    appointment = db.query(Appointment).filter(
        Appointment.appointment_id == appointment_id,
        Appointment.tenant_id == tenant_id
    ).first()
    
    if not appointment:
        return jsonify({"ok": False, "error": "Appointment not found"}), 404
    
    # Get old slot
    old_slot = db.query(TimeSlot).filter(
        TimeSlot.appointment_id == appointment_id
    ).first()
    
    # Get new slot
    new_slot = db.query(TimeSlot).filter(
        TimeSlot.slot_id == new_slot_id,
        TimeSlot.tenant_id == tenant_id
    ).first()
    
    if not new_slot:
        return jsonify({"ok": False, "error": "New slot not found"}), 404
    
    if new_slot.status != "available":
        return jsonify({"ok": False, "error": "New slot is not available"}), 409
    
    # Get provider info
    provider = db.query(Provider).filter(
        Provider.provider_id == new_slot.provider_id
    ).first()
    
    # Release old slot
    if old_slot:
        old_slot.status = "available"
        old_slot.appointment_id = None
        old_slot.updated_at = datetime.utcnow()
    
    # Update appointment
    appointment.scheduled_date = new_slot.slot_date
    appointment.scheduled_time = new_slot.start_time
    appointment.duration_minutes = new_slot.duration_minutes
    appointment.provider_name = provider.provider_name if provider else None
    appointment.provider_id = provider.provider_id if provider else None
    appointment.location = new_slot.location
    appointment.room = new_slot.room
    appointment.status = "rescheduled"
    appointment.rescheduled_from_id = appointment.appointment_id
    appointment.updated_at = datetime.utcnow()
    
    # Book new slot
    new_slot.status = "booked"
    new_slot.appointment_id = appointment.appointment_id
    new_slot.updated_at = datetime.utcnow()
    
    db.commit()
    
    return jsonify({
        "ok": True,
        "appointment": appointment.to_dict(),
        "new_slot": new_slot.to_dict()
    })


@bp.route("/api/schedule/cancel/<appointment_id>", methods=["DELETE"])
def cancel_appointment(appointment_id):
    """Cancel an appointment and free the slot."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    try:
        appt_uuid = uuid.UUID(appointment_id)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid appointment ID"}), 400
    
    # Get appointment
    appointment = db.query(Appointment).filter(
        Appointment.appointment_id == appt_uuid,
        Appointment.tenant_id == tenant_id
    ).first()
    
    if not appointment:
        return jsonify({"ok": False, "error": "Appointment not found"}), 404
    
    # Get cancellation reason from request body
    data = request.get_json() or {}
    cancellation_reason = data.get("reason", "Cancelled by user")
    
    # Release the slot
    slot = db.query(TimeSlot).filter(
        TimeSlot.appointment_id == appt_uuid
    ).first()
    
    if slot:
        slot.status = "available"
        slot.appointment_id = None
        slot.updated_at = datetime.utcnow()
    
    # Update appointment status
    appointment.status = "cancelled"
    appointment.cancelled_at = datetime.utcnow()
    appointment.cancellation_reason = cancellation_reason
    appointment.updated_at = datetime.utcnow()
    
    db.commit()
    
    return jsonify({
        "ok": True,
        "appointment": appointment.to_dict()
    })


@bp.route("/api/patient/<patient_context_id>/appointments", methods=["GET"])
def get_patient_appointments(patient_context_id):
    """Get all appointments for a patient."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    try:
        patient_uuid = uuid.UUID(patient_context_id)
    except ValueError:
        return jsonify({"ok": False, "error": "Invalid patient context ID"}), 400
    
    # Get filter parameters
    status_filter = request.args.get("status")  # scheduled, completed, cancelled, etc.
    include_past = request.args.get("include_past", "true").lower() == "true"
    
    # Build query
    query = db.query(Appointment).filter(
        Appointment.patient_context_id == patient_uuid,
        Appointment.tenant_id == tenant_id
    )
    
    if status_filter:
        query = query.filter(Appointment.status == status_filter)
    
    if not include_past:
        query = query.filter(Appointment.scheduled_date >= date.today())
    
    appointments = query.order_by(Appointment.scheduled_date.desc(), Appointment.scheduled_time.desc()).all()
    
    return jsonify({
        "ok": True,
        "patient_context_id": patient_context_id,
        "count": len(appointments),
        "appointments": [a.to_dict() for a in appointments]
    })


@bp.route("/api/schedule/exceptions", methods=["GET"])
def get_schedule_exceptions():
    """Get schedule exceptions (holidays, time off)."""
    db = get_db_session()
    tenant_id = _get_tenant_id()
    
    provider_id_str = request.args.get("provider_id")
    start_date_str = request.args.get("start_date")
    end_date_str = request.args.get("end_date")
    
    # Default date range
    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()
    
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        except ValueError:
            end_date = start_date + timedelta(days=30)
    else:
        end_date = start_date + timedelta(days=30)
    
    # Build query
    query = db.query(ScheduleException).filter(
        ScheduleException.tenant_id == tenant_id,
        ScheduleException.is_active == True,
        ScheduleException.start_date <= end_date,
        ScheduleException.end_date >= start_date
    )
    
    if provider_id_str:
        try:
            provider_id = uuid.UUID(provider_id_str)
            # Include provider-specific and clinic-wide exceptions
            query = query.filter(
                or_(
                    ScheduleException.provider_id == provider_id,
                    ScheduleException.provider_id == None
                )
            )
        except ValueError:
            pass
    
    exceptions = query.order_by(ScheduleException.start_date).all()
    
    return jsonify({
        "ok": True,
        "count": len(exceptions),
        "exceptions": [e.to_dict() for e in exceptions]
    })


# =============================================================================
# UNIFIED TABBED EMR RENDERERS
# =============================================================================

def _build_scheduling_calendar_html(scheduling_data: dict, style: str) -> str:
    """Build the scheduling calendar view HTML."""
    today = scheduling_data["today"]
    slots = scheduling_data["slots"]
    provider_map = scheduling_data.get("provider_map", {})
    
    # Group slots by date
    slots_by_date = {}
    for slot in slots:
        date_key = slot.slot_date.isoformat()
        if date_key not in slots_by_date:
            slots_by_date[date_key] = []
        slots_by_date[date_key].append(slot)
    
    # Build week view (7 days)
    week_days = []
    for i in range(7):
        day = today + timedelta(days=i)
        day_key = day.isoformat()
        day_slots = slots_by_date.get(day_key, [])
        
        # Count available vs booked
        available = sum(1 for s in day_slots if s.status == "available")
        booked = sum(1 for s in day_slots if s.status == "booked")
        
        week_days.append({
            "date": day,
            "day_name": day.strftime("%a"),
            "day_num": day.strftime("%d"),
            "is_today": day == today,
            "available": available,
            "booked": booked,
            "slots": day_slots[:8],  # First 8 slots for preview
        })
    
    # Build calendar HTML
    calendar_html = '<div class="emr-calendar-week">'
    for day_info in week_days:
        today_class = "today" if day_info["is_today"] else ""
        calendar_html += f'''
        <div class="emr-calendar-day {today_class}" data-date="{day_info['date'].isoformat()}">
            <div class="emr-day-header">
                <span class="day-name">{day_info['day_name']}</span>
                <span class="day-num">{day_info['day_num']}</span>
            </div>
            <div class="emr-day-summary">
                <span class="available-count">{day_info['available']} avail</span>
                <span class="booked-count">{day_info['booked']} booked</span>
            </div>
            <div class="emr-day-slots">
        '''
        
        for slot in day_info["slots"][:5]:  # Show up to 5 slots
            provider = provider_map.get(slot.provider_id)
            provider_name = provider.provider_name if provider else "Unknown"
            status_class = f"slot-{slot.status}"
            time_str = slot.start_time.strftime("%I:%M %p") if slot.start_time else ""
            
            calendar_html += f'''
                <div class="emr-slot {status_class}" 
                     data-slot-id="{slot.slot_id}"
                     data-provider-id="{slot.provider_id}"
                     onclick="selectSlot('{slot.slot_id}')">
                    <span class="slot-time">{time_str}</span>
                    <span class="slot-provider">{provider_name[:15]}</span>
                </div>
            '''
        
        if len(day_info["slots"]) > 5:
            calendar_html += f'<div class="more-slots">+{len(day_info["slots"]) - 5} more</div>'
        
        calendar_html += '</div></div>'
    
    calendar_html += '</div>'
    return calendar_html


def _build_providers_list_html(scheduling_data: dict, style: str) -> str:
    """Build providers list for filter sidebar."""
    providers = scheduling_data["providers"]
    
    html = '<div class="emr-providers-list">'
    html += '<div class="providers-header">Providers</div>'
    
    for p in providers:
        html += f'''
        <div class="provider-item" data-provider-id="{p['provider_id']}" onclick="filterByProvider('{p['provider_id']}')">
            <span class="provider-name">{p['provider_name']}</span>
            <span class="provider-specialty">{p.get('specialty', '')}</span>
        </div>
        '''
    
    html += '</div>'
    return html


def _build_appointment_booking_modal_html(scheduling_data: dict, style: str) -> str:
    """Build the appointment booking modal HTML."""
    providers = scheduling_data["providers"]
    
    provider_options = ""
    for p in providers:
        provider_options += f'<option value="{p["provider_id"]}">{p["provider_name"]} - {p.get("specialty", "")}</option>'
    
    return f'''
    <div id="booking-modal" class="emr-modal" style="display:none;">
        <div class="emr-modal-content">
            <div class="emr-modal-header">
                <h3>Schedule Appointment</h3>
                <button class="modal-close" onclick="closeBookingModal()">&times;</button>
            </div>
            <div class="emr-modal-body">
                <form id="booking-form" onsubmit="submitBooking(event)">
                    <div class="form-group">
                        <label>Provider</label>
                        <select id="booking-provider" required>
                            <option value="">Select Provider...</option>
                            {provider_options}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Date</label>
                        <input type="date" id="booking-date" required>
                    </div>
                    <div class="form-group">
                        <label>Available Times</label>
                        <div id="available-slots-list">
                            <p class="hint">Select a provider and date to see available times</p>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Appointment Type</label>
                        <select id="booking-type" required>
                            <option value="follow_up">Follow-up Visit</option>
                            <option value="new_patient">New Patient</option>
                            <option value="annual_exam">Annual Exam</option>
                            <option value="urgent">Urgent</option>
                            <option value="telehealth">Telehealth</option>
                            <option value="consultation">Consultation</option>
                            <option value="lab_work">Lab Work</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Visit Reason</label>
                        <textarea id="booking-reason" rows="3" placeholder="Reason for visit..."></textarea>
                    </div>
                    <input type="hidden" id="booking-slot-id">
                    <input type="hidden" id="booking-patient-id">
                </form>
            </div>
            <div class="emr-modal-footer">
                <button type="button" class="btn-secondary" onclick="closeBookingModal()">Cancel</button>
                <button type="submit" form="booking-form" class="btn-primary">Book Appointment</button>
            </div>
        </div>
    </div>
    '''


def _build_orders_tab_html(orders_data: dict) -> str:
    """Build the Orders tab HTML content."""
    all_orders = orders_data.get("all_orders", [])
    pending_count = orders_data.get("pending_count", 0)
    in_progress_count = orders_data.get("in_progress_count", 0)
    completed_count = orders_data.get("completed_count", 0)
    
    # Build summary cards
    html = '''
    <div class="orders-container">
        <div class="orders-header">
            <h3>Clinical Orders</h3>
            <div class="orders-actions">
                <button class="order-btn" onclick="alert('New Order dialog would open')">+ New Order</button>
            </div>
        </div>
        
        <div class="orders-summary">
            <div class="summary-card summary-pending">
                <div class="summary-count">{pending}</div>
                <div class="summary-label">Pending</div>
            </div>
            <div class="summary-card summary-progress">
                <div class="summary-count">{in_progress}</div>
                <div class="summary-label">In Progress</div>
            </div>
            <div class="summary-card summary-complete">
                <div class="summary-count">{completed}</div>
                <div class="summary-label">Completed</div>
            </div>
        </div>
        
        <div class="orders-filters">
            <select class="order-filter" onchange="filterOrders(this.value)">
                <option value="all">All Orders</option>
                <option value="lab">Lab Orders</option>
                <option value="imaging">Imaging</option>
                <option value="medication">Medications</option>
                <option value="referral">Referrals</option>
            </select>
            <select class="order-filter" onchange="filterOrderStatus(this.value)">
                <option value="all">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
            </select>
        </div>
        
        <div class="orders-list">
    '''.format(pending=pending_count, in_progress=in_progress_count, completed=completed_count)
    
    # Build order rows
    for order in all_orders[:30]:  # Limit to 30 for performance
        order_type_icon = {
            "lab": "🧪",
            "imaging": "📷",
            "medication": "💊",
            "referral": "📋"
        }.get(order.order_type, "📄")
        
        status_class = {
            "pending": "status-pending",
            "in_progress": "status-progress",
            "completed": "status-complete",
            "cancelled": "status-cancelled"
        }.get(order.status, "status-pending")
        
        ordered_date = order.ordered_at.strftime("%m/%d/%Y") if order.ordered_at else ""
        result_badge = ""
        if order.result_status == "abnormal":
            result_badge = '<span class="result-badge result-abnormal">Abnormal</span>'
        elif order.result_status == "critical":
            result_badge = '<span class="result-badge result-critical">Critical</span>'
        elif order.result_status == "normal":
            result_badge = '<span class="result-badge result-normal">Normal</span>'
        
        html += f'''
            <div class="order-row" data-order-type="{order.order_type}" data-order-status="{order.status}">
                <div class="order-icon">{order_type_icon}</div>
                <div class="order-info">
                    <div class="order-name">{order.order_name}</div>
                    <div class="order-meta">
                        <span class="order-type">{order.order_type.title()}</span>
                        <span class="order-date">{ordered_date}</span>
                        <span class="order-provider">{order.ordering_provider_name or 'Unassigned'}</span>
                    </div>
                </div>
                <div class="order-status-area">
                    {result_badge}
                    <span class="order-status {status_class}">{order.status.replace('_', ' ').title()}</span>
                </div>
            </div>
        '''
    
    if not all_orders:
        html += '<div class="no-orders">No orders found</div>'
    
    html += '''
        </div>
    </div>
    '''
    
    return html


def _build_billing_tab_html(billing_data: dict) -> str:
    """Build the Billing tab HTML content."""
    claims = billing_data.get("claims", [])
    charges = billing_data.get("charges", [])
    payments = billing_data.get("payments", [])
    total_charges = billing_data.get("total_charges", 0)
    total_payments = billing_data.get("total_payments", 0)
    claims_pending = billing_data.get("claims_pending", 0)
    claims_paid = billing_data.get("claims_paid", 0)
    claims_denied = billing_data.get("claims_denied", 0)
    
    html = f'''
    <div class="billing-container">
        <div class="billing-header">
            <h3>Billing & Claims</h3>
        </div>
        
        <div class="billing-summary">
            <div class="billing-card">
                <div class="billing-card-title">Total Charges</div>
                <div class="billing-card-amount">${total_charges:,.2f}</div>
            </div>
            <div class="billing-card">
                <div class="billing-card-title">Total Payments</div>
                <div class="billing-card-amount">${total_payments:,.2f}</div>
            </div>
            <div class="billing-card">
                <div class="billing-card-title">Outstanding</div>
                <div class="billing-card-amount">${(total_charges - total_payments):,.2f}</div>
            </div>
        </div>
        
        <div class="billing-tabs">
            <div class="billing-tab active" onclick="showBillingSection('claims')">Claims ({len(claims)})</div>
            <div class="billing-tab" onclick="showBillingSection('charges')">Charges ({len(charges)})</div>
            <div class="billing-tab" onclick="showBillingSection('payments')">Payments ({len(payments)})</div>
        </div>
        
        <div id="billing-claims" class="billing-section active">
            <div class="claims-summary">
                <span class="claim-stat">Pending: {claims_pending}</span>
                <span class="claim-stat">Paid: {claims_paid}</span>
                <span class="claim-stat claim-denied">Denied: {claims_denied}</span>
            </div>
            <table class="billing-table">
                <thead>
                    <tr>
                        <th>Claim #</th>
                        <th>Payer</th>
                        <th>DOS</th>
                        <th>Charges</th>
                        <th>Paid</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for claim in claims[:20]:
        dos = claim.service_date_from.strftime("%m/%d/%Y") if claim.service_date_from else "N/A"
        status_class = {
            "paid": "status-paid",
            "pending": "status-pending",
            "submitted": "status-pending",
            "denied": "status-denied",
        }.get(claim.status, "")
        
        html += f'''
                    <tr>
                        <td class="claim-number">{claim.claim_number or 'N/A'}</td>
                        <td>{claim.payer_name or 'N/A'}</td>
                        <td>{dos}</td>
                        <td>${float(claim.total_charges or 0):,.2f}</td>
                        <td>${float(claim.paid_amount or 0):,.2f}</td>
                        <td><span class="claim-status {status_class}">{claim.status.title()}</span></td>
                    </tr>
        '''
    
    if not claims:
        html += '<tr><td colspan="6" class="no-data">No claims found</td></tr>'
    
    html += '''
                </tbody>
            </table>
        </div>
        
        <div id="billing-charges" class="billing-section">
            <table class="billing-table">
                <thead>
                    <tr>
                        <th>DOS</th>
                        <th>CPT</th>
                        <th>Description</th>
                        <th>Charge</th>
                        <th>Paid</th>
                        <th>Balance</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for charge in charges[:20]:
        dos = charge.service_date.strftime("%m/%d/%Y") if charge.service_date else "N/A"
        balance = float(charge.total_charge or 0) - float(charge.paid_amount or 0)
        
        html += f'''
                    <tr>
                        <td>{dos}</td>
                        <td class="cpt-code">{charge.cpt_code or 'N/A'}</td>
                        <td>{charge.description[:40]}...</td>
                        <td>${float(charge.total_charge or 0):,.2f}</td>
                        <td>${float(charge.paid_amount or 0):,.2f}</td>
                        <td class="{"balance-due" if balance > 0 else ""}">${balance:,.2f}</td>
                    </tr>
        '''
    
    if not charges:
        html += '<tr><td colspan="6" class="no-data">No charges found</td></tr>'
    
    html += '''
                </tbody>
            </table>
        </div>
        
        <div id="billing-payments" class="billing-section">
            <table class="billing-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Source</th>
                        <th>Method</th>
                        <th>Reference</th>
                        <th>Amount</th>
                    </tr>
                </thead>
                <tbody>
    '''
    
    for payment in payments[:20]:
        pay_date = payment.payment_date.strftime("%m/%d/%Y") if payment.payment_date else "N/A"
        source_label = "Insurance" if payment.payment_source == "insurance" else "Patient"
        
        html += f'''
                    <tr>
                        <td>{pay_date}</td>
                        <td>{source_label}</td>
                        <td>{payment.payment_method or 'N/A'}</td>
                        <td>{payment.reference_number or payment.check_number or 'N/A'}</td>
                        <td class="payment-amount">${float(payment.amount or 0):,.2f}</td>
                    </tr>
        '''
    
    if not payments:
        html += '<tr><td colspan="5" class="no-data">No payments found</td></tr>'
    
    html += '''
                </tbody>
            </table>
        </div>
    </div>
    '''
    
    return html


def _build_messages_tab_html(messages_data: dict) -> str:
    """Build the Messages tab HTML content."""
    threads = messages_data.get("threads", [])
    open_threads = messages_data.get("open_threads", [])
    unread_count = messages_data.get("unread_count", 0)
    
    html = f'''
    <div class="messages-container">
        <div class="messages-header">
            <h3>Messages</h3>
            <div class="messages-actions">
                <button class="message-btn" onclick="alert('Compose message dialog would open')">+ New Message</button>
            </div>
        </div>
        
        <div class="messages-summary">
            <div class="msg-stat">
                <span class="msg-stat-count">{unread_count}</span>
                <span class="msg-stat-label">Unread</span>
            </div>
            <div class="msg-stat">
                <span class="msg-stat-count">{len(open_threads)}</span>
                <span class="msg-stat-label">Open</span>
            </div>
            <div class="msg-stat">
                <span class="msg-stat-count">{len(threads)}</span>
                <span class="msg-stat-label">Total</span>
            </div>
        </div>
        
        <div class="messages-filters">
            <select class="msg-filter">
                <option value="all">All Messages</option>
                <option value="unread">Unread</option>
                <option value="open">Open</option>
                <option value="closed">Closed</option>
            </select>
            <select class="msg-filter">
                <option value="all">All Categories</option>
                <option value="clinical">Clinical</option>
                <option value="prescription">Prescription</option>
                <option value="appointment">Appointment</option>
                <option value="billing">Billing</option>
            </select>
        </div>
        
        <div class="messages-list">
    '''
    
    for thread in threads[:20]:
        unread_class = "msg-unread" if thread.unread_count > 0 else ""
        category_icon = {
            "clinical": "🏥",
            "prescription": "💊",
            "appointment": "📅",
            "billing": "💳",
            "general": "💬",
            "lab_results": "🧪",
        }.get(thread.category, "💬")
        
        priority_badge = ""
        if thread.priority == "high" or thread.priority == "urgent":
            priority_badge = '<span class="priority-badge">High Priority</span>'
        
        last_msg_time = ""
        if thread.last_message_at:
            last_msg_time = thread.last_message_at.strftime("%m/%d %I:%M %p")
        
        status_badge = f'<span class="thread-status status-{thread.status}">{thread.status.title()}</span>'
        
        html += f'''
            <div class="message-thread {unread_class}">
                <div class="thread-icon">{category_icon}</div>
                <div class="thread-content">
                    <div class="thread-header">
                        <span class="thread-subject">{thread.subject}</span>
                        {priority_badge}
                    </div>
                    <div class="thread-preview">{thread.last_message_preview or 'No messages yet'}</div>
                    <div class="thread-meta">
                        <span class="thread-category">{thread.category.title()}</span>
                        <span class="thread-pool">{thread.assigned_pool or 'Unassigned'}</span>
                        <span class="thread-time">{last_msg_time}</span>
                    </div>
                </div>
                <div class="thread-status-area">
                    {status_badge}
                    {f'<span class="unread-badge">{thread.unread_count}</span>' if thread.unread_count > 0 else ''}
                </div>
            </div>
        '''
    
    if not threads:
        html += '<div class="no-messages">No messages found</div>'
    
    html += '''
        </div>
    </div>
    '''
    
    return html


def _get_unified_common_styles() -> str:
    """Return common CSS styles for unified EMR layout."""
    return '''
        /* Unified EMR Tab Styles */
        .emr-tabs {
            display: flex;
            border-bottom: 2px solid #e2e8f0;
            background: #f8fafc;
            padding: 0 16px;
        }
        .emr-tab {
            padding: 12px 20px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            margin-bottom: -2px;
            font-size: 14px;
            font-weight: 500;
            color: #64748b;
            transition: all 0.2s;
        }
        .emr-tab:hover { color: #1e40af; background: #f1f5f9; }
        .emr-tab.active { 
            color: #1e40af; 
            border-bottom-color: #1e40af;
            background: white;
        }
        .emr-tab-content { display: none; padding: 16px; }
        .emr-tab-content.active { display: block; }
        
        /* Patient Banner */
        .patient-banner {
            background: linear-gradient(135deg, #1e3a5f 0%, #2c5282 100%);
            color: white;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .patient-banner-photo {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: #4a6fa5;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            font-weight: 600;
        }
        .patient-banner-info { flex: 1; }
        .patient-banner-name { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
        .patient-banner-details { font-size: 13px; opacity: 0.9; display: flex; gap: 16px; flex-wrap: wrap; }
        .patient-banner-alerts { display: flex; gap: 8px; }
        .banner-alert { padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .banner-alert-critical { background: #dc2626; }
        .banner-alert-warning { background: #f59e0b; }
        
        /* Calendar Styles */
        .emr-calendar-week {
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 8px;
            margin: 16px 0;
        }
        .emr-calendar-day {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 8px;
            min-height: 200px;
        }
        .emr-calendar-day.today {
            border-color: #3b82f6;
            background: #eff6ff;
        }
        .emr-day-header {
            text-align: center;
            padding-bottom: 8px;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 8px;
        }
        .emr-day-header .day-name { display: block; font-size: 11px; color: #64748b; text-transform: uppercase; }
        .emr-day-header .day-num { display: block; font-size: 18px; font-weight: 600; color: #1e293b; }
        .emr-day-summary { 
            display: flex; 
            justify-content: space-between; 
            font-size: 10px; 
            margin-bottom: 8px;
            padding: 4px 0;
        }
        .available-count { color: #059669; }
        .booked-count { color: #dc2626; }
        .emr-day-slots { display: flex; flex-direction: column; gap: 4px; }
        .emr-slot {
            padding: 6px 8px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .emr-slot.slot-available { background: #d1fae5; color: #065f46; }
        .emr-slot.slot-available:hover { background: #a7f3d0; }
        .emr-slot.slot-booked { background: #fee2e2; color: #991b1b; }
        .emr-slot.slot-blocked { background: #f3f4f6; color: #6b7280; }
        .slot-time { font-weight: 500; }
        .slot-provider { font-size: 10px; opacity: 0.8; }
        .more-slots { text-align: center; font-size: 10px; color: #64748b; padding: 4px; }
        
        /* Providers List */
        .emr-providers-list {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 16px;
        }
        .providers-header {
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            margin-bottom: 8px;
        }
        .provider-item {
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            margin-bottom: 4px;
        }
        .provider-item:hover { background: #f1f5f9; }
        .provider-item.active { background: #dbeafe; }
        .provider-name { display: block; font-weight: 500; font-size: 13px; color: #1e293b; }
        .provider-specialty { display: block; font-size: 11px; color: #64748b; }
        
        /* Modal Styles */
        .emr-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1000;
        }
        .emr-modal-content {
            background: white;
            border-radius: 12px;
            width: 500px;
            max-width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        .emr-modal-header {
            padding: 16px 20px;
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .emr-modal-header h3 { margin: 0; font-size: 18px; color: #1e293b; }
        .modal-close {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            color: #64748b;
        }
        .modal-close:hover { color: #1e293b; }
        .emr-modal-body { padding: 20px; }
        .emr-modal-footer {
            padding: 16px 20px;
            border-top: 1px solid #e2e8f0;
            display: flex;
            justify-content: flex-end;
            gap: 8px;
        }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; font-size: 13px; font-weight: 500; color: #374151; margin-bottom: 6px; }
        .form-group select, .form-group input, .form-group textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 14px;
        }
        .form-group select:focus, .form-group input:focus, .form-group textarea:focus {
            outline: none;
            border-color: #3b82f6;
            box-shadow: 0 0 0 3px rgba(59,130,246,0.1);
        }
        .btn-primary {
            padding: 10px 20px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }
        .btn-primary:hover { background: #2563eb; }
        .btn-secondary {
            padding: 10px 20px;
            background: white;
            color: #374151;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
        }
        .btn-secondary:hover { background: #f3f4f6; }
        .hint { color: #9ca3af; font-size: 13px; font-style: italic; }
        
        /* Scheduling Actions */
        .scheduling-actions {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        .schedule-btn {
            padding: 8px 16px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
        }
        .schedule-btn:hover { background: #2563eb; }
        .schedule-btn-outline {
            padding: 8px 16px;
            background: white;
            color: #3b82f6;
            border: 1px solid #3b82f6;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
        }
        .schedule-btn-outline:hover { background: #eff6ff; }
        
        /* Appointments List */
        .appointments-list { margin-top: 16px; }
        .appointment-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 8px;
        }
        .appointment-item:hover { border-color: #3b82f6; }
        .appt-time { font-weight: 600; color: #1e40af; min-width: 80px; }
        .appt-info { flex: 1; }
        .appt-patient { font-weight: 500; color: #1e293b; }
        .appt-details { font-size: 12px; color: #64748b; }
        .appt-status {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .appt-status-scheduled { background: #dbeafe; color: #1e40af; }
        .appt-status-confirmed { background: #d1fae5; color: #065f46; }
        .appt-status-checked-in { background: #f3e8ff; color: #7c3aed; }
        .appt-status-completed { background: #f3f4f6; color: #4b5563; }
        .appt-status-no-show { background: #fee2e2; color: #991b1b; }
        
        /* =============== ORDERS TAB STYLES =============== */
        .orders-container { padding: 16px; }
        .orders-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .orders-header h3 { margin: 0; color: #1e293b; font-size: 18px; }
        .order-btn { padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
        .order-btn:hover { background: #2563eb; }
        
        .orders-summary { display: flex; gap: 16px; margin-bottom: 20px; }
        .summary-card { flex: 1; padding: 16px; border-radius: 8px; text-align: center; }
        .summary-pending { background: #fef3c7; border: 1px solid #fcd34d; }
        .summary-progress { background: #dbeafe; border: 1px solid #93c5fd; }
        .summary-complete { background: #d1fae5; border: 1px solid #6ee7b7; }
        .summary-count { font-size: 28px; font-weight: 700; color: #1e293b; }
        .summary-label { font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 500; }
        
        .orders-filters { display: flex; gap: 12px; margin-bottom: 16px; }
        .order-filter { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; min-width: 150px; }
        
        .orders-list { background: white; border: 1px solid #e2e8f0; border-radius: 8px; }
        .order-row { display: flex; align-items: center; padding: 16px; border-bottom: 1px solid #e2e8f0; gap: 12px; }
        .order-row:last-child { border-bottom: none; }
        .order-row:hover { background: #f8fafc; }
        .order-icon { font-size: 24px; width: 40px; text-align: center; }
        .order-info { flex: 1; }
        .order-name { font-weight: 500; color: #1e293b; margin-bottom: 4px; }
        .order-meta { font-size: 12px; color: #64748b; display: flex; gap: 12px; }
        .order-type { background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
        .order-status-area { display: flex; align-items: center; gap: 8px; }
        .order-status { padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
        .status-pending { background: #fef3c7; color: #92400e; }
        .status-progress { background: #dbeafe; color: #1e40af; }
        .status-complete { background: #d1fae5; color: #065f46; }
        .status-cancelled { background: #fee2e2; color: #991b1b; }
        .result-badge { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
        .result-normal { background: #d1fae5; color: #065f46; }
        .result-abnormal { background: #fef3c7; color: #92400e; }
        .result-critical { background: #fee2e2; color: #991b1b; }
        .no-orders { padding: 40px; text-align: center; color: #64748b; }
        
        /* =============== BILLING TAB STYLES =============== */
        .billing-container { padding: 16px; }
        .billing-header { margin-bottom: 20px; }
        .billing-header h3 { margin: 0; color: #1e293b; font-size: 18px; }
        
        .billing-summary { display: flex; gap: 16px; margin-bottom: 24px; }
        .billing-card { flex: 1; background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; text-align: center; }
        .billing-card-title { font-size: 12px; color: #64748b; text-transform: uppercase; font-weight: 500; margin-bottom: 8px; }
        .billing-card-amount { font-size: 24px; font-weight: 700; color: #1e293b; }
        
        .billing-tabs { display: flex; border-bottom: 2px solid #e2e8f0; margin-bottom: 16px; }
        .billing-tab { padding: 12px 20px; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; font-size: 14px; font-weight: 500; color: #64748b; }
        .billing-tab:hover { color: #1e40af; }
        .billing-tab.active { color: #1e40af; border-bottom-color: #1e40af; }
        
        .billing-section { display: none; }
        .billing-section.active { display: block; }
        
        .claims-summary { display: flex; gap: 16px; margin-bottom: 16px; font-size: 13px; }
        .claim-stat { padding: 4px 12px; background: #f1f5f9; border-radius: 4px; }
        .claim-denied { background: #fee2e2; color: #991b1b; }
        
        .billing-table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }
        .billing-table th { background: #f8fafc; padding: 12px; text-align: left; font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
        .billing-table td { padding: 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px; }
        .billing-table tr:last-child td { border-bottom: none; }
        .billing-table tr:hover { background: #f8fafc; }
        .claim-number { font-family: monospace; color: #1e40af; }
        .cpt-code { font-family: monospace; font-weight: 500; }
        .claim-status { padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .status-paid { background: #d1fae5; color: #065f46; }
        .status-denied { background: #fee2e2; color: #991b1b; }
        .balance-due { color: #dc2626; font-weight: 600; }
        .payment-amount { color: #059669; font-weight: 600; }
        .no-data { text-align: center; color: #64748b; font-style: italic; padding: 20px !important; }
        
        /* =============== MESSAGES TAB STYLES =============== */
        .messages-container { padding: 16px; }
        .messages-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .messages-header h3 { margin: 0; color: #1e293b; font-size: 18px; }
        .message-btn { padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 500; }
        .message-btn:hover { background: #2563eb; }
        
        .messages-summary { display: flex; gap: 24px; margin-bottom: 20px; }
        .msg-stat { text-align: center; }
        .msg-stat-count { display: block; font-size: 24px; font-weight: 700; color: #1e293b; }
        .msg-stat-label { font-size: 12px; color: #64748b; text-transform: uppercase; }
        
        .messages-filters { display: flex; gap: 12px; margin-bottom: 16px; }
        .msg-filter { padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 13px; min-width: 150px; }
        
        .messages-list { background: white; border: 1px solid #e2e8f0; border-radius: 8px; }
        .message-thread { display: flex; align-items: flex-start; padding: 16px; border-bottom: 1px solid #e2e8f0; gap: 12px; cursor: pointer; }
        .message-thread:last-child { border-bottom: none; }
        .message-thread:hover { background: #f8fafc; }
        .message-thread.msg-unread { background: #eff6ff; }
        .thread-icon { font-size: 24px; width: 40px; text-align: center; }
        .thread-content { flex: 1; }
        .thread-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
        .thread-subject { font-weight: 500; color: #1e293b; }
        .priority-badge { background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
        .thread-preview { font-size: 13px; color: #64748b; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 400px; }
        .thread-meta { display: flex; gap: 12px; font-size: 11px; color: #9ca3af; }
        .thread-status-area { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
        .thread-status { padding: 4px 10px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; }
        .thread-status.status-open { background: #dbeafe; color: #1e40af; }
        .thread-status.status-closed { background: #f3f4f6; color: #4b5563; }
        .unread-badge { background: #dc2626; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
        .no-messages { padding: 40px; text-align: center; color: #64748b; }
    '''


def _get_unified_common_script() -> str:
    """Return common JavaScript for unified EMR."""
    return '''
    <script>
        let selectedPatient = null;
        let selectedSlot = null;
        let currentTab = 'chart';
        
        // Tab switching
        function switchTab(tabName) {
            currentTab = tabName;
            document.querySelectorAll('.emr-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.emr-tab-content').forEach(c => c.classList.remove('active'));
            
            document.querySelector(`.emr-tab[data-tab="${tabName}"]`).classList.add('active');
            document.getElementById(`tab-${tabName}`).classList.add('active');
            
            // Load scheduling data if switching to scheduling tab
            if (tabName === 'scheduling') {
                loadSchedulingData();
            }
        }
        
        // Patient selection (updates banner and loads patient data)
        function selectPatient(element, patientKey) {
            // Remove active from all patient items
            document.querySelectorAll('[onclick^="selectPatient"]').forEach(el => {
                el.classList.remove('active', 'selected');
            });
            element.classList.add('active', 'selected');
            
            // Get patient info from data attributes
            const mrn = element.dataset.patientMrn || element.dataset.cernerMrn || 
                       element.dataset.allscriptsId || element.dataset.athenaRecordNumber || 
                       element.dataset.netsmartMrn || element.dataset.qualifactsMrn ||
                       element.dataset.id || '';
            const name = element.dataset.patientName || element.dataset.cernerPatient || 
                        element.dataset.allscriptsName || element.dataset.athenaFullName || 
                        element.dataset.netsmartClient || element.dataset.qualifactsClient ||
                        element.dataset.name || '';
            
            selectedPatient = { key: patientKey, mrn: mrn, name: name };
            
            // Update patient banner
            updatePatientBanner(patientKey);
            
            // Show/hide detail panels
            document.querySelectorAll('.detail-panel').forEach(p => p.style.display = 'none');
            const panel = document.getElementById('detail-' + patientKey);
            if (panel) panel.style.display = 'block';
            
            // Update hidden context element
            let contextEl = document.getElementById('mobius-patient-context');
            if (!contextEl) {
                contextEl = document.createElement('div');
                contextEl.id = 'mobius-patient-context';
                contextEl.style.display = 'none';
                document.body.appendChild(contextEl);
            }
            contextEl.setAttribute('data-patient-mrn', mrn);
            contextEl.setAttribute('data-patient-name', name);
            contextEl.setAttribute('data-patient-key', patientKey);
            
            console.log('[Unified EMR] Selected patient:', selectedPatient);
        }
        
        function updatePatientBanner(patientKey) {
            const banner = document.getElementById('patient-banner');
            if (!banner) return;
            
            const detailPanel = document.getElementById('detail-' + patientKey);
            if (detailPanel) {
                // Get patient info from the detail panel's data or content
                const nameEl = detailPanel.querySelector('.patient-name, h2, .epic-patient-name, .athena-name');
                const name = nameEl ? nameEl.textContent : 'Unknown Patient';
                
                // Update banner content
                const bannerName = banner.querySelector('.patient-banner-name');
                if (bannerName) bannerName.textContent = name;
                
                const bannerMrn = banner.querySelector('.patient-banner-mrn');
                if (bannerMrn && selectedPatient) bannerMrn.textContent = 'MRN: ' + selectedPatient.mrn;
            }
            
            banner.style.display = 'flex';
        }
        
        // Scheduling functions
        function loadSchedulingData() {
            // Load calendar data via API
            fetch('/mock-emr/api/schedule/calendar?view=week')
                .then(r => r.json())
                .then(data => {
                    console.log('[EMR] Loaded scheduling data:', data);
                })
                .catch(err => console.error('Failed to load scheduling:', err));
        }
        
        function selectSlot(slotId) {
            selectedSlot = slotId;
            document.querySelectorAll('.emr-slot').forEach(s => s.classList.remove('selected'));
            const slotEl = document.querySelector(`[data-slot-id="${slotId}"]`);
            if (slotEl) {
                slotEl.classList.add('selected');
                if (slotEl.classList.contains('slot-available')) {
                    openBookingModal(slotId);
                }
            }
        }
        
        function filterByProvider(providerId) {
            document.querySelectorAll('.provider-item').forEach(p => p.classList.remove('active'));
            document.querySelector(`[data-provider-id="${providerId}"]`).classList.add('active');
            
            // Filter calendar slots
            document.querySelectorAll('.emr-slot').forEach(slot => {
                if (slot.dataset.providerId === providerId) {
                    slot.style.display = 'flex';
                } else {
                    slot.style.display = 'none';
                }
            });
        }
        
        function clearProviderFilter() {
            document.querySelectorAll('.provider-item').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.emr-slot').forEach(slot => slot.style.display = 'flex');
        }
        
        // Booking modal functions
        function openBookingModal(slotId = null) {
            if (!selectedPatient) {
                alert('Please select a patient first');
                return;
            }
            
            document.getElementById('booking-modal').style.display = 'flex';
            document.getElementById('booking-patient-id').value = selectedPatient.key;
            
            if (slotId) {
                document.getElementById('booking-slot-id').value = slotId;
            }
        }
        
        function closeBookingModal() {
            document.getElementById('booking-modal').style.display = 'none';
        }
        
        function loadAvailableSlots() {
            const providerId = document.getElementById('booking-provider').value;
            const date = document.getElementById('booking-date').value;
            
            if (!providerId || !date) return;
            
            fetch(`/mock-emr/api/schedule/slots?provider_id=${providerId}&date=${date}`)
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('available-slots-list');
                    if (data.slots && data.slots.length > 0) {
                        container.innerHTML = data.slots.map(slot => `
                            <label class="slot-option">
                                <input type="radio" name="slot" value="${slot.slot_id}" 
                                       onchange="document.getElementById('booking-slot-id').value='${slot.slot_id}'">
                                ${slot.start_time} - ${slot.end_time} (${slot.location || 'TBD'})
                            </label>
                        `).join('');
                    } else {
                        container.innerHTML = '<p class="hint">No available slots for this date</p>';
                    }
                })
                .catch(err => {
                    console.error('Failed to load slots:', err);
                });
        }
        
        function submitBooking(event) {
            event.preventDefault();
            
            const slotId = document.getElementById('booking-slot-id').value;
            const patientId = document.getElementById('booking-patient-id').value;
            const appointmentType = document.getElementById('booking-type').value;
            const visitReason = document.getElementById('booking-reason').value;
            
            if (!slotId) {
                alert('Please select a time slot');
                return;
            }
            
            fetch('/mock-emr/api/schedule/book', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    slot_id: slotId,
                    patient_context_id: patientId,
                    appointment_type: appointmentType,
                    visit_reason: visitReason
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.ok) {
                    alert('Appointment booked successfully!');
                    closeBookingModal();
                    location.reload();
                } else {
                    alert('Error: ' + (data.error || 'Failed to book appointment'));
                }
            })
            .catch(err => {
                console.error('Booking failed:', err);
                alert('Failed to book appointment');
            });
        }
        
        // Event listeners for booking form
        document.addEventListener('DOMContentLoaded', function() {
            const providerSelect = document.getElementById('booking-provider');
            const dateInput = document.getElementById('booking-date');
            
            if (providerSelect) providerSelect.addEventListener('change', loadAvailableSlots);
            if (dateInput) dateInput.addEventListener('change', loadAvailableSlots);
            
            // Auto-select first patient
            const firstPatient = document.querySelector('[onclick^="selectPatient"]');
            if (firstPatient) {
                const match = firstPatient.getAttribute('onclick').match(/'([^']+)'/);
                if (match) {
                    selectPatient(firstPatient, match[1]);
                }
            }
        });
        
        // Billing tab section switching
        function showBillingSection(section) {
            document.querySelectorAll('.billing-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.billing-section').forEach(s => s.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById('billing-' + section).classList.add('active');
        }
        
        // Orders filtering
        function filterOrders(type) {
            document.querySelectorAll('.order-row').forEach(row => {
                if (type === 'all' || row.dataset.orderType === type) {
                    row.style.display = 'flex';
                } else {
                    row.style.display = 'none';
                }
            });
        }
        
        function filterOrderStatus(status) {
            document.querySelectorAll('.order-row').forEach(row => {
                if (status === 'all' || row.dataset.orderStatus === status) {
                    row.style.display = 'flex';
                } else {
                    row.style.display = 'none';
                }
            });
        }
    </script>
    '''


def _render_unified_epic_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Epic-like EMR with tabbed layout."""
    
    # Build patient list items
    patient_items = []
    for p in patients:
        alert_class = "epic-alert" if p["critical_alert"] else ""
        patient_items.append(f'''
        <div class="epic-patient-item {alert_class}" 
             data-patient-mrn="{p['mrn'] or ''}"
             data-patient-name="{p['display_name'] or ''}"
             data-patient-context-id="{p['patient_context_id']}"
             onclick="selectPatient(this, '{p['patient_key']}')">
            <div class="epic-patient-name">{p['display_name'] or 'Unknown'}</div>
            <div class="epic-patient-mrn">{p['mrn'] or 'N/A'}</div>
        </div>
        ''')
    
    # Build chart tab content (clinical data)
    chart_panels = _build_detail_panels(patients, "epic")
    
    # Build scheduling tab content
    calendar_html = _build_scheduling_calendar_html(scheduling_data, style)
    providers_html = _build_providers_list_html(scheduling_data, style)
    booking_modal = _build_appointment_booking_modal_html(scheduling_data, style)
    
    # Build appointments list for today
    appointments = scheduling_data.get("today_appointments", [])
    appointments_html = '<div class="appointments-list">'
    appointments_html += '<h3>Today\'s Appointments</h3>'
    
    if appointments:
        for appt in appointments[:10]:
            time_str = appt.scheduled_time.strftime("%I:%M %p") if appt.scheduled_time else ""
            status_class = f"appt-status-{appt.status.replace('_', '-')}"
            appointments_html += f'''
            <div class="appointment-item" data-appointment-id="{appt.appointment_id}">
                <span class="appt-time">{time_str}</span>
                <div class="appt-info">
                    <div class="appt-patient">{appt.provider_name or 'Unassigned'}</div>
                    <div class="appt-details">{appt.appointment_type.replace('_', ' ').title()} | {appt.location or 'TBD'}</div>
                </div>
                <span class="appt-status {status_class}">{appt.status.replace('_', ' ')}</span>
            </div>
            '''
    else:
        appointments_html += '<p class="hint">No appointments scheduled for today</p>'
    
    appointments_html += '</div>'
    
    # Build Orders tab content
    orders_html = _build_orders_tab_html(orders_data)
    
    # Build Billing tab content
    billing_html = _build_billing_tab_html(billing_data)
    
    # Build Messages tab content
    messages_html = _build_messages_tab_html(messages_data)
    
    common_styles = _get_unified_common_styles()
    common_script = _get_unified_common_script()
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EpicCare - Unified EMR</title>
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
            flex-shrink: 0;
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
        
        .epic-main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
        
        /* Patient Banner */
        #patient-banner {{
            display: none;
        }}
        
        /* Tabs */
        .emr-tabs {{
            background: #f0f7ff;
            border-bottom: 2px solid #ccd9e8;
        }}
        .emr-tab {{ color: #1e3a5f; }}
        .emr-tab.active {{ border-bottom-color: #2c5282; color: #2c5282; }}
        
        .epic-content {{ flex: 1; overflow-y: auto; padding: 0; background: white; }}
        
        /* Epic-specific detail styles */
        .epic-detail {{ background: white; border-radius: 8px; margin: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
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
        
        /* Scheduling tab layout */
        .scheduling-layout {{
            display: grid;
            grid-template-columns: 220px 1fr;
            gap: 16px;
            padding: 16px;
            height: 100%;
        }}
        .scheduling-sidebar {{ overflow-y: auto; }}
        .scheduling-main {{ overflow-y: auto; }}
        
        {common_styles}
        
        .epic-style-badge {{ position: fixed; bottom: 16px; right: 16px; background: #2c5282; color: white; padding: 8px 16px; border-radius: 20px; font-size: 12px; z-index: 100; }}
    </style>
</head>
<body>
    <header class="epic-header">
        <div class="epic-logo">EpicCare</div>
        <div class="epic-header-info">Unified EMR | Style: {style} | Patients: {len(patients)}</div>
    </header>
    
    <div class="epic-container">
        <aside class="epic-sidebar">
            <div class="epic-sidebar-header">Patient List</div>
            {"".join(patient_items)}
        </aside>
        
        <main class="epic-main">
            <!-- Patient Banner (shown when patient selected) -->
            <div id="patient-banner" class="patient-banner">
                <div class="patient-banner-photo">?</div>
                <div class="patient-banner-info">
                    <div class="patient-banner-name">Select a Patient</div>
                    <div class="patient-banner-details">
                        <span class="patient-banner-mrn">MRN: --</span>
                        <span>DOB: --</span>
                    </div>
                </div>
                <div class="patient-banner-alerts"></div>
            </div>
            
            <!-- Tab Navigation -->
            <div class="emr-tabs">
                <div class="emr-tab active" data-tab="chart" onclick="switchTab('chart')">Chart</div>
                <div class="emr-tab" data-tab="scheduling" onclick="switchTab('scheduling')">Scheduling</div>
                <div class="emr-tab" data-tab="orders" onclick="switchTab('orders')">Orders</div>
                <div class="emr-tab" data-tab="billing" onclick="switchTab('billing')">Billing</div>
                <div class="emr-tab" data-tab="messages" onclick="switchTab('messages')">Messages</div>
            </div>
            
            <div class="epic-content">
                <!-- Chart Tab -->
                <div id="tab-chart" class="emr-tab-content active">
                    {chart_panels}
                </div>
                
                <!-- Scheduling Tab -->
                <div id="tab-scheduling" class="emr-tab-content">
                    <div class="scheduling-layout">
                        <div class="scheduling-sidebar">
                            <div class="scheduling-actions">
                                <button class="schedule-btn" onclick="openBookingModal()">+ New Appointment</button>
                            </div>
                            {providers_html}
                            <button class="schedule-btn-outline" onclick="clearProviderFilter()">Clear Filter</button>
                        </div>
                        <div class="scheduling-main">
                            <h3 style="margin-bottom: 16px; color: #1e3a5f;">Weekly Schedule</h3>
                            {calendar_html}
                            {appointments_html}
                        </div>
                    </div>
                </div>
                
                <!-- Orders Tab -->
                <div id="tab-orders" class="emr-tab-content">
                    {orders_html}
                </div>
                
                <!-- Billing Tab -->
                <div id="tab-billing" class="emr-tab-content">
                    {billing_html}
                </div>
                
                <!-- Messages Tab -->
                <div id="tab-messages" class="emr-tab-content">
                    {messages_html}
                </div>
            </div>
        </main>
    </div>
    
    {booking_modal}
    
    <div class="epic-style-badge">EMR Style: Epic (Unified)</div>
    
    {common_script}
</body>
</html>'''


# Create simplified unified renderers for other styles that delegate to the Epic renderer with style-specific adjustments
def _render_unified_cerner_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Cerner-like EMR - uses Epic base with Cerner colors."""
    # For brevity, delegate to Epic with Cerner-specific styling
    return _render_unified_epic_style(patients, scheduling_data, orders_data, billing_data, messages_data, style).replace(
        '#1e3a5f', '#d35400').replace('#2c5282', '#e67e22').replace('EpicCare', 'Cerner PowerChart'
    ).replace('EMR Style: Epic', 'EMR Style: Cerner')


def _render_unified_allscripts_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Allscripts-like EMR."""
    return _render_unified_epic_style(patients, scheduling_data, orders_data, billing_data, messages_data, style).replace(
        '#1e3a5f', '#2e7d32').replace('#2c5282', '#4caf50').replace('EpicCare', 'Allscripts Professional'
    ).replace('EMR Style: Epic', 'EMR Style: Allscripts')


def _render_unified_athena_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Athena-like EMR."""
    return _render_unified_epic_style(patients, scheduling_data, orders_data, billing_data, messages_data, style).replace(
        '#1e3a5f', '#6b21a8').replace('#2c5282', '#9333ea').replace('EpicCare', 'athenaOne'
    ).replace('EMR Style: Epic', 'EMR Style: Athena')


def _render_unified_legacy_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Legacy-style EMR."""
    return _render_unified_epic_style(patients, scheduling_data, orders_data, billing_data, messages_data, style).replace(
        '#1e3a5f', '#333333').replace('#2c5282', '#666666').replace('EpicCare', 'Medical Records System v2.1'
    ).replace('EMR Style: Epic', 'EMR Style: Legacy')


def _render_unified_netsmart_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Netsmart-like EMR."""
    return _render_unified_epic_style(patients, scheduling_data, orders_data, billing_data, messages_data, style).replace(
        '#1e3a5f', '#0d4f5c').replace('#2c5282', '#147a8a').replace('EpicCare', 'myAvatar NX'
    ).replace('EMR Style: Epic', 'EMR Style: Netsmart')


def _render_unified_qualifacts_style(patients: list, scheduling_data: dict, orders_data: dict, billing_data: dict, messages_data: dict, style: str) -> str:
    """Render unified Qualifacts-like EMR."""
    return _render_unified_epic_style(patients, scheduling_data, orders_data, billing_data, messages_data, style).replace(
        '#1e3a5f', '#4f46e5').replace('#2c5282', '#6366f1').replace('EpicCare', 'CareLogic'
    ).replace('EMR Style: Epic', 'EMR Style: Qualifacts')


# =============================================================================
# LEGACY EPIC-STYLE RENDERER (kept for backward compatibility)
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
# NETSMART (myAvatar) STYLE - Behavioral Health Focus
# =============================================================================

def _render_netsmart_style(patients: list, style: str) -> str:
    """Render Netsmart myAvatar-like EMR with teal/dark theme for behavioral health."""
    
    patient_rows = []
    for p in patients:
        status = "critical" if p["critical_alert"] else ("review" if p["needs_review"] else "active")
        status_dot = {"critical": "🔴", "review": "🟡", "active": "🟢"}.get(status, "⚪")
        patient_rows.append(f'''
        <div class="netsmart-client-row {status}" 
             data-netsmart-mrn="{p['mrn'] or ''}"
             data-netsmart-client="{p['display_name'] or ''}"
             onclick="selectPatient(this, '{p['patient_key']}')">
            <span class="netsmart-status">{status_dot}</span>
            <span class="netsmart-name">{p['display_name'] or 'Unknown'}</span>
            <span class="netsmart-id">{p['mrn'] or 'N/A'}</span>
            <span class="netsmart-dob">{p['dob'] or 'N/A'}</span>
        </div>
        ''')
    
    detail_panels = _build_detail_panels(patients, style)
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <title>myAvatar NX - Netsmart</title>
    <meta charset="utf-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #1a2332;
            color: #e8ecf1;
            min-height: 100vh;
        }}
        .netsmart-header {{
            background: linear-gradient(135deg, #0d4f5c 0%, #147a8a 100%);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 2px solid #00a5b5;
        }}
        .netsmart-logo {{
            font-size: 22px;
            font-weight: 700;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .netsmart-logo-icon {{
            width: 32px;
            height: 32px;
            background: #00d4e5;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
        }}
        .netsmart-nav {{
            display: flex;
            gap: 4px;
        }}
        .netsmart-nav-item {{
            padding: 8px 16px;
            color: rgba(255,255,255,0.8);
            cursor: pointer;
            border-radius: 6px 6px 0 0;
            font-size: 13px;
            transition: all 0.2s;
        }}
        .netsmart-nav-item:hover, .netsmart-nav-item.active {{
            background: rgba(255,255,255,0.15);
            color: #fff;
        }}
        .netsmart-user {{
            display: flex;
            align-items: center;
            gap: 12px;
            color: rgba(255,255,255,0.9);
            font-size: 13px;
        }}
        .netsmart-user-avatar {{
            width: 36px;
            height: 36px;
            background: #00a5b5;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
        }}
        .netsmart-container {{
            display: flex;
            height: calc(100vh - 56px);
        }}
        .netsmart-sidebar {{
            width: 280px;
            background: #243447;
            border-right: 1px solid #3a4d63;
            display: flex;
            flex-direction: column;
        }}
        .netsmart-search {{
            padding: 16px;
            border-bottom: 1px solid #3a4d63;
        }}
        .netsmart-search input {{
            width: 100%;
            padding: 10px 14px;
            background: #1a2332;
            border: 1px solid #3a4d63;
            border-radius: 6px;
            color: #e8ecf1;
            font-size: 13px;
        }}
        .netsmart-search input::placeholder {{ color: #6b7a8f; }}
        .netsmart-client-list {{
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }}
        .netsmart-client-row {{
            display: grid;
            grid-template-columns: 24px 1fr 100px 90px;
            gap: 8px;
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            align-items: center;
            margin-bottom: 4px;
            transition: all 0.15s;
        }}
        .netsmart-client-row:hover {{ background: rgba(0,165,181,0.15); }}
        .netsmart-client-row.active, .netsmart-client-row.selected {{ 
            background: rgba(0,165,181,0.25);
            border: 1px solid #00a5b5;
        }}
        .netsmart-client-row.critical {{ border-left: 3px solid #ef4444; }}
        .netsmart-client-row.review {{ border-left: 3px solid #f59e0b; }}
        .netsmart-name {{ font-weight: 500; font-size: 14px; }}
        .netsmart-id {{ color: #6b7a8f; font-size: 12px; font-family: monospace; }}
        .netsmart-dob {{ color: #6b7a8f; font-size: 12px; }}
        .netsmart-main {{
            flex: 1;
            background: #1e2d3d;
            overflow-y: auto;
        }}
        .netsmart-toolbar {{
            background: #243447;
            padding: 12px 20px;
            display: flex;
            gap: 12px;
            border-bottom: 1px solid #3a4d63;
        }}
        .netsmart-btn {{
            padding: 8px 16px;
            background: #147a8a;
            color: #fff;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
        }}
        .netsmart-btn:hover {{ background: #0d6570; }}
        .netsmart-content {{
            padding: 20px;
        }}
        .detail-panel {{ display: none; }}
        .detail-panel.active {{ display: block; }}
        .netsmart-detail-card {{
            background: #243447;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 16px;
        }}
        .netsmart-detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid #3a4d63;
        }}
        .netsmart-client-name {{
            font-size: 24px;
            font-weight: 600;
            color: #fff;
        }}
        .netsmart-client-meta {{
            font-size: 13px;
            color: #6b7a8f;
            margin-top: 4px;
        }}
        .netsmart-section {{
            margin-bottom: 20px;
        }}
        .netsmart-section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #00d4e5;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .netsmart-pill {{
            display: inline-block;
            padding: 4px 12px;
            background: rgba(0,165,181,0.2);
            color: #00d4e5;
            border-radius: 20px;
            font-size: 12px;
            margin: 2px 4px 2px 0;
        }}
        .netsmart-pill.danger {{
            background: rgba(239,68,68,0.2);
            color: #f87171;
        }}
        .netsmart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 16px;
        }}
        .netsmart-stat {{
            background: #1a2332;
            padding: 16px;
            border-radius: 8px;
        }}
        .netsmart-stat-label {{
            font-size: 11px;
            color: #6b7a8f;
            text-transform: uppercase;
            margin-bottom: 4px;
        }}
        .netsmart-stat-value {{
            font-size: 18px;
            font-weight: 600;
            color: #fff;
        }}
        .netsmart-style-badge {{
            position: fixed;
            top: 70px;
            right: 20px;
            background: #00a5b5;
            color: #fff;
            padding: 6px 14px;
            border-radius: 16px;
            font-size: 11px;
            font-weight: 600;
            z-index: 100;
        }}
        .netsmart-ai-badge {{
            background: linear-gradient(135deg, #8b5cf6, #06b6d4);
            color: #fff;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }}
    </style>
</head>
<body>
    <div class="netsmart-header">
        <div class="netsmart-logo">
            <span class="netsmart-logo-icon">🏥</span>
            myAvatar NX
        </div>
        <div class="netsmart-nav">
            <span class="netsmart-nav-item active">Dashboard</span>
            <span class="netsmart-nav-item">Clients</span>
            <span class="netsmart-nav-item">Scheduling</span>
            <span class="netsmart-nav-item">Clinical</span>
            <span class="netsmart-nav-item">Billing</span>
            <span class="netsmart-nav-item">Reports</span>
        </div>
        <div class="netsmart-user">
            <span class="netsmart-ai-badge">✨ Bells AI</span>
            <span>Dr. Sarah Miller</span>
            <div class="netsmart-user-avatar">SM</div>
        </div>
    </div>
    <div class="netsmart-container">
        <div class="netsmart-sidebar">
            <div class="netsmart-search">
                <input type="text" placeholder="Search clients..." />
            </div>
            <div class="netsmart-client-list">
                {"".join(patient_rows)}
            </div>
        </div>
        <div class="netsmart-main">
            <div class="netsmart-toolbar">
                <button class="netsmart-btn">📋 New Note</button>
                <button class="netsmart-btn">📅 Schedule</button>
                <button class="netsmart-btn">💊 Medications</button>
                <button class="netsmart-btn">📊 Assessments</button>
            </div>
            <div class="netsmart-content">
                {detail_panels}
            </div>
        </div>
    </div>
    <div class="netsmart-style-badge">Style: Netsmart | Clients: {len(patients)}</div>
    {_get_common_script()}
</body>
</html>'''


# =============================================================================
# QUALIFACTS (CareLogic) STYLE - Modern Behavioral Health
# =============================================================================

def _render_qualifacts_style(patients: list, style: str) -> str:
    """Render Qualifacts CareLogic-like EMR with modern light theme."""
    
    patient_cards = []
    for p in patients:
        status_class = "critical" if p["critical_alert"] else ("review" if p["needs_review"] else "")
        status_badge = '<span class="qf-badge qf-badge-critical">Critical</span>' if p["critical_alert"] else (
            '<span class="qf-badge qf-badge-review">Review</span>' if p["needs_review"] else '')
        patient_cards.append(f'''
        <div class="qf-client-card {status_class}" 
             data-qualifacts-mrn="{p['mrn'] or ''}"
             data-qualifacts-client="{p['display_name'] or ''}"
             onclick="selectPatient(this, '{p['patient_key']}')">
            <div class="qf-client-info">
                <span class="qf-client-name">{p['display_name'] or 'Unknown'}</span>
                <span class="qf-client-id">{p['mrn'] or 'N/A'}</span>
            </div>
            <div class="qf-client-meta">
                <span>DOB: {p['dob'] or 'N/A'}</span>
                {status_badge}
            </div>
        </div>
        ''')
    
    detail_panels = _build_detail_panels(patients, style)
    
    return f'''<!DOCTYPE html>
<html>
<head>
    <title>CareLogic - Qualifacts</title>
    <meta charset="utf-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f8fafc;
            color: #1e293b;
            min-height: 100vh;
        }}
        .qf-header {{
            background: #fff;
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #e2e8f0;
            height: 60px;
        }}
        .qf-logo {{
            font-size: 20px;
            font-weight: 700;
            color: #6366f1;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .qf-logo-mark {{
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #fff;
            font-size: 16px;
        }}
        .qf-nav {{
            display: flex;
            gap: 8px;
            height: 100%;
        }}
        .qf-nav-item {{
            padding: 0 20px;
            color: #64748b;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            display: flex;
            align-items: center;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }}
        .qf-nav-item:hover {{ color: #6366f1; }}
        .qf-nav-item.active {{
            color: #6366f1;
            border-bottom-color: #6366f1;
        }}
        .qf-user {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .qf-ai-btn {{
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: #fff;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            border: none;
        }}
        .qf-user-avatar {{
            width: 36px;
            height: 36px;
            background: #e0e7ff;
            color: #6366f1;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 14px;
        }}
        .qf-container {{
            display: flex;
            height: calc(100vh - 60px);
        }}
        .qf-sidebar {{
            width: 320px;
            background: #fff;
            border-right: 1px solid #e2e8f0;
            display: flex;
            flex-direction: column;
        }}
        .qf-sidebar-header {{
            padding: 20px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .qf-sidebar-title {{
            font-size: 16px;
            font-weight: 600;
            color: #1e293b;
            margin-bottom: 12px;
        }}
        .qf-search {{
            position: relative;
        }}
        .qf-search input {{
            width: 100%;
            padding: 10px 14px 10px 38px;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            font-size: 14px;
            color: #1e293b;
        }}
        .qf-search input:focus {{
            outline: none;
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99,102,241,0.1);
        }}
        .qf-search::before {{
            content: "🔍";
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 14px;
        }}
        .qf-client-list {{
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }}
        .qf-client-card {{
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 14px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.15s;
        }}
        .qf-client-card:hover {{
            border-color: #6366f1;
            box-shadow: 0 2px 8px rgba(99,102,241,0.1);
        }}
        .qf-client-card.active, .qf-client-card.selected {{
            border-color: #6366f1;
            background: #f5f3ff;
        }}
        .qf-client-card.critical {{ border-left: 3px solid #ef4444; }}
        .qf-client-card.review {{ border-left: 3px solid #f59e0b; }}
        .qf-client-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}
        .qf-client-name {{
            font-weight: 600;
            font-size: 14px;
            color: #1e293b;
        }}
        .qf-client-id {{
            font-size: 12px;
            color: #64748b;
            font-family: 'JetBrains Mono', monospace;
        }}
        .qf-client-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: #64748b;
        }}
        .qf-badge {{
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
        .qf-badge-critical {{
            background: #fef2f2;
            color: #dc2626;
        }}
        .qf-badge-review {{
            background: #fffbeb;
            color: #d97706;
        }}
        .qf-main {{
            flex: 1;
            overflow-y: auto;
            padding: 24px;
        }}
        .detail-panel {{ display: none; }}
        .detail-panel.active {{ display: block; }}
        .qf-detail-card {{
            background: #fff;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            padding: 24px;
            margin-bottom: 16px;
        }}
        .qf-detail-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .qf-client-title {{
            font-size: 28px;
            font-weight: 700;
            color: #1e293b;
        }}
        .qf-client-subtitle {{
            font-size: 14px;
            color: #64748b;
            margin-top: 4px;
        }}
        .qf-actions {{
            display: flex;
            gap: 8px;
        }}
        .qf-btn {{
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            border: 1px solid #e2e8f0;
            background: #fff;
            color: #1e293b;
            transition: all 0.15s;
        }}
        .qf-btn:hover {{
            background: #f8fafc;
            border-color: #6366f1;
        }}
        .qf-btn-primary {{
            background: #6366f1;
            color: #fff;
            border-color: #6366f1;
        }}
        .qf-btn-primary:hover {{
            background: #4f46e5;
        }}
        .qf-section {{
            margin-bottom: 24px;
        }}
        .qf-section-title {{
            font-size: 13px;
            font-weight: 600;
            color: #6366f1;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .qf-pill {{
            display: inline-block;
            padding: 6px 14px;
            background: #f1f5f9;
            color: #475569;
            border-radius: 20px;
            font-size: 13px;
            margin: 2px 4px 2px 0;
        }}
        .qf-pill.danger {{
            background: #fef2f2;
            color: #dc2626;
        }}
        .qf-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 16px;
        }}
        .qf-stat {{
            background: #f8fafc;
            padding: 16px;
            border-radius: 10px;
        }}
        .qf-stat-label {{
            font-size: 12px;
            color: #64748b;
            margin-bottom: 4px;
        }}
        .qf-stat-value {{
            font-size: 20px;
            font-weight: 600;
            color: #1e293b;
        }}
        .qf-style-badge {{
            position: fixed;
            top: 70px;
            right: 20px;
            background: #6366f1;
            color: #fff;
            padding: 6px 14px;
            border-radius: 16px;
            font-size: 11px;
            font-weight: 600;
            z-index: 100;
        }}
        .qf-mbc {{
            background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
            border: 1px solid #86efac;
            border-radius: 10px;
            padding: 16px;
            margin-top: 16px;
        }}
        .qf-mbc-title {{
            font-size: 13px;
            font-weight: 600;
            color: #166534;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .qf-mbc-content {{
            font-size: 13px;
            color: #15803d;
        }}
    </style>
</head>
<body>
    <div class="qf-header">
        <div class="qf-logo">
            <span class="qf-logo-mark">Q</span>
            CareLogic
        </div>
        <div class="qf-nav">
            <span class="qf-nav-item active">Dashboard</span>
            <span class="qf-nav-item">Clients</span>
            <span class="qf-nav-item">Scheduling</span>
            <span class="qf-nav-item">Documentation</span>
            <span class="qf-nav-item">Billing</span>
            <span class="qf-nav-item">Reports</span>
        </div>
        <div class="qf-user">
            <button class="qf-ai-btn">✨ iQ Assistant</button>
            <div class="qf-user-avatar">SM</div>
        </div>
    </div>
    <div class="qf-container">
        <div class="qf-sidebar">
            <div class="qf-sidebar-header">
                <div class="qf-sidebar-title">Client Search</div>
                <div class="qf-search">
                    <input type="text" placeholder="Search by name or MRN..." />
                </div>
            </div>
            <div class="qf-client-list">
                {" ".join(patient_cards)}
            </div>
        </div>
        <div class="qf-main">
            {detail_panels}
        </div>
    </div>
    <div class="qf-style-badge">Style: Qualifacts | Clients: {len(patients)}</div>
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
        elif style == "netsmart":
            # Netsmart style pills
            netsmart_allergy_html = " ".join([f'<span class="netsmart-pill danger">{a}</span>' for a in allergies]) if allergies else '<span class="netsmart-pill">None reported</span>'
            panel = f'''
            <div class="detail-panel netsmart-detail-card" id="detail-{p['patient_key']}" style="display:none">
                <div class="netsmart-detail-header">
                    <div>
                        <div class="netsmart-client-name">{p['display_name'] or 'Unknown'}</div>
                        <div class="netsmart-client-meta">MRN: {p['mrn'] or 'N/A'} • DOB: {p['dob'] or 'N/A'} • Blood Type: {clinical.get('blood_type', 'N/A')}</div>
                    </div>
                    <span class="netsmart-ai-badge">✨ Bells AI Ready</span>
                </div>
                <div class="netsmart-grid">
                    <div class="netsmart-stat"><div class="netsmart-stat-label">Blood Pressure</div><div class="netsmart-stat-value">{vitals.get('bp', 'N/A')}</div></div>
                    <div class="netsmart-stat"><div class="netsmart-stat-label">Heart Rate</div><div class="netsmart-stat-value">{vitals.get('hr', 'N/A')} bpm</div></div>
                    <div class="netsmart-stat"><div class="netsmart-stat-label">Temperature</div><div class="netsmart-stat-value">{vitals.get('temp', 'N/A')}°F</div></div>
                    <div class="netsmart-stat"><div class="netsmart-stat-label">Weight</div><div class="netsmart-stat-value">{vitals.get('weight_lbs', 'N/A')} lbs</div></div>
                </div>
                <div class="netsmart-section"><div class="netsmart-section-title">Allergies</div>{netsmart_allergy_html}</div>
                <div class="netsmart-section"><div class="netsmart-section-title">Current Medications</div>{med_list}</div>
                <div class="netsmart-section"><div class="netsmart-section-title">Emergency Contact</div><p style="color:#e8ecf1">{clinical.get('emergency_contact_name', 'N/A')} ({clinical.get('emergency_contact_relation', '')}) - {clinical.get('emergency_contact_phone', 'N/A')}</p></div>
                <div class="netsmart-section"><div class="netsmart-section-title">Care Team</div><p style="color:#e8ecf1">Primary: {clinical.get('primary_care_provider', 'N/A')}</p></div>
            </div>
            '''
        elif style == "qualifacts":
            # Qualifacts style pills
            qf_allergy_html = " ".join([f'<span class="qf-pill danger">{a}</span>' for a in allergies]) if allergies else '<span class="qf-pill">None reported</span>'
            panel = f'''
            <div class="detail-panel qf-detail-card" id="detail-{p['patient_key']}" style="display:none">
                <div class="qf-detail-header">
                    <div>
                        <div class="qf-client-title">{p['display_name'] or 'Unknown'}</div>
                        <div class="qf-client-subtitle">MRN: {p['mrn'] or 'N/A'} • DOB: {p['dob'] or 'N/A'} • Blood Type: {clinical.get('blood_type', 'N/A')}</div>
                    </div>
                    <div class="qf-actions">
                        <button class="qf-btn">📋 Add Note</button>
                        <button class="qf-btn qf-btn-primary">📊 Assessments</button>
                    </div>
                </div>
                <div class="qf-grid">
                    <div class="qf-stat"><div class="qf-stat-label">Blood Pressure</div><div class="qf-stat-value">{vitals.get('bp', 'N/A')}</div></div>
                    <div class="qf-stat"><div class="qf-stat-label">Heart Rate</div><div class="qf-stat-value">{vitals.get('hr', 'N/A')} bpm</div></div>
                    <div class="qf-stat"><div class="qf-stat-label">Temperature</div><div class="qf-stat-value">{vitals.get('temp', 'N/A')}°F</div></div>
                    <div class="qf-stat"><div class="qf-stat-label">Weight</div><div class="qf-stat-value">{vitals.get('weight_lbs', 'N/A')} lbs</div></div>
                </div>
                <div class="qf-section"><div class="qf-section-title">Allergies</div>{qf_allergy_html}</div>
                <div class="qf-section"><div class="qf-section-title">Current Medications</div>{med_list}</div>
                <div class="qf-section"><div class="qf-section-title">Emergency Contact</div><p>{clinical.get('emergency_contact_name', 'N/A')} ({clinical.get('emergency_contact_relation', '')}) - {clinical.get('emergency_contact_phone', 'N/A')}</p></div>
                <div class="qf-section"><div class="qf-section-title">Care Team</div><p>Primary Provider: {clinical.get('primary_care_provider', 'N/A')}</p></div>
                <div class="qf-mbc">
                    <div class="qf-mbc-title">📈 Measurement-Based Care</div>
                    <div class="qf-mbc-content">PHQ-9: 8 (Mild) • GAD-7: 5 (Mild) • Last assessed: 7 days ago</div>
                </div>
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
            document.querySelectorAll('.detail-panel').forEach(p => {
                p.style.display = 'none';
                // Clear patient context from hidden panels
                p.removeAttribute('data-selected-patient-mrn');
            });
            
            // Get MRN from the clicked element (various EMR formats)
            const mrn = element.dataset.patientMrn || element.dataset.cernerMrn || 
                       element.dataset.allscriptsId || element.dataset.athenaRecordNumber || 
                       element.dataset.netsmartMrn || element.dataset.qualifactsMrn ||
                       element.dataset.id || '';
            const name = element.dataset.patientName || element.dataset.cernerPatient || 
                        element.dataset.allscriptsName || element.dataset.athenaFullName || 
                        element.dataset.netsmartClient || element.dataset.qualifactsClient ||
                        element.dataset.name || '';
            
            // Show selected detail panel and set patient context
            const detail = document.getElementById('detail-' + patientKey);
            if (detail) {
                detail.style.display = 'block';
                
                // Set data attributes on the visible detail panel for Mobius detection
                detail.setAttribute('data-selected-patient-mrn', mrn);
                detail.setAttribute('data-selected-patient-name', name);
                detail.setAttribute('data-patient-key', patientKey);
            }
            
            // Also update/create a dedicated context element for reliable detection
            let contextEl = document.getElementById('mobius-patient-context');
            if (!contextEl) {
                contextEl = document.createElement('div');
                contextEl.id = 'mobius-patient-context';
                contextEl.style.display = 'none';
                document.body.appendChild(contextEl);
            }
            contextEl.setAttribute('data-patient-mrn', mrn);
            contextEl.setAttribute('data-patient-name', name);
            contextEl.setAttribute('data-patient-key', patientKey);
            
            // Log for debugging
            console.log('[Mock EMR] Selected patient:', {
                patientKey: patientKey,
                mrn: mrn,
                name: name
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
