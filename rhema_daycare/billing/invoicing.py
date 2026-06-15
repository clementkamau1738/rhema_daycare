import frappe
from frappe import _
from frappe.utils import (
    today, get_first_day, get_last_day,
    add_days, now_datetime, get_time
)


def _settings():
    return frappe.get_cached_doc("Daycare Settings")


def _send_admin_alert(subject, message):
    try:
        email = _settings().get("admin_email") or ""
        if not email:
            frappe.log_error("Admin email not configured.", "Admin Alert Skipped")
            return
        frappe.sendmail(recipients=[email],
            subject=f"[Rhema Daycare] {subject}",
            message=message, now=True)
    except Exception as e:
        frappe.log_error(str(e), "Admin Alert Failed")


def generate_monthly_invoices():
    lock_key = f"rhema_invoice_lock_{today()[:7]}"
    if frappe.cache().get(lock_key):
        frappe.log_error("Invoice generation already ran this month.", "Billing Lock")
        return
    frappe.cache().set(lock_key, 1, ex=7200)

    settings = _settings()
    tuition_item = settings.get("tuition_item_code")
    if not tuition_item:
        _send_admin_alert("Invoice generation failed",
            "Daycare Settings missing Tuition Fee Item.")
        return

    period_start = get_first_day(today())
    period_end = get_last_day(today())
    company = frappe.db.get_single_value("Global Defaults", "default_company")

    all_classrooms = {
        c["name"]: c
        for c in frappe.get_all("Classroom", fields=["name", "monthly_fee"])
    }

    active_children = frappe.get_all("Child Profile",
        filters={"status": "Active"},
        fields=["name", "full_name", "guardian", "assigned_classroom"])

    created = 0
    skipped = []
    errors = []

    for child in active_children:
        sp = f"inv_{child['name']}"
        try:
            frappe.db.savepoint(sp)
            result = _create_invoice(child, period_start, period_end,
                all_classrooms, tuition_item, company)
            if result == "created":
                created += 1
            else:
                skipped.append(child["name"])
            frappe.db.release_savepoint(sp)
        except Exception as e:
            frappe.db.rollback(save_point=sp)
            errors.append({"child": child["name"], "error": str(e)})
            frappe.log_error(f"Invoice failed for {child['name']}: {e}",
                "Monthly Invoice Error")

    summary = (f"Invoice run {today()[:7]} — "
        f"Created: {created} | Skipped: {len(skipped)} | Errors: {len(errors)}")
    if errors:
        detail = "\n".join(f"  {e['child']}: {e['error']}" for e in errors)
        _send_admin_alert("Invoice errors", f"{summary}\n\n{detail}")
    else:
        frappe.log_error(summary, "Invoice Run Summary")


def _create_invoice(child, period_start, period_end,
                    classrooms, tuition_item, company):
    if not child.get("guardian"):
        frappe.log_error(f"Skipped {child['name']}: no guardian.", "Invoice Skip")
        return "skipped"

    classroom = classrooms.get(child.get("assigned_classroom"))
    if not classroom:
        frappe.log_error(f"Skipped {child['name']}: no classroom.", "Invoice Skip")
        return "skipped"

    if not classroom.get("monthly_fee") or float(classroom["monthly_fee"]) <= 0:
        frappe.log_error(
            f"Skipped {child['name']}: no monthly_fee on classroom.", "Invoice Skip")
        return "skipped"

    existing = frappe.db.exists("Sales Invoice", {
        "customer": child["guardian"],
        "rhema_child": child["name"],
        "posting_date": ["between", [period_start, period_end]],
        "docstatus": ["!=", 2]
    })
    if existing:
        return "skipped"

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = child["guardian"]
    invoice.posting_date = today()
    invoice.due_date = period_end
    invoice.rhema_child = child["name"]
    invoice.company = company
    invoice.append("items", {
        "item_code": tuition_item,
        "qty": 1,
        "rate": classroom["monthly_fee"],
        "description": f"Monthly tuition — {child['full_name']} — {period_start} to {period_end}"
    })
    invoice.flags.ignore_permissions = False
    invoice.insert()
    invoice.submit()
    return "created"


def send_payment_reminders():
    yesterday = add_days(today(), -1)
    overdue = frappe.get_all("Sales Invoice",
        filters={
            "status": "Overdue",
            "docstatus": 1,
            "due_date": ["<", yesterday],
            "outstanding_amount": [">", 0]
        },
        fields=["name", "customer", "outstanding_amount", "due_date", "rhema_child"])

    for inv in overdue:
        try:
            _send_payment_reminder(inv)
        except Exception as e:
            frappe.log_error(f"Reminder failed for {inv['name']}: {e}",
                "Payment Reminder Error")


