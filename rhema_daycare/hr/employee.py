import frappe
from frappe import _
from frappe.utils import getdate, nowdate


def validate_background_check(doc, method):
    """Doc event: block saving if a Failed background check is paired with a
    classroom assignment — a stated child-safety control."""
    if doc.get("background_check_status") == "Failed" and doc.get("assigned_classroom"):
        frappe.throw(
            _("{0} has a Failed background check and cannot be assigned to a "
              "classroom. Clear the classroom assignment first.").format(
                doc.employee_name or doc.name),
            frappe.ValidationError
        )


def validate_cpr_certification(doc, method):
    """Doc event: when Daycare Settings > Require CPR Certification for Teachers
    is enabled, block assigning a classroom to an employee who is not CPR
    certified or whose certification has expired. Manual (Module 5) treats a
    lapsed CPR certification as a compliance risk during ECDE inspection; this
    enforces the setting the field itself promises rather than leaving it
    informational-only."""
    if not doc.get("assigned_classroom"):
        return

    require_cpr = frappe.db.get_single_value(
        "Daycare Settings", "require_cpr_for_teachers")
    if not require_cpr:
        return

    if not doc.get("cpr_certified"):
        frappe.throw(
            _("{0} is not CPR certified and cannot be assigned to a classroom. "
              "Daycare Settings requires CPR certification for teachers.").format(
                doc.employee_name or doc.name),
            frappe.ValidationError
        )

    expiry = doc.get("cpr_expiry_date")
    if expiry and getdate(expiry) < getdate(nowdate()):
        frappe.throw(
            _("{0}'s CPR certification expired on {1} and cannot be assigned "
              "to a classroom until it is renewed.").format(
                doc.employee_name or doc.name, expiry),
            frappe.ValidationError
        )
