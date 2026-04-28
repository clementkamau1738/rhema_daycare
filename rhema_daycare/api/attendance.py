import frappe
from frappe.utils import now_datetime, today


def _get_setting(fieldname, default=None):
    """Safely get value from Rhema Daycare Settings"""
    try:
        return frappe.db.get_single_value(
            "Rhema Daycare Settings", fieldname
        ) or default
    except Exception:
        return default


def _check_rate_limit(child_id):
    """
    Prevent spam/brute force attacks.
    Limits check-in requests to 1 per 30 seconds per child.
    """
    cache_key = f"checkin_rate_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw(
            "Too many requests. Please wait 30 seconds before trying again.",
            frappe.ValidationError
        )
    frappe.cache().set(cache_key, True, expires_in_sec=30)


def _validate_roles():
    """Check user has required role to perform check-in"""
    allowed_roles = ["Teacher", "Daycare Manager", "System Manager"]
    user_roles = frappe.get_roles(frappe.session.user)
    if not any(role in user_roles for role in allowed_roles):
        frappe.throw(
            "You do not have permission to check in children. "
            "Required roles: Teacher, Daycare Manager, or System Manager.",
            frappe.PermissionError
        )


@frappe.whitelist()
def checkin_child(child_id):
    """
    Called by QR scanner mobile app.
    FIXED: Full authentication, rate limiting, input validation.
    """

    # 1. Block guest access
    if frappe.session.user == "Guest":
        frappe.throw(
            "You must be logged in to check in children.",
            frappe.AuthenticationError
        )

    # 2. Check user has correct role
    _validate_roles()

    # 3. Validate input — prevent injection and bad data
    if not child_id:
        frappe.throw("Child ID is required.", frappe.ValidationError)

    child_id = str(child_id).strip()

    if len(child_id) > 50:
        frappe.throw("Invalid child ID format.", frappe.ValidationError)

    # 4. Rate limiting — prevent spam
    _check_rate_limit(child_id)

    # 5. Check child exists
    if not frappe.db.exists("Child Profile", child_id):
        frappe.throw(
            f"Child ID '{child_id}' not found.",
            frappe.DoesNotExistError
        )

    child = frappe.get_doc("Child Profile", child_id)

    # 6. Check child is active
    if child.status != "Active":
        frappe.throw(
            f"{child.full_name} is not currently enrolled as Active.",
            frappe.ValidationError
        )

    # 7. Prevent duplicate check-in on same day
    today_log = frappe.db.get_value(
        "Child Attendance Log",
        {
            "child": child_id,
            "check_in": [">=", today() + " 00:00:00"],
            "check_out": ["is", "not set"]
        },
        "name"
    )
    if today_log:
        frappe.throw(
            f"{child.full_name} is already checked in today (Log: {today_log}).",
            frappe.ValidationError
        )

    # 8. Create attendance log inside transaction
    try:
        frappe.db.begin()
        log = frappe.new_doc("Child Attendance Log")
        log.child = child.name
        log.check_in = now_datetime()
        log.status = "Present"
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            f"Check-in failed for {child.full_name}: {str(e)}",
            "Check-in Error"
        )
        frappe.throw("Check-in failed. Please try again.")

    # 9. Notify parent — non-blocking (failure won't break check-in)
    try:
        _notify_parent_checkin(child)
    except Exception as e:
        frappe.log_error(
            f"Notification failed for {child.full_name}: {str(e)}",
            "Notification Error"
        )

    return {
        "status": "success",
        "child": child.full_name,
        "check_in": str(log.check_in),
        "log_id": log.name,
        "checked_in_by": frappe.session.user
    }