def _send_payment_reminder(inv):
    customer = frappe.db.get_value("Customer", inv["customer"],
        ["customer_name", "email_id"], as_dict=True)
    if not customer or not customer.get("email_id"):
        frappe.log_error(
            f"No email for {inv['customer']} — reminder skipped.",
            "Reminder: Missing Email")
        return
    frappe.sendmail(
        recipients=[customer["email_id"]],
        subject=f"Payment reminder — Invoice {inv['name']}",
        message=(f"Hi {customer['customer_name']},<br><br>"
            f"Invoice <strong>{inv['name']}</strong> for "
            f"<strong>KES {float(inv['outstanding_amount']):,.0f}</strong> is overdue.<br>"
            f"Due date: {inv['due_date']}<br><br>"
            f"Please pay via your parent portal.<br><br>"
            f"— Rhema Daycare team"))


def calculate_late_pickup_fees():
    settings = _settings()
    cutoff = get_time(settings.get("pickup_cutoff_time") or "17:30:00")
    if get_time(now_datetime()) <= cutoff:
        return

    late_fee_item = settings.get("late_fee_item_code")
    if not late_fee_item:
        frappe.log_error("Late fee item not in Daycare Settings.", "Late Fee Config")
        return

    company = frappe.db.get_single_value("Global Defaults", "default_company")

    open_logs = frappe.get_all("Child Attendance Log",
        filters={
            "check_in": [">=", today()],
            "check_out": ["is", "not set"],
            "late_fee_charged": 0
        },
        fields=["name", "child", "check_in"])

    for log in open_logs:
        try:
            _apply_late_fee(log, cutoff, settings, late_fee_item, company)
        except Exception as e:
            frappe.log_error(f"Late fee failed for {log['name']}: {e}", "Late Fee Error")


def _apply_late_fee(log, cutoff, settings, late_fee_item, company):
    from frappe.utils import time_diff_in_hours, get_datetime
    now = now_datetime()
    cutoff_dt = get_datetime(str(today()) + " " + str(cutoff))
    hours_late = time_diff_in_hours(now, cutoff_dt)
    fee = _calculate_fee(hours_late, settings)
    if fee <= 0:
        return

    child = frappe.db.get_value("Child Profile", log["child"],
        ["name", "full_name", "guardian"], as_dict=True)
    if not child or not child.get("guardian"):
        return

    invoice = frappe.new_doc("Sales Invoice")
    invoice.customer = child["guardian"]
    invoice.posting_date = today()
    invoice.due_date = today()
    invoice.rhema_child = child["name"]
    invoice.company = company
    invoice.append("items", {
        "item_code": late_fee_item,
        "qty": 1,
        "rate": fee,
        "description": f"Late pickup fee — {child['full_name']} — {hours_late:.1f} hrs past cutoff"
    })
    invoice.insert()
    invoice.submit()
    frappe.db.set_value("Child Attendance Log", log["name"], "late_fee_charged", 1)
    _notify_late_pickup(child, hours_late, fee)


def _calculate_fee(hours_late, settings):
    grace = float(settings.get("late_pickup_grace_minutes") or 0) / 60
    rate = float(settings.get("late_pickup_fee_per_hour") or 200)
    minimum = float(settings.get("late_pickup_minimum_fee") or 0)
    maximum = float(settings.get("late_pickup_maximum_fee") or 9999)
    billable = max(0.0, hours_late - grace)
    if billable <= 0:
        return 0.0
    return max(minimum, min(round(billable * rate, 2), maximum))


def _notify_late_pickup(child, hours_late, fee):
    try:
        email = frappe.db.get_value("Customer", child["guardian"], "email_id")
        if not email:
            return
        frappe.sendmail(recipients=[email],
            subject=f"Late pickup alert — {child['full_name']}",
            message=(f"<strong>{child['full_name']}</strong> is still at Rhema Daycare — "
                f"{hours_late * 60:.0f} mins past cutoff.<br>"
                f"Late fee: <strong>KES {fee:,.0f}</strong>.<br><br>"
                f"— Rhema Daycare team"),
            now=True)
    except Exception as e:
        frappe.log_error(str(e), "Late Pickup Notification Error")


def check_missing_children():
    settings = _settings()
    alert_time = get_time(settings.get("absence_alert_time") or "09:30:00")
    if get_time(now_datetime()) < alert_time:
        return

    active = frappe.get_all("Child Profile",
        filters={"status": "Active"},
        fields=["name", "full_name", "guardian"])

    checked_in = {
        r["child"]
        for r in frappe.get_all("Child Attendance Log",
            filters={"check_in": [">=", today()]},
            fields=["child"])
    }

    for child in active:
        if child["name"] not in checked_in:
            try:
                _notify_absence(child)
            except Exception as e:
                frappe.log_error(
                    f"Absence alert failed for {child['name']}: {e}",
                    "Absence Alert Error")


def _notify_absence(child):
    if not child.get("guardian"):
        return
    email = frappe.db.get_value("Customer", child["guardian"], "email_id")
    if not email:
        return
    frappe.sendmail(recipients=[email],
        subject=f"Absence alert — {child['full_name']} has not checked in",
        message=(f"<strong>{child['full_name']}</strong> has not checked in "
            f"at Rhema Daycare by the expected time.<br><br>"
            f"If planned absence, no action needed. Otherwise please contact us.<br><br>"
            f"— Rhema Daycare team"))


def on_invoice_submit(doc, method):
    pass

