import frappe
from frappe.utils import today, get_time, now_datetime


def execute(filters=None):
    columns = [
        {"label": "Child", "fieldname": "child_name", "fieldtype": "Data", "width": 180},
        {"label": "Classroom", "fieldname": "classroom", "fieldtype": "Link",
         "options": "Classroom", "width": 150},
        {"label": "Check In", "fieldname": "check_in", "fieldtype": "Datetime", "width": 160},
        {"label": "Check Out", "fieldname": "check_out", "fieldtype": "Datetime", "width": 160},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 140},
    ]

    active_children = frappe.get_all(
        "Child Profile",
        filters={"status": "Active"},
        fields=["name", "full_name", "assigned_classroom"],
    )

    logs_today = frappe.get_all(
        "Child Attendance Log",
        filters={"check_in": [">=", today()]},
        fields=["child", "check_in", "check_out", "status"],
        order_by="check_in desc",
    )
    log_by_child = {}
    for log in logs_today:
        log_by_child.setdefault(log.child, log)

    absence_alert_time = get_time(
        frappe.db.get_single_value("Daycare Settings", "absence_alert_time") or "09:30:00")
    past_alert_time = get_time(now_datetime()) >= absence_alert_time

    data = []
    for child in active_children:
        log = log_by_child.get(child.name)

        if log and log.status == "Absent":
            status = "<span style='color:#8d99a6'>&#9679; Absent (marked)</span>"
        elif log and log.check_out:
            status = "<span style='color:#2490ef'>&#9679; Checked Out</span>"
        elif log and log.check_in:
            status = "<span style='color:#28a745'>&#9679; Present</span>"
        elif past_alert_time:
            status = "<span style='color:#d1495b'>&#9679; No Check-in</span>"
        else:
            status = "<span style='color:#8d99a6'>&#9679; Not Yet Arrived</span>"

        data.append({
            "child_name": child.full_name,
            "classroom": child.assigned_classroom,
            "check_in": log.check_in if log else None,
            "check_out": log.check_out if log else None,
            "status": status,
        })

    return columns, data