@frappe.whitelist()
def checkout_child(child_id):
    """
    Called by QR scanner on child pickup.
    FIXED: Full authentication and validation.
    """

    # 1. Block guest access
    if frappe.session.user == "Guest":
        frappe.throw(
            "You must be logged in to check out children.",
            frappe.AuthenticationError
        )

    # 2. Check role
    _validate_roles()

    # 3. Validate input
    if not child_id:
        frappe.throw("Child ID is required.", frappe.ValidationError)

    child_id = str(child_id).strip()

    if not frappe.db.exists("Child Profile", child_id):
        frappe.throw("Child not found.", frappe.DoesNotExistError)

    child = frappe.get_doc("Child Profile", child_id)

    # 4. Find open check-in for today
    log_name = frappe.db.get_value(
        "Child Attendance Log",
        {
            "child": child_id,
            "check_in": [">=", today() + " 00:00:00"],
            "check_out": ["is", "not set"],
            "status": "Present"
        },
        "name"
    )

    if not log_name:
        frappe.throw(
            f"No open check-in found for {child.full_name} today.",
            frappe.ValidationError
        )

    # 5. Update check-out inside transaction
    try:
        frappe.db.begin()
        log = frappe.get_doc("Child Attendance Log", log_name)
        log.check_out = now_datetime()
        log.save(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(
            f"Check-out failed for {child.full_name}: {str(e)}",
            "Check-out Error"
        )
        frappe.throw("Check-out failed. Please try again.")

    return {
        "status": "success",
        "child": child.full_name,
        "check_out": str(log.check_out),
        "checked_out_by": frappe.session.user
    }


@frappe.whitelist()
def get_child_status(child_id):
    """
    Get current attendance status for a child.
    Can be called by Teacher, Daycare Manager, or Parent.
    """

    if frappe.session.user == "Guest":
        frappe.throw("Authentication required.", frappe.AuthenticationError)

    if not child_id or not frappe.db.exists("Child Profile", child_id):
        frappe.throw("Child not found.", frappe.DoesNotExistError)

    child = frappe.get_doc("Child Profile", child_id)

    # Parents can only see their own children
    user_roles = frappe.get_roles(frappe.session.user)
    staff_roles = ["Teacher", "Daycare Manager", "System Manager"]
    is_staff = any(role in user_roles for role in staff_roles)

    if not is_staff:
        guardian = frappe.db.get_value(
            "Customer",
            {"email_id": frappe.session.user},
            "name"
        )
        if child.guardian != guardian:
            frappe.throw(
                "You do not have permission to view this child.",
                frappe.PermissionError
            )

    # Get today's attendance
    log = frappe.db.get_value(
        "Child Attendance Log",
        {
            "child": child_id,
            "check_in": [">=", today() + " 00:00:00"]
        },
        ["check_in", "check_out", "status"],
        as_dict=True
    )

    return {
        "child": child.full_name,
        "status": child.status,
        "today_attendance": log or {},
        "classroom": child.assigned_classroom
    }


def _notify_parent_checkin(child):
    """Send email notification to parent on check-in"""
    if not child.guardian:
        return

    if not frappe.db.exists("Customer", child.guardian):
        return

    guardian = frappe.get_doc("Customer", child.guardian)

    if not guardian.email_id:
        frappe.log_error(
            f"No email for guardian {guardian.customer_name}",
            "Notification Skip"
        )
        return

    try:
        frappe.sendmail(
            recipients=[guardian.email_id],
            subject=f"{child.full_name} has arrived at Rhema Daycare",
            message=f"""
                <p>Dear {guardian.customer_name},</p>
                <p><strong>{child.full_name}</strong> has been
                checked in at <strong>Rhema Daycare</strong>.</p>
                <p><strong>Check-in time:</strong> {now_datetime()}</p>
                <p>Thank you for choosing Rhema Daycare.</p>
            """
        )
    except Exception as e:
        frappe.log_error(
            f"Email failed for {child.full_name}: {str(e)}",
            "Email Error"
        )


@frappe.whitelist()
def get_today_log():
    """Get all attendance logs for today"""
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required.", frappe.AuthenticationError)

    logs = frappe.db.sql("""
        SELECT
            cal.name,
            cal.child,
            cp.full_name as child_name,
            cal.check_in,
            cal.check_out,
            cal.status
        FROM `tabChild Attendance Log` cal
        LEFT JOIN `tabChild Profile` cp ON cal.child = cp.name
        WHERE DATE(cal.check_in) = CURDATE()
        ORDER BY cal.check_in DESC
    """, as_dict=True)

    return logs


@frappe.whitelist()
def simulate_late_pickup(child_id):
    """Simulate a late pickup alert for testing"""
    if frappe.session.user == "Guest":
        frappe.throw("Authentication required.", frappe.AuthenticationError)

    child_id = str(child_id).strip()

    if not frappe.db.exists("Child Profile", child_id):
        frappe.throw(f"Child '{child_id}' not found.")

    child = frappe.get_doc("Child Profile", child_id)

    if not child.guardian:
        frappe.throw(f"{child.full_name} has no guardian assigned.")

    guardian = frappe.get_doc("Customer", child.guardian)

    if not guardian.email_id:
        frappe.throw(f"Guardian has no email address.")

    late_fee_per_hour = float(frappe.db.get_single_value(
        "Rhema Daycare Settings", "late_fee_per_hour"
    ) or 200)

    estimated_fee = late_fee_per_hour * 1

    try:
        frappe.sendmail(
            recipients=[guardian.email_id],
            subject=f"⚠️ Late Pickup Alert — {child.full_name} | Rhema Daycare",
            message=f"""
                <p>Dear {guardian.customer_name},</p>
                <p><strong>{child.full_name}</strong> is still at
                Rhema Daycare past the 5:30 PM pickup time.</p>
                <p><strong>Estimated late fee:</strong>
                KES {estimated_fee:,.0f}/hour</p>
                <p>Please arrange for immediate pickup.</p>
                <p><strong>Rhema Daycare Team</strong></p>
            """,
            now=True
        )
    except Exception as e:
        frappe.log_error(str(e), "Late Pickup Simulation Error")

    return {
        "status": "success",
        "child": child.full_name,
        "estimated_fee": estimated_fee
    }
