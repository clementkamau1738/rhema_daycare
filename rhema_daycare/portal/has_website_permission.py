import frappe

def has_website_permission(doc, ptype, user, verbose=False):
    guardian = frappe.db.get_value("Customer",
        {"email_id": user}, "name")
    if not guardian:
        return False
    return doc.guardian == guardian
