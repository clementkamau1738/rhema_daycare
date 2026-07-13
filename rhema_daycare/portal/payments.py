import re
import frappe
from frappe import _
from rhema_daycare.billing.mpesa import stk_push, _format_phone


@frappe.whitelist(methods=["POST"])
def initiate_payment(invoice_name, phone):
    """Portal 'Pay now' entrypoint. Verifies the logged-in guardian actually
    owns this invoice before triggering a real STK push."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)

    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw(_("Your account is not linked to a guardian record."), frappe.PermissionError)

    if not re.match(r'^254[17]\d{8}$', _format_phone(phone)):
        frappe.throw(_("Enter a valid Kenyan phone number (e.g. 0712345678)."))

    # Rate limit — checked here (fail fast on a recent request), but only set
    # once the invoice lookup below confirms this attempt will actually
    # proceed, so a bad invoice_name doesn't burn a legitimate retry's
    # cooldown. Each successful call is a real, billable Daraja API request
    # and an unsolicited payment prompt on someone's phone; phone is
    # intentionally not restricted to the guardian's own number (payment is
    # often made from a relative's phone), so without this a guardian could
    # otherwise spam STK push requests at an arbitrary number using their own
    # invoice.
    cache_key = f"rhema_stk_push_{frappe.session.user}"
    if frappe.cache().get(cache_key):
        frappe.throw(_("Please wait before requesting another payment prompt."))

    invoice = frappe.db.get_value(
        "Sales Invoice",
        {"name": invoice_name, "customer": guardian_name, "docstatus": 1},
        ["name", "outstanding_amount"],
        as_dict=True
    )
    if not invoice:
        frappe.throw(_("Invoice not found or does not belong to you."), frappe.PermissionError)
    if not invoice.outstanding_amount or invoice.outstanding_amount <= 0:
        frappe.throw(_("This invoice has no outstanding balance."))

    frappe.cache().set(cache_key, 1, ex=60)

    result = stk_push(phone, invoice.outstanding_amount, invoice.name)
    return {
        "status": "pending",
        "message": result.get("customer_message") or
                    _("Check your phone to complete the M-Pesa payment."),
        "checkout_request_id": result.get("checkout_request_id"),
    }
