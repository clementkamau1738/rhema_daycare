import frappe
from frappe.utils import today
from rhema_daycare.portal.permissions import get_portal_children


def get_context(context):
    """
    Provides context data for the parent portal page.
    Shows children linked to the logged-in guardian (primary or additional).
    """

    # Redirect guests to login
    if frappe.session.user == "Guest":
        frappe.throw(
            "Please login to access the Parent Portal.",
            frappe.PermissionError
        )

    # Find guardian linked to logged-in user
    guardian = frappe.db.get_value(
        "Customer",
        {"email_id": frappe.session.user},
        "name"
    )

    if not guardian:
        context.children = []
        context.guardian_name = "Parent"
        context.error = "No guardian account linked to this email."
        return

    # Get guardian's display name
    context.guardian_name = frappe.db.get_value(
        "Customer", guardian, "customer_name"
    )

    # Get all active children this guardian can see (primary or additional)
    context.children = get_portal_children(frappe.session.user)

    # Get today's attendance for each child
    for child in context.children:
        attendance = frappe.db.get_value(
            "Child Attendance Log",
            {
                "child": child.name,
                "check_in": [">=", today()]
            },
            ["check_in", "check_out", "status"],
            as_dict=True
        )
        child.today_attendance = attendance or {}

    context.no_cache = 1
