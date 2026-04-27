import frappe
from frappe.utils import get_time, now_datetime, nowtime


def _get_setting(fieldname, default=None):
    try:
        return frappe.db.get_single_value("Rhema Daycare Settings", fieldname) or default
    except Exception:
        return default


def check_late_pickup(doc, method):
    if doc.check_out or doc.status != "Present":
        return
    cutoff_str = str(_get_setting("cutoff_time", "17:30:00"))
    if get_time(nowtime()) <= get_time(cutoff_str):
        return
    alert_key = f"late_pickup_{doc.name}_{now_datetime().strftime('%Y-%m-%d')}"
    if frappe.cache().get(alert_key):
        return
    try:
        child = frappe.get_doc("Child Profile", doc.child)
        if not child.guardian:
            return
        guardian = frappe.get_doc("Customer", child.guardian)
        if not guardian.email_id:
            return
        late_fee_per_hour = float(_get_setting("late_fee_per_hour", 200))
        cutoff_hour = int(cutoff_str.split(":")[0])
        hours_late = max(1, now_datetime().hour - cutoff_hour)
        estimated_fee = hours_late * late_fee_per_hour
        frappe.sendmail(
            recipients=[guardian.email_id],
            subject=f"Late Pickup Alert — {child.full_name} | Rhema Daycare",
            message=f"<p>Dear {guardian.customer_name},</p><p>{child.full_name} is still at Rhema Daycare. Estimated late fee: KES {estimated_fee:.0f}</p>"
        )
        frappe.cache().set(alert_key, True, expires_in_sec=3600)
    except Exception as e:
        frappe.log_error(str(e), "Late Pickup Error")
