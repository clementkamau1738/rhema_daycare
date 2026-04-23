import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please login.", frappe.PermissionError)

    guardian = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")

    if not guardian:
        context.children = []
        context.guardian_name = "Parent"
        context.error = "No guardian account linked to this email."
        return

    context.guardian_name = frappe.db.get_value("Customer", guardian, "customer_name")

    context.children = frappe.get_all("Child Profile",
        filters={"guardian": guardian, "status": "Active"},
        fields=["name", "full_name", "status", "assigned_classroom"]
    )

    for child in context.children:
        attendance = frappe.db.get_value("Child Attendance Log",
            {"child": child.name, "status": "Present"},
            ["check_in", "check_out", "status"], as_dict=True
        )
        child.today_attendance = attendance or {}

    context.no_cache = 1
