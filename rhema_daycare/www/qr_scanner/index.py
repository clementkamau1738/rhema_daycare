import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    allowed_roles = ["Teacher", "Daycare Manager", "System Manager"]
    if not any(r in frappe.get_roles(frappe.session.user) for r in allowed_roles):
        frappe.throw("Access denied.", frappe.PermissionError)

    context.user = frappe.session.user
    context.no_cache = 1
