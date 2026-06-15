import re
import frappe
from frappe import _
from frappe.utils import now_datetime, today


@frappe.whitelist()
def checkin_child(child_id: str):
    # 1. Authentication
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    # 2. Permission
    if not frappe.has_permission("Child Attendance Log", "create"):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    # 3. Input validation
    if not child_id or not isinstance(child_id, str):
        frappe.throw(_("child_id must be a non-empty string."))
    if not re.match(r'^[\w\-]+$', child_id.strip()):
        frappe.throw(_("Invalid child_id format."))
    if len(child_id) > 140:
        frappe.throw(_("child_id too long."))

    # 4. Rate limit
    cache_key = f"rhema_checkin_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw(_("Rate limit: please wait before retrying."))
    frappe.cache().set(cache_key, 1, ex=300)

    # 5. Child must exist and be Active
    child = frappe.db.get_value(
        "Child Profile",
        {"name": child_id.strip(), "status": "Active"},
        ["name", "full_name", "guardian", "assigned_classroom"],
        as_dict=True
    )
    if not child:
        frappe.throw(
            _("Active child not found: '{0}'.").format(child_id),
            frappe.DoesNotExistError
        )

    # 6. Duplicate check-in guard
    open_log = frappe.db.exists("Child Attendance Log", {
        "child":     child_id,
        "check_in":  [">=", today()],
        "check_out": ["is", "not set"]
    })
    if open_log:
        frappe.throw(
            _("'{0}' is already checked in. Check them out first.").format(
                child.full_name
            )
        )

    # 7. Create log
    log = frappe.new_doc("Child Attendance Log")
    log.child         = child.name
    log.check_in      = now_datetime()
    log.status        = "Present"
    log.checked_in_by = frappe.session.user
    log.insert()
    frappe.db.commit()

    # 8. Notify guardian — never crashes check-in
    _notify_guardian(child, "checkin", log.check_in)

    return {
        "status": "success",
        "child":  child.full_name,
        "log":    log.name,
        "time":   str(log.check_in)
    }


@frappe.whitelist()
def checkout_child(child_id: str):
    # 1. Authentication
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    # 2. Permission
    if not frappe.has_permission("Child Attendance Log", "write"):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    # 3. Input validation
    if not child_id or not isinstance(child_id, str):
        frappe.throw(_("child_id must be a non-empty string."))
    if not re.match(r'^[\w\-]+$', child_id.strip()):
        frappe.throw(_("Invalid child_id format."))
    if len(child_id) > 140:
        frappe.throw(_("child_id too long."))

    # 4. Rate limit
    cache_key = f"rhema_checkout_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw(_("Rate limit: please wait before retrying."))
    frappe.cache().set(cache_key, 1, ex=300)

    # 5. Child must exist and be Active
    child = frappe.db.get_value(
        "Child Profile",
        {"name": child_id.strip(), "status": "Active"},
        ["name", "full_name", "guardian", "assigned_classroom"],
        as_dict=True
    )
    if not child:
        frappe.throw(
            _("Active child not found: '{0}'.").format(child_id),
            frappe.DoesNotExistError
        )

    # 6. Find open log for today
    open_log_name = frappe.db.get_value("Child Attendance Log", {
        "child":     child_id,
        "check_in":  [">=", today()],
        "check_out": ["is", "not set"]
    }, "name")

    if not open_log_name:
        frappe.throw(
            _("No open check-in found for '{0}' today.").format(
                child.full_name
            ),
            frappe.DoesNotExistError
        )

    # 7. Record checkout
    now = now_datetime()
    frappe.db.set_value("Child Attendance Log", open_log_name, {
        "check_out":      now,
        "checked_out_by": frappe.session.user,
        "status":         "Present"
    })
    frappe.db.commit()

    _notify_guardian(child, "checkout", now)

    return {
        "status":  "success",
        "child":   child.full_name,
        "log":     open_log_name,
        "time":    str(now)
    }


def _notify_guardian(child, event, timestamp):
    """Send email to guardian. Isolated — never crashes the check-in flow."""
    try:
        if not child.get("guardian"):
            return
        email = frappe.db.get_value("Customer", child["guardian"], "email_id")
        if not email:
            frappe.log_error(
                f"No email for guardian of {child['name']}. Notification skipped.",
                "Notification: Missing Email"
            )
            return
        if event == "checkin":
            subject = _("{0} has arrived at Rhema Daycare").format(child["full_name"])
            message = _("Check-in recorded at {0}.").format(
                frappe.utils.format_datetime(timestamp)
            )
        else:
            subject = _("{0} has been picked up").format(child["full_name"])
            message = _("Check-out recorded at {0}.").format(
                frappe.utils.format_datetime(timestamp)
            )
        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            now=False
        )
    except Exception as e:
        frappe.log_error(str(e), "Attendance notification error")

