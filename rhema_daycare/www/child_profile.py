import frappe

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please login.", frappe.PermissionError)

    # Get child name from URL
    child_name = frappe.form_dict.get("name") or context.get("name")

    if not child_name:
        frappe.throw("Child not found.", frappe.DoesNotExistError)

    # Get child record
    child = frappe.get_doc("Child Profile", child_name)

    # Check permission - only guardian can view
    guardian = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if child.guardian != guardian:
        frappe.throw("You do not have permission to view this profile.", frappe.PermissionError)

    context.child = child

    # Get attendance logs
    context.attendance_logs = frappe.get_all("Child Attendance Log",
        filters={"child": child_name},
        fields=["check_in", "check_out", "status"],
        order_by="check_in desc",
        limit=10
    )

    context.no_cache = 1
