import frappe
from rhema_daycare.portal.permissions import get_portal_child_detail

def get_context(context):
    if frappe.session.user == "Guest":
        frappe.throw("Please login.", frappe.PermissionError)

    # Get child name from URL
    child_name = frappe.form_dict.get("name") or context.get("name")

    if not child_name:
        frappe.throw("Child not found.", frappe.DoesNotExistError)

    # Delegate entirely to the same guardian check used by /child/<name> and
    # the has_website_permission hook: primary guardian OR Additional
    # Guardian, and only while the child is Active. The field subset it
    # returns intentionally excludes medical_conditions/allergies/
    # immunization_records — sensitive health data is staff-only under
    # Kenya's Data Protection Act 2019 (manual, Module 7 Security) — this
    # page used to fetch the raw doc and leaked those fields directly.
    child = get_portal_child_detail(child_name, frappe.session.user)

    context.child = child
    context.attendance_logs = frappe.get_all("Child Attendance Log",
        filters={"child": child_name},
        fields=["check_in", "check_out", "status"],
        order_by="check_in desc",
        limit=10
    )

    context.no_cache = 1
