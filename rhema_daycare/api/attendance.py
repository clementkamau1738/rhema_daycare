import frappe


@frappe.whitelist()
def checkin_child(child_id):
    """Called by QR scanner mobile app"""

    # Find the child record
    child = frappe.get_doc("Child Profile", {"name": child_id})

    if not child:
        frappe.throw("Child not found.")

    if child.status != "Active":
        frappe.throw(
            f"{child.full_name} is not currently enrolled as Active."
        )

    # Create attendance log
    log = frappe.new_doc("Child Attendance Log")
    log.child = child.name
    log.check_in = frappe.utils.now_datetime()
    log.status = "Present"
    log.insert(ignore_permissions=True)

    # Notify parent via email
    notify_parent_checkin(child)

    return {
        "status": "success",
        "child": child.full_name,
        "check_in": str(log.check_in)
    }


@frappe.whitelist()
def checkout_child(child_id):
    """Called by QR scanner mobile app on pickup"""

    child = frappe.get_doc("Child Profile", {"name": child_id})

    if not child:
        frappe.throw("Child not found.")

    # Find today's open attendance log (no check_out yet)
    log_name = frappe.db.get_value(
        "Child Attendance Log",
        {
            "child": child.name,
            "check_out": ("is", "not set"),
            "status": "Present"
        },
        "name"
    )

    if not log_name:
        frappe.throw(
            f"No open check-in found for {child.full_name} today."
        )

    log = frappe.get_doc("Child Attendance Log", log_name)
    log.check_out = frappe.utils.now_datetime()
    log.save(ignore_permissions=True)

    return {
        "status": "success",
        "child": child.full_name,
        "check_out": str(log.check_out)
    }


def notify_parent_checkin(child):
    """Send email notification to parent/guardian on check-in"""

    if not child.guardian:
        return

    parent = frappe.get_doc("Customer", child.guardian)

    if not parent.email_id:
        return

    frappe.sendmail(
        recipients=[parent.email_id],
        subject=f"{child.full_name} has arrived at Rhema Daycare",
        message=f"""
            <p>Dear {parent.customer_name},</p>
            <p>This is to notify you that <strong>{child.full_name}</strong>
            has been checked in at <strong>Rhema Daycare</strong>.</p>
            <p><strong>Check-in time:</strong> {frappe.utils.now_datetime()}</p>
            <p>Thank you for choosing Rhema Daycare.</p>
        """
    )