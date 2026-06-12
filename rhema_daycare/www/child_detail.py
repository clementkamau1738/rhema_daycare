import frappe
from frappe import _
from rhema_daycare.portal.permissions import has_website_permission


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)

    child_name = frappe.form_dict.get("child_name")
    if not child_name:
        frappe.throw(_("Child not specified"), frappe.DoesNotExistError)

    # Ownership check
    child_doc = frappe.get_doc("Child Profile", child_name)
    if not has_website_permission(child_doc, "read", frappe.session.user):
        frappe.throw(_("Access denied"), frappe.PermissionError)

    # Safe fields only — medical data excluded
    context.child = frappe.db.get_value(
        "Child Profile", child_name,
        ["name", "full_name", "date_of_birth", "gender",
         "assigned_classroom", "enrollment_date", "status"],
        as_dict=True
    )

    # Today's attendance
    from frappe.utils import today
    context.attendance_today = frappe.db.get_value(
        "Child Attendance Log",
        {"child": child_name, "check_in": [">=", today()]},
        ["check_in", "check_out", "status"],
        as_dict=True
    )

    # Outstanding invoices
    context.invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "rhema_child": child_name,
            "docstatus": 1,
            "outstanding_amount": [">", 0]
        },
        fields=["name", "posting_date", "due_date", "outstanding_amount"],
        order_by="due_date asc"
    )
