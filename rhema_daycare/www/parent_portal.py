import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect
    guardian = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if not guardian:
        context.children = []
        context.guardian_name = frappe.session.user
        context.error = "No guardian account linked to your email. Please contact the administrator."
        return
    context.guardian_name = frappe.db.get_value("Customer", guardian, "customer_name") or frappe.session.user
    context.children = frappe.get_all("Child Profile",
        filters={"guardian": guardian, "status": "Active"},
        fields=["name", "full_name", "status", "assigned_classroom", "gender"],
        limit=20, order_by="full_name asc")
    for child in context.children:
        try:
            attendance = frappe.db.get_value("Child Attendance Log",
                {"child": child.name, "check_in": [">=", frappe.utils.today() + " 00:00:00"], "status": "Present"},
                ["check_in", "check_out", "status"], as_dict=True)
            child.today_attendance = attendance or {}
        except Exception:
            child.today_attendance = {}
    context.no_cache = 1
