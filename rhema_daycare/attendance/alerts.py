import frappe
from frappe.utils import now_datetime, today, get_time, time_diff_in_hours, get_datetime


def evaluate_late_pickup(doc, method):
    if doc.check_out:
        return

    settings = frappe.get_cached_doc("Daycare Settings")
    cutoff = get_time(settings.get("pickup_cutoff_time") or "17:30:00")

    if get_time(now_datetime()) <= cutoff:
        return

    if frappe.db.get_value("Child Attendance Log", doc.name, "late_alert_sent"):
        return

    child = frappe.db.get_value(
        "Child Profile", doc.child,
        ["name", "full_name", "guardian", "assigned_classroom"],
        as_dict=True
    )
    if not child:
        return

    cutoff_dt = get_datetime(str(today()) + " " + str(cutoff))
    minutes_late = time_diff_in_hours(now_datetime(), cutoff_dt) * 60

    try:
        from rhema_daycare.notifications.hub import send_late_pickup_alert
        send_late_pickup_alert(child, minutes_late)
        frappe.db.set_value("Child Attendance Log", doc.name, "late_alert_sent", 1)
    except Exception as e:
        frappe.log_error(str(e), "Late Pickup Alert Error")


def check_active_late_pickups():
    settings = frappe.get_cached_doc("Daycare Settings")
    cutoff = get_time(settings.get("pickup_cutoff_time") or "17:30:00")

    if get_time(now_datetime()) <= cutoff:
        return

    open_logs = frappe.get_all(
        "Child Attendance Log",
        filters={
            "check_in": [">=", today()],
            "check_out": ["is", "not set"],
            "late_alert_sent": 0
        },
        fields=["name", "child"]
    )

    cutoff_dt = get_datetime(str(today()) + " " + str(cutoff))

    for log in open_logs:
        try:
            child = frappe.db.get_value(
                "Child Profile", log["child"],
                ["name", "full_name", "guardian", "assigned_classroom"],
                as_dict=True
            )
            if not child:
                continue

            minutes_late = time_diff_in_hours(now_datetime(), cutoff_dt) * 60

            from rhema_daycare.notifications.hub import send_late_pickup_alert
            send_late_pickup_alert(child, minutes_late)
            frappe.db.set_value("Child Attendance Log", log["name"], "late_alert_sent", 1)

        except Exception as e:
            frappe.log_error(
                "Late pickup alert failed for log " + str(log["name"]) + ": " + str(e),
                "Late Pickup Alert Error"
            )
            