import frappe
from frappe.utils import today, get_first_day, get_last_day, getdate


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
    if getdate(today()).day != 1:
        return
    month_start = get_first_day(today())
    month_end = get_last_day(today())
    batch_size = 50
    start = 0
    success = 0
    while True:
        children = frappe.get_all("Child Profile",
            filters={"status": "Active"},
            fields=["name", "full_name", "guardian", "assigned_classroom"],
            limit=batch_size, start=start, order_by="name asc")
        if not children:
            break
        for child in children:
            try:
                if not child.guardian or not child.assigned_classroom:
                    continue
                if _is_invoice_exists(child.guardian, month_start, month_end):
                    continue
                if not frappe.db.exists("Classroom", child.assigned_classroom):
                    continue
                classroom = frappe.get_doc("Classroom", child.assigned_classroom)
                if not getattr(classroom, "monthly_fee", None) or classroom.monthly_fee <= 0:
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
                    "description": f"Monthly tuition for {child.full_name}"
                })
                invoice.insert(ignore_permissions=True)
                invoice.submit()
                frappe.db.commit()
                success += 1
            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(str(e), "Invoice Error")
        start += batch_size
    frappe.logger().info(f"Invoices generated: {success}")


def send_payment_reminders():
    overdue = frappe.get_all("Sales Invoice",
        filters={"status": "Overdue", "docstatus": 1},
        fields=["name", "customer", "outstanding_amount", "due_date"])
    for inv in overdue:
        try:
            customer = frappe.get_doc("Customer", inv.customer)
            if not customer.email_id:
                continue
            frappe.sendmail(
                recipients=[customer.email_id],
                subject=f"Payment Reminder — {inv.name} | Rhema Daycare",
                message=f"<p>Dear {customer.customer_name},</p><p>Invoice {inv.name} of KES {inv.outstanding_amount:,.2f} is overdue. Due: {inv.due_date}</p>"
            )
        except Exception as e:
            frappe.log_error(str(e), "Reminder Error")
