import frappe
from frappe import _
from frappe.utils import format_datetime


def send_checkin_notification(child):
    _dispatch(
        notification_type="Check-in Alert",
        guardian_name=child.get("guardian"),
        template="Rhema: Check-in Alert",
        context={
            "child_name": child.get("full_name"),
            "checkin_time": format_datetime(frappe.utils.now_datetime()),
        },
        fallback_subject=_("{0} has arrived at Rhema Daycare").format(child.get("full_name")),
        fallback_message=_("Check-in recorded at {0}.").format(
            format_datetime(frappe.utils.now_datetime())),
        priority="normal"
    )


def send_checkout_notification(child, checkout_time):
    _dispatch(
        notification_type="Check-out Alert",
        guardian_name=child.get("guardian"),
        template="Rhema: Check-out Alert",
        context={
            "child_name": child.get("full_name"),
            "checkout_time": format_datetime(checkout_time),
        },
        fallback_subject=_("{0} has been picked up").format(child.get("full_name")),
        fallback_message=_("Check-out recorded at {0}. Have a great evening!").format(
            format_datetime(checkout_time)),
        priority="normal"
    )


def send_late_pickup_alert(child, minutes_late, fee=None):
    if fee is not None:
        fee_line = _("Late fee: <strong>KES {0:,.0f}</strong>.<br><br>").format(float(fee))
    else:
        fee_line = _("A late fee is being applied. Please collect your child urgently.<br><br>")
    _dispatch(
        notification_type="Late Pickup Alert",
        guardian_name=child.get("guardian"),
        template="Rhema: Late Pickup Alert",
        context={
            "child_name": child.get("full_name"),
            "minutes_late": f"{minutes_late:.0f}",
            "fee": f"{float(fee):,.0f}" if fee is not None else None,
        },
        fallback_subject=_("Late pickup alert — {0}").format(child.get("full_name")),
        fallback_message=_(
            "<strong>{0}</strong> is still at Rhema Daycare — "
            "{1:.0f} minutes past the pickup cutoff.<br><br>"
        ).format(child.get("full_name"), minutes_late) + fee_line + _("— Rhema Daycare team"),
        priority="high"
    )


def send_absence_alert(child):
    _dispatch(
        notification_type="Absence Alert",
        guardian_name=child.get("guardian"),
        template="Rhema: Absence Alert",
        context={"child_name": child.get("full_name")},
        fallback_subject=_("Absence alert — {0} has not checked in").format(
            child.get("full_name")),
        fallback_message=_(
            "<strong>{0}</strong> has not checked in at Rhema Daycare "
            "by the expected time.<br><br>"
            "If this is a planned absence, no action is needed.<br>"
            "If unexpected, please contact us immediately.<br><br>"
            "— Rhema Daycare team"
        ).format(child.get("full_name")),
        priority="high"
    )


def send_payment_reminder(invoice, guardian_name):
    _dispatch(
        notification_type="Payment Reminder",
        guardian_name=guardian_name,
        template="Rhema: Payment Reminder",
        context={
            "invoice_number": invoice.get("name"),
            "outstanding_amount": f"{float(invoice.get('outstanding_amount') or 0):,.0f}",
            "due_date": invoice.get("due_date"),
        },
        fallback_subject=_("Payment reminder — Invoice {0}").format(invoice.get("name")),
        fallback_message=_(
            "Invoice <strong>{0}</strong> for "
            "<strong>KES {1:,.0f}</strong> is overdue.<br>"
            "Due date: {2}<br><br>"
            "Please pay via your parent portal.<br><br>"
            "— Rhema Daycare team"
        ).format(
            invoice.get("name"),
            float(invoice.get("outstanding_amount") or 0),
            invoice.get("due_date")
        ),
        priority="normal"
    )


def send_enrollment_approved(child):
    _dispatch(
        notification_type="Enrollment Approved",
        guardian_name=child.get("guardian"),
        template="Rhema: Enrollment Approved",
        context={"child_name": child.get("full_name")},
        fallback_subject=_("{0}'s enrollment has been approved").format(child.get("full_name")),
        fallback_message=_(
            "Good news — <strong>{0}</strong>'s enrollment at Rhema Daycare "
            "has been approved. They are now available for check-in and billing.<br><br>"
            "— Rhema Daycare team"
        ).format(child.get("full_name")),
        priority="normal"
    )


def send_invoice_generated(invoice, guardian_name):
    amount = float(invoice.get("grand_total") or invoice.get("outstanding_amount") or 0)
    _dispatch(
        notification_type="Invoice Generated",
        guardian_name=guardian_name,
        template="Rhema: Invoice Generated",
        context={
            "invoice_number": invoice.get("name"),
            "outstanding_amount": f"{amount:,.0f}",
            "due_date": invoice.get("due_date"),
        },
        fallback_subject=_("Invoice {0} generated").format(invoice.get("name")),
        fallback_message=_(
            "A new invoice <strong>{0}</strong> for "
            "<strong>KES {1:,.0f}</strong> has been generated.<br>"
            "Due date: {2}<br><br>"
            "Please pay via your parent portal.<br><br>"
            "— Rhema Daycare team"
        ).format(invoice.get("name"), amount, invoice.get("due_date")),
        priority="normal"
    )


def send_admin_alert(subject, message):
    settings = frappe.get_cached_doc("Daycare Settings")
    admin_email = settings.get("admin_email")
    fallback_subject = f"[Rhema Daycare] {subject}"
    if not admin_email:
        _log_notification("Admin Alert", None, fallback_subject,
            "Skipped", "Admin email not configured in Daycare Settings.")
        return
    # Route through the same Email Template lookup as every other notification
    # type, so "Rhema: Admin Alert" (shipped as a fixture) is actually used
    # instead of sitting unreferenced while this built its message inline.
    rendered_subject, rendered_message = _render(
        "Rhema: Admin Alert",
        {"subject": subject, "message": message},
        fallback_subject,
        f"<p>{message}</p>"
    )
    try:
        frappe.sendmail(
            recipients=[admin_email],
            subject=rendered_subject,
            message=rendered_message,
            now=True
        )
        _log_notification("Admin Alert", admin_email, rendered_subject, "Sent", "")
    except Exception as e:
        frappe.log_error(title="Admin Alert Failed", message=str(e))
        _log_notification("Admin Alert", admin_email, rendered_subject,
            "Failed", str(e))


def _render(template_name, context, fallback_subject, fallback_message):
    """Render subject/message from the named Email Template if it exists
    (admin-customisable via Settings → Email Templates), otherwise fall back
    to the hardcoded text so notifications never break if fixtures haven't
    synced yet."""
    if not frappe.db.exists("Email Template", template_name):
        return fallback_subject, fallback_message
    template = frappe.get_cached_doc("Email Template", template_name)
    subject = frappe.render_template(template.subject, context, is_path=False)
    message = frappe.render_template(template.response, context, is_path=False)
    return subject, message


def _dispatch(notification_type, guardian_name, template, context,
              fallback_subject, fallback_message, priority="normal"):
    """
    Central dispatch — null-safe.
    One failed email never crashes the caller or affects other notifications.

    Guard sequence:
      1. guardian_name present?
      2. Customer record exists?
      3. email_id present and non-empty? (send email if so)
      4. communication_preference includes SMS and mobile_no present? (send SMS if so)
      5. Every attempt/skip/failure is written to Notification Log.

    "Sent" only means delivery was actually attempted and succeeded. A
    normal-priority email (now=False) is merely *accepted into Frappe's
    Email Queue* at this point, not delivered — that's logged as "Queued"
    with a reference to the Email Queue row, and reconcile_queued_notifications
    (hourly) resolves it to Sent/Failed once real delivery is attempted.
    High-priority sends (now=True) deliver synchronously, so "Sent" is
    already accurate for those.
    """
    if not guardian_name:
        _log_notification(notification_type, None, fallback_subject,
            "Skipped", "No guardian on the record.")
        return

    guardian = frappe.db.get_value(
        "Customer",
        guardian_name,
        ["customer_name", "email_id", "communication_preference", "guardian_mobile_no"],
        as_dict=True
    )

    if not guardian:
        _log_notification(notification_type, guardian_name, fallback_subject,
            "Skipped", f"Guardian {guardian_name!r} not found.")
        return

    try:
        subject, message = _render(template, context, fallback_subject, fallback_message)
    except Exception as e:
        # A syntactically-valid-but-runtime-broken admin-edited Email
        # Template (e.g. a bad variable/filter reference) must never reach
        # the caller — fall back to the hardcoded text exactly like the
        # "template doesn't exist" case already does.
        frappe.log_error(title="Notification Template Render Failed", message=str(e))
        subject, message = fallback_subject, fallback_message

    preference = guardian.get("communication_preference") or "Email"
    email = (guardian.get("email_id") or "").strip()
    mobile_no = (guardian.get("guardian_mobile_no") or "").strip()

    email_sent = False
    email_queue_doc = None
    if preference in ("Email", "Both"):
        if email:
            try:
                email_queue_doc = frappe.sendmail(
                    recipients=[email], subject=subject, message=message,
                    now=(priority == "high"))
                email_sent = True
            except Exception as e:
                _log_notification(notification_type, email, subject, "Failed", str(e))
        else:
            _log_notification(notification_type, guardian_name, subject,
                "Skipped", "No email on file.")

    sms_sent = False
    if preference in ("SMS", "Both"):
        if mobile_no:
            sms_sent, sms_reason = _send_sms(mobile_no, subject, message)
            if not sms_sent:
                _log_notification(notification_type, guardian_name, subject, "Failed", sms_reason)
        else:
            _log_notification(notification_type, guardian_name, subject,
                "Skipped", "No mobile number on file.")

    if email_sent or sms_sent:
        channels = ", ".join(c for c, sent in (("email", email_sent), ("sms", sms_sent)) if sent)
        recipient = guardian.customer_name or guardian_name
        ref_doctype = "Email Queue" if email_queue_doc else None
        ref_name = email_queue_doc.name if email_queue_doc else None
        if email_sent and priority != "high":
            _log_notification(notification_type, recipient, subject, "Queued",
                f"Queued via {channels}; awaiting delivery confirmation.",
                reference_doctype=ref_doctype, reference_name=ref_name)
        else:
            _log_notification(notification_type, recipient, subject, "Sent",
                f"Sent via {channels}.", reference_doctype=ref_doctype, reference_name=ref_name)


