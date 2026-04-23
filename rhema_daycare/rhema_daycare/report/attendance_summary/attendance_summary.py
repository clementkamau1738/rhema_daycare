import frappe

def execute(filters=None):
    if not filters:
        filters = {}
    if not filters.get("from_date"):
        filters["from_date"] = frappe.utils.today()
    if not filters.get("to_date"):
        filters["to_date"] = frappe.utils.today()
    columns = [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 120},
        {"label": "Child Name", "fieldname": "child_name", "fieldtype": "Data", "width": 160},
        {"label": "Classroom", "fieldname": "classroom", "fieldtype": "Data", "width": 140},
        {"label": "Check In", "fieldname": "check_in", "fieldtype": "Datetime", "width": 160},
        {"label": "Check Out", "fieldname": "check_out", "fieldtype": "Datetime", "width": 160},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 100},
        {"label": "Hours", "fieldname": "hours", "fieldtype": "Float", "width": 80}
    ]
    data = frappe.db.sql("""
        SELECT
            DATE(cal.check_in) as date,
            cp.full_name as child_name,
            cp.assigned_classroom as classroom,
            cal.check_in, cal.check_out, cal.status,
            ROUND(TIMESTAMPDIFF(MINUTE, cal.check_in, cal.check_out) / 60, 2) as hours
        FROM `tabChild Attendance Log` cal
        LEFT JOIN `tabChild Profile` cp ON cal.child = cp.name
        WHERE DATE(cal.check_in) BETWEEN %(from_date)s AND %(to_date)s
        ORDER BY cal.check_in DESC
    """, filters, as_dict=True)
    return columns, data
