import frappe
from frappe.utils import get_first_day, today


def execute(filters=None):
    filters = filters or {}
    from_date = filters.get("from_date") or get_first_day(today())
    to_date = filters.get("to_date") or today()

    columns = [
        {"label": "Child", "fieldname": "child_name", "fieldtype": "Data", "width": 180},
        {"label": "Classroom", "fieldname": "classroom", "fieldtype": "Link",
         "options": "Classroom", "width": 150},
        {"label": "Days Present", "fieldname": "days_present", "fieldtype": "Int", "width": 110},
        {"label": "Days Operated", "fieldname": "days_operated", "fieldtype": "Int", "width": 120},
        {"label": "Attendance %", "fieldname": "attendance_pct", "fieldtype": "Percent", "width": 120},
    ]

    child_filters = {"status": "Active"}
    if filters.get("classroom"):
        child_filters["assigned_classroom"] = filters["classroom"]

    children = frappe.get_all("Child Profile", filters=child_filters,
        fields=["name", "full_name", "assigned_classroom"])
    if not children:
        return columns, []

    # "Days operated" is derived from actual attendance activity in the
    # period (distinct calendar dates on which *any* child checked in),
    # rather than a fixed 5-day-week assumption — this system has no
    # holiday-calendar concept of its own for the daycare (Employee Holiday
    # Lists are HR-side, not tied to Child Attendance), so real operating
    # days is the only accurate denominator available.
    days_operated = frappe.db.sql("""
        SELECT COUNT(DISTINCT DATE(check_in))
        FROM `tabChild Attendance Log`
        WHERE DATE(check_in) BETWEEN %(from_date)s AND %(to_date)s
    """, {"from_date": from_date, "to_date": to_date})[0][0] or 0

    present_counts = dict(frappe.db.sql("""
        SELECT child, COUNT(DISTINCT DATE(check_in))
        FROM `tabChild Attendance Log`
        WHERE DATE(check_in) BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY child
    """, {"from_date": from_date, "to_date": to_date}))

    data = []
    for child in children:
        days_present = present_counts.get(child.name, 0)
        attendance_pct = round((days_present / days_operated) * 100, 1) if days_operated else 0
        data.append({
            "child_name": child.full_name,
            "classroom": child.assigned_classroom,
            "days_present": days_present,
            "days_operated": days_operated,
            "attendance_pct": attendance_pct,
        })

    data.sort(key=lambda r: r["attendance_pct"])
    return columns, data
