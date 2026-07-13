import frappe

def execute(filters=None):
    if not filters:
        filters = {}
    if not filters.get("from_date"):
        filters["from_date"] = frappe.utils.add_months(frappe.utils.today(), -12)
    if not filters.get("to_date"):
        filters["to_date"] = frappe.utils.today()
    columns = [
        {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 120},
        {"label": "New Enrollments", "fieldname": "new", "fieldtype": "Int", "width": 140},
        {"label": "Active Children", "fieldname": "active", "fieldtype": "Int", "width": 140},
        {"label": "Inactive", "fieldname": "inactive", "fieldtype": "Int", "width": 120},
        {"label": "Graduated", "fieldname": "graduated", "fieldtype": "Int", "width": 120}
    ]
    data = frappe.db.sql("""
        SELECT
            DATE_FORMAT(creation, %(fmt)s) as month,
            COUNT(*) as new,
            SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'Inactive' THEN 1 ELSE 0 END) as inactive,
            SUM(CASE WHEN status = 'Graduated' THEN 1 ELSE 0 END) as graduated
        FROM `tabChild Profile`
        WHERE creation BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY month
        ORDER BY month DESC
    """, {**filters, "fmt": "%Y-%m"}, as_dict=True)
    return columns, data
