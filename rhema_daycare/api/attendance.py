import frappe
from frappe.utils import now_datetime, today


def _get_setting(fieldname, default=None):
    try:
        return frappe.db.get_single_value("Rhema Daycare Settings", fieldname) or default
    except Exception:
        return default


def _check_rate_limit(child_id):
    cache_key = f"checkin_rate_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw("Too many requests. Please wait 30 seconds.")
    frappe.cache().set(cache_key, True, expires_in_sec=30)


@frappe.whitelist()
def checkin_child(child_id):
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required.", frappe.AuthenticationError)
    allowed_roles = ["Teacher", "Daycare Manager", "System Manager"]
    if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
        frappe.throw("Insufficient permissions.", frappe.PermissionError)
    if not child_id or len(str(child_id)) > 50:
        frappe.throw("Invalid child ID.")
    _check_rate_limit(child_id)
    if not frappe.db.exists("Child Profile", child_id):
        frappe.throw("Child not found.", frappe.DoesNotExistError)
    child = frappe.get_doc("Child Profile", child_id)
    if child.status != "Active":
        frappe.throw(f"{child.full_name} is not Active.")
    today_log = frappe.db.get_value("Child Attendance Log", {
        "child": child_id,
        "check_in": [">=", today() + " 00:00:00"],
        "check_out": ["is", "not set"]
    }, "name")
    if today_log:
        frappe.throw(f"{child.full_name} is already checked in today.")
    try:
        frappe.db.begin()
        log = frappe.new_doc("Child Attendance Log")
        log.child = child.name
        log.check_in = now_datetime()
        log.status = "Present"
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(str(e), "Check-in Error")
        frappe.throw("Check-in failed. Please try again.")
    try:
        notify_parent_checkin(child)
    except Exception as e:
        frappe.log_error(str(e), "Notification Error")
    return {
        "status": "success",
        "child": child.full_name,
        "check_in": str(log.check_in),
        "log_id": log.name
    }


@frappe.whitelist()
def checkout_child(child_id):
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required.", frappe.AuthenticationError)
    if not child_id or not frappe.db.exists("Child Profile", child_id):
        frappe.throw("Child not found.", frappe.DoesNotExistError)
    child = frappe.get_doc("Child Profile", child_id)
    log_name = frappe.db.get_value("Child Attendance Log", {
        "child": child_id,
        "check_in": [">=", today() + " 00:00:00"],
        "check_out": ["is", "not set"]
    }, "name")
    if not log_name:
        frappe.throw(f"No open check-in for {child.full_name} today.")
    try:
        frappe.db.begin()
        log = frappe.get_doc("Child Attendance Log", log_name)
        log.check_out = now_datetime()
        log.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(str(e), "Check-out Error")
        frappe.throw("Check-out failed.")
    return {"status": "success", "child": child.full_name, "check_out": str(log.check_out)}


def notify_parent_checkin(child):
    if not child.guardian:
        return
    guardian = frappe.get_doc("Customer", child.guardian)
    if not guardian.email_id:
        frappe.log_error(f"No email for {guardian.customer_name}", "Notification Skip")
        return
    try:
        frappe.sendmail(
            recipients=[guardian.email_id],
            subject=f"{child.full_name} has arrived at Rhema Daycare",
            message=f"<p>Dear {guardian.customer_name},</p><p>{child.full_name} checked in at {now_datetime()}.</p>"
        )
    except Exception as e:
        frappe.log_error(str(e), "Email Error")