def _send_sms(mobile_no, subject, message):
    """Returns (sent: bool, reason: str) — never raises.

    Frappe core's send_sms() does NOT raise when no gateway is configured;
    it silently no-ops (msgprint only, which is a no-op outside an
    interactive session), which used to make this function report success
    for a message that was never actually transmitted. Checking the gateway
    up front closes that false-positive."""
    if not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
        return False, "SMS gateway not configured in SMS Settings."
    try:
        from frappe.core.doctype.sms_settings.sms_settings import send_sms
        plain_text = frappe.utils.strip_html(message)[:160]
        send_sms([mobile_no], f"{subject}: {plain_text}")
        return True, ""
    except Exception as e:
        frappe.log_error(title="SMS Send Failed", message=str(e))
        return False, str(e)


def _log_notification(notification_type, recipient, subject, status, reason,
                       reference_doctype=None, reference_name=None):
    try:
        frappe.get_doc({
            "doctype": "Rhema Notification Log",
            "notification_type": notification_type,
            "recipient": recipient,
            "subject": subject,
            "status": status,
            "reason": reason,
            "reference_doctype": reference_doctype,
            "reference_name": reference_name,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(title="Notification Log Write Failed", message=str(e))
    # Mirror to Error Log too for Skipped/Failed, matching prior behaviour.
    # Never let logging itself take down the caller — title has a 140-char limit.
    if status in ("Skipped", "Failed"):
        try:
            frappe.log_error(
                title=f"Notification: {status}"[:140],
                message=f"{notification_type} — {reason}\nSubject: {subject}")
        except Exception:
            pass


def reconcile_queued_notifications():
    """Scheduled job (hourly): resolve 'Queued' Rhema Notification Log
    entries against the actual outcome of the Email Queue row they point
    to, so 'Sent' always means delivered, not just accepted for delivery."""
    rows = frappe.get_all(
        "Rhema Notification Log",
        filters={"status": "Queued", "reference_doctype": "Email Queue"},
        fields=["name", "reference_name"]
    )
    for row in rows:
        if not row.reference_name or not frappe.db.exists("Email Queue", row.reference_name):
            continue
        queue = frappe.db.get_value("Email Queue", row.reference_name, ["status", "error"], as_dict=True)
        if queue.status == "Sent":
            frappe.db.set_value("Rhema Notification Log", row.name, "status", "Sent")
        elif queue.status == "Error":
            frappe.db.set_value("Rhema Notification Log", row.name, {
                "status": "Failed",
                "reason": queue.error or "Delivery failed after retries.",
            })
        # Not Sent / Sending / Partially Sent: still in flight, leave as
        # Queued — checked again next run.
    if rows:
        frappe.db.commit()
