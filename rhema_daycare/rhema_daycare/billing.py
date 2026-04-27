import frappe
from frappe.utils import (
    today, add_months, getdate, nowdate,
    get_first_day, get_last_day, now_datetime,
    time_diff_in_hours, get_time
)


def _get_setting(fieldname, default=None):
    try:
        return frappe.db.get_single_value("Rhema Daycare Settings", fieldname) or default
    except Exception:
        return default


def _is_invoice_exists(guardian, month_start, month_end):
    return frappe.db.exists("Sales Invoice", {
        "customer": guardian,
        "posting_date": ["between", [month_start, month_end]],
        "docstatus": ["!=", 2]
    })


def generate_monthly_invoices():
    if getdate(nowdate()).day != 1:
        return
    month_start = get_first_day(today())
    month_end = get_last_day(today())
    month_label = getdate(today()).strftime("%B %Y")
    batch_size = 50
    start = 0
    success_count = 0
    error_count = 0
    skip_count = 0
    while True:
        active_children = frappe.get_all("Child Profile",
            filters={"status": "Active"},
            fields=["name", "full_name", "guardian", "assigned_classroom"],
            limit=batch_size, start=start, order_by="name asc")
        if not active_children:
            break
        for child in active_children:
            if not child.guardian:
                frappe.log_error(f"Child {child.full_name} has no guardian.", "Invoice Generator")
                skip_count += 1
                continue
            if not child.assigned_classroom:
                frappe.log_error(f"Child {child.full_name} has no classroom.", "Invoice Generator")
                skip_count += 1
                continue
            if _is_invoice_exists(child.guardian, month_start, month_end):
                skip_count += 1
                continue
            try:
                if not frappe.db.exists("Classroom", child.assigned_classroom):
                    skip_count += 1
                    continue
                classroom = frappe.get_doc("Classroom", child.assigned_classroom)
                if not classroom.monthly_fee or classroom.monthly_fee <= 0:
                    skip_count += 1
                    continue
                if not frappe.db.exists("Item", "Tuition Fee"):
                    error_count += 1
                    continue
                frappe.db.begin()
                invoice = frappe.new_doc("Sales Invoice")
                invoice.customer = child.guardian
                invoice.posting_date = today()
                invoice.due_date = month_end
                invoice.append("items", {
                    "item_code": "Tuition Fee",
                    "qty": 1,
                    "rate": classroom.monthly_fee,
                    "description": f"Monthly tuition for {child.full_name} — {month_label}"
                })
                invoice.insert(ignore_permissions=True)
                invoice.submit()
                frappe.db.commit()
                success_count += 1
            except Exception as e:
                frappe.db.rollback()
                error_count += 1
                frappe.log_error(f"Invoice failed for {child.full_name}: {str(e)}", "Invoice Generator")
        start += batch_size
    frappe.logger().info(f"Invoices ({month_label}): {success_count} created, {skip_count} skipped, {error_count} failed.")


def send_payment_reminders():
    overdue_invoices = frappe.get_all("Sales Invoice",
        filters={"status": "Overdue", "docstatus": 1},
        fields=["name", "customer", "outstanding_amount", "due_date"])
    for inv in overdue_invoices:
        try:
            customer = frappe.get_doc("Customer", inv.customer)
            if not customer.email_id:
                continue
            frappe.sendmail(
                recipients=[customer.email_id],
                subject=f"Payment Reminder — Invoice {inv.name} | Rhema Daycare",
                message=f"""
                    <p>Dear {customer.customer_name},</p>
                    <table border="1" cellpadding="6" style="border-collapse:collapse;">
                        <tr><td><strong>Invoice No</strong></td><td>{inv.name}</td></tr>
                        <tr><td><strong>Outstanding</strong></td><td>KES {inv.outstanding_amount:,.2f}</td></tr>
                        <tr><td><strong>Due Date</strong></td><td>{inv.due_date}</td></tr>
                    </table>
                    <p>Thank you,<br><strong>Rhema Daycare</strong></p>
                """
            )
        except Exception as e:
            frappe.log_error(f"Reminder failed for {inv.name}: {str(e)}", "Payment Reminder")


def calculate_late_pickup_fees():
    late_cutoff_str = str(_get_setting("cutoff_time", "17:30:00"))
    late_fee_per_hour = float(_get_setting("late_fee_per_hour", 200))
    late_cutoff = get_time(late_cutoff_str)
    late_logs = frappe.get_all("Child Attendance Log",
        filters={"check_out": ["is", "set"], "late_fee_charged": 0, "status": "Present"},
        fields=["name", "child", "check_in", "check_out"])
    for log in late_logs:
        try:
            if not log.check_out:
                continue
            checkout_time = get_time(log.check_out)
            if checkout_time <= late_cutoff:
                continue
            hours_late = time_diff_in_hours(
                str(log.check_out),
                f"{getdate(log.check_out)} {late_cutoff_str}"
            )
            if hours_late <= 0:
                continue
            fee = round(hours_late * late_fee_per_hour, 2)
            if not frappe.db.exists("Child Profile", log.child):
                continue
            child = frappe.get_doc("Child Profile", log.child)
            frappe.db.set_value("Child Attendance Log", log.name, {
                "late_fee_charged": 1,
                "late_fee_amount": fee
            })
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Late fee failed for {log.name}: {str(e)}", "Late Fee Calculator")
