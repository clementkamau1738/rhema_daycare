import frappe
from frappe import _
from rhema_daycare.portal.permissions import get_portal_child_detail


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    child_name = frappe.form_dict.get("child_name")
    if not child_name:
        frappe.throw(_("Child not specified"), frappe.DoesNotExistError)

    # get_portal_child_detail already performs the ownership check (guardian
    # or additional-guardian match) and returns safe fields only — medical
    # data is intentionally excluded.
    child = get_portal_child_detail(child_name, frappe.session.user)

    context.child = child
    context.attendance_today = child.get("attendance_today")
    context.meals_today = child.get("meals_today")
    context.naps_today = child.get("naps_today")
    context.teacher_notes_today = child.get("teacher_notes_today")
    context.invoices = child.get("outstanding_invoices")
