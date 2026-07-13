import frappe
from frappe import _


def _is_guardian_of(child_name, guardian_name):
    """True if guardian_name is either the primary guardian or listed in the
    child's Additional Guardians table (secondary, portal-read-only access)."""
    if frappe.db.exists("Child Profile", {
        "name": child_name, "guardian": guardian_name, "status": "Active"
    }):
        return True
    return bool(frappe.db.exists("Additional Guardian", {
        "parent": child_name, "parenttype": "Child Profile", "guardian": guardian_name
    })) and frappe.db.get_value("Child Profile", child_name, "status") == "Active"


def _children_for_guardian(guardian_name):
    primary = frappe.get_all(
        "Child Profile",
        filters={"guardian": guardian_name, "status": "Active"},
        pluck="name"
    )
    secondary = frappe.get_all(
        "Additional Guardian",
        filters={"guardian": guardian_name, "parenttype": "Child Profile"},
        pluck="parent"
    )
    names = set(primary)
    for name in secondary:
        if frappe.db.get_value("Child Profile", name, "status") == "Active":
            names.add(name)
    return list(names)


def has_website_permission(doc, ptype, user, verbose=False):
    if user == "Guest":
        return False
    if ptype != "read":
        return False
    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": user}, "name"
    )
    if not guardian_name:
        return False
    return _is_guardian_of(doc.name, guardian_name)


def get_portal_children(user):
    if user == "Guest":
        return []
    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": user}, "name"
    )
    if not guardian_name:
        return []
    names = _children_for_guardian(guardian_name)
    if not names:
        return []
    return frappe.get_all(
        "Child Profile",
        filters={"name": ["in", names]},
        fields=[
            "name", "full_name", "date_of_birth",
            "gender", "assigned_classroom",
            "creation", "status"
        ]
    )


def get_portal_child_detail(child_name, user):
    if user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)
    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": user}, "name"
    )
    if not guardian_name:
        frappe.throw(
            _("Your account is not linked to a guardian record."),
            frappe.PermissionError
        )
    if not _is_guardian_of(child_name, guardian_name):
        frappe.throw(_("Access denied."), frappe.PermissionError)
    child = frappe.db.get_value(
        "Child Profile",
        child_name,
        [
            "name", "full_name", "date_of_birth", "gender",
            "assigned_classroom", "creation", "status"
        ],
        as_dict=True
    )
    from frappe.utils import today
    child["attendance_today"] = frappe.db.get_value(
        "Child Attendance Log",
        {"child": child_name, "check_in": [">=", today()]},
        ["check_in", "check_out", "status"],
        as_dict=True
    )
    child["meals_today"] = frappe.get_all(
        "Meal Record",
        filters={"child": child_name, "meal_date": today()},
        fields=["meal_type", "food_items", "amount_eaten", "notes"],
        order_by="creation asc"
    )
    child["naps_today"] = frappe.get_all(
        "Nap Record",
        filters={"child": child_name, "nap_date": today()},
        fields=["nap_start", "nap_end", "notes"],
        order_by="creation asc"
    )
    child["teacher_notes_today"] = frappe.get_all(
        "Teacher Note",
        filters={"child": child_name, "note_date": today()},
        fields=["note"],
        order_by="creation asc"
    )
    child["outstanding_invoices"] = frappe.get_all(
        "Sales Invoice",
        filters={
            "rhema_child":        child_name,
            "docstatus":          1,
            "outstanding_amount": [">", 0]
        },
        fields=["name", "posting_date", "due_date", "outstanding_amount"],
        order_by="due_date asc"
    )
    return child
