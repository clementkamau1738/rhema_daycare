import frappe
from frappe import _


def has_website_permission(doc, ptype, user, verbose=False):
    """
    Called by Frappe before rendering any Child Profile portal page.
    Returns True only if the logged-in user is the guardian of this child.
    """
    # Block guests entirely
    if user == "Guest":
        return False

    # Portal users can only read — never write via web routes
    if ptype != "read":
        return False

    # Resolve the logged-in user's email to a Customer (guardian) record
    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": user}, "name"
    )
    if not guardian_name:
        return False

    # Ownership check — doc.name must belong to this guardian
    return bool(frappe.db.exists("Child Profile", {
        "name": doc.name,
        "guardian": guardian_name,
        "status": "Active"
    }))


def get_portal_children(user):
    """Return safe child records for the portal home page.
    Medical fields deliberately excluded."""
    if user == "Guest":
        return []

    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": user}, "name"
    )
    if not guardian_name:
        return []

    return frappe.get_all(
        "Child Profile",
        filters={"guardian": guardian_name, "status": "Active"},
        fields=[
            "name", "full_name", "date_of_birth",
            "gender", "assigned_classroom",
            "enrollment_date", "status"
            # medical_conditions, allergies, immunization_records
            # deliberately excluded from portal
        ]
    )


def get_portal_child_detail(child_name, user):
    """Get child detail for portal — excludes sensitive medical fields"""

    if not user or user == "Guest":
        frappe.throw("Authentication required.", frappe.AuthenticationError)

    guardian = frappe.db.get_value(
        "Customer",
        {"email_id": user},
        "name"
    )

    if not guardian:
        frappe.throw("No guardian account linked.", frappe.PermissionError)

    # Verify ownership and active status
    child = frappe.db.get_value(
        "Child Profile",
        {
            "name": child_name,
            "guardian": guardian,
            "status": "Active"
        },
        [
            "name",
            "full_name",
            "status",
            "assigned_classroom",
            "gender",
            "date_of_birth",
            "guardian",
            "workflow_state"
        ],
        as_dict=True
    )

    if not child:
        frappe.throw(
            "Child not found or access denied.",
            frappe.DoesNotExistError
        )

    # Get today's attendance
    from frappe.utils import today
    attendance = frappe.db.get_value(
        "Child Attendance Log",
        {
            "child": child_name,
            "check_in": [">=", today() + " 00:00:00"]
        },
        ["check_in", "check_out", "status"],
        as_dict=True
    )
    child.today_attendance = attendance or {}

    # Get recent invoices
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": guardian,
            "docstatus": 1
        },
        fields=["name", "posting_date", "grand_total", "outstanding_amount", "status"],
        limit=5,
        order_by="posting_date desc"
    )
    child.recent_invoices = invoices

    return child
