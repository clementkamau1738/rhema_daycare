"""
M-Pesa Daraja API integration (STK Push).

Real Safaricom Daraja endpoints are used here, driven by credentials stored
in Daycare Settings (mpesa_environment/shortcode/consumer_key/consumer_secret/
passkey). This module cannot be exercised against a live phone in a sandbox
without real Safaricom-issued credentials — see test_mpesa.py for a
request-shape unit test that mocks the network call instead.
"""
import base64
import hmac
import re
from datetime import datetime

import frappe
import requests
from frappe import _

SANDBOX_BASE = "https://sandbox.safaricom.co.ke"
PRODUCTION_BASE = "https://api.safaricom.co.ke"


def _settings():
    return frappe.get_cached_doc("Daycare Settings")


def _get_or_create_callback_secret():
    """Safaricom's Daraja callbacks carry no signature of their own — the
    original implementation authenticated an inbound callback purely by
    matching CheckoutRequestID against a pre-created Integration Request,
    which is guessable/replayable. This lazily generates and persists a
    per-site secret, embedded in the callback URL and checked on every
    inbound request, closing that gap without needing anything from
    Safaricom's side."""
    settings = _settings()
    secret = settings.get_password("mpesa_callback_secret", raise_exception=False)
    if secret:
        return secret
    secret = frappe.generate_hash(length=32)
    frappe.db.set_single_value("Daycare Settings", "mpesa_callback_secret", secret)
    frappe.db.commit()
    return secret


def _base_url():
    settings = _settings()
    return PRODUCTION_BASE if settings.get("mpesa_environment") == "Production" else SANDBOX_BASE


def get_access_token():
    """OAuth2 client-credentials token, cached for slightly under its 1-hour lifetime."""
    cache_key = "rhema_mpesa_access_token"
    cached = frappe.cache().get(cache_key)
    if cached:
        return cached.decode() if isinstance(cached, bytes) else cached

    settings = _settings()
    consumer_key = settings.get("mpesa_consumer_key")
    consumer_secret = settings.get_password("mpesa_consumer_secret", raise_exception=False)
    if not consumer_key or not consumer_secret:
        frappe.throw(_("M-Pesa consumer key/secret are not configured in Daycare Settings."))

    response = requests.get(
        f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials",
        auth=(consumer_key, consumer_secret),
        timeout=15
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    frappe.cache().set("rhema_mpesa_access_token", token, ex=3500)
    return token


def _format_phone(phone):
    """Normalise to Safaricom's 2547XXXXXXXX / 2541XXXXXXXX format."""
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "254" + digits[1:]
    elif digits.startswith("7") or digits.startswith("1"):
        digits = "254" + digits
    return digits


def build_stk_push_payload(phone, amount, invoice_name, callback_url):
    """Pure request-building logic — kept separate from the network call so it
    can be unit tested without hitting a real endpoint."""
    settings = _settings()
    shortcode = settings.get("mpesa_shortcode")
    passkey = settings.get_password("mpesa_passkey", raise_exception=False)
    if not shortcode or not passkey:
        frappe.throw(_("M-Pesa shortcode/passkey are not configured in Daycare Settings."))

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = base64.b64encode(
        f"{shortcode}{passkey}{timestamp}".encode()
    ).decode()
    phone = _format_phone(phone)

    return {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(round(float(amount))),
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": invoice_name,
        "TransactionDesc": f"Rhema Daycare invoice {invoice_name}",
    }


def stk_push(phone, amount, invoice_name):
    """Initiate an STK push and log the CheckoutRequestID via Integration
    Request so the async callback can be correlated back to the invoice."""
    callback_secret = _get_or_create_callback_secret()
    callback_url = frappe.utils.get_url(
        "/api/method/rhema_daycare.billing.mpesa.mpesa_callback"
        f"?token={callback_secret}")
    payload = build_stk_push_payload(phone, amount, invoice_name, callback_url)
    token = get_access_token()

    response = requests.post(
        f"{_base_url()}/mpesa/stkpush/v1/processrequest",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15
    )
    result = response.json()

    checkout_request_id = result.get("CheckoutRequestID")
    frappe.get_doc({
        "doctype": "Integration Request",
        "integration_request_service": "M-Pesa STK Push",
        "request_id": checkout_request_id,
        "reference_doctype": "Sales Invoice",
        "reference_docname": invoice_name,
        "data": frappe.as_json(payload),
        "output": frappe.as_json(result),
        "status": "Queued" if checkout_request_id else "Failed",
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    if not checkout_request_id:
        frappe.throw(
            _("M-Pesa STK push failed: {0}").format(
                result.get("errorMessage") or result.get("ResponseDescription") or "Unknown error"))

    return {
        "checkout_request_id": checkout_request_id,
        "customer_message": result.get("CustomerMessage"),
    }


@frappe.whitelist(allow_guest=True)
def mpesa_callback():
    """Safaricom calls this back unauthenticated. Authenticated by a secret
    token embedded in the callback URL (see _get_or_create_callback_secret)
    checked first, then correlated against a known CheckoutRequestID, then
    the declared payment amount is cross-checked against what was actually
    requested in the original STK push before any Payment Entry is created —
    three independent checks, since none of Safaricom's own payload is
    otherwise verifiable."""
    token = frappe.local.form_dict.get("token")
    expected_token = _settings().get_password("mpesa_callback_secret", raise_exception=False)
    if not expected_token or not token or not hmac.compare_digest(str(token), str(expected_token)):
        frappe.log_error(
            title="M-Pesa Callback: Bad Token",
            message="Rejected an inbound M-Pesa callback with a missing or incorrect token.")
        frappe.local.response["http_status_code"] = 403
        return {"ResultDesc": "Rejected"}

    payload = frappe.local.form_dict
    try:
        stk_callback = payload["Body"]["stkCallback"]
    except (KeyError, TypeError):
        frappe.local.response["http_status_code"] = 400
        return {"ResultDesc": "Invalid payload"}

    checkout_request_id = stk_callback.get("CheckoutRequestID")
    result_code = stk_callback.get("ResultCode")

    integration_request_name = frappe.db.get_value(
        "Integration Request", {"request_id": checkout_request_id}, "name")
    if not integration_request_name:
        frappe.log_error(
            title="M-Pesa Callback: Unknown Request",
            message=f"M-Pesa callback for unknown CheckoutRequestID {checkout_request_id}")
        return {"ResultDesc": "Accepted"}

    # Lock the Integration Request row and read its status as part of the
    # locking query itself (not a separate plain read afterward), so this
    # sees the latest committed status rather than a pre-lock snapshot —
    # same REPEATABLE-READ pitfall found and fixed for Classroom capacity.
    # This closes both a forged replay and a legitimate Safaricom callback
    # redelivery: either would otherwise create a second Payment Entry
    # against an invoice already marked paid.
    locked = frappe.db.sql(
        "SELECT status FROM `tabIntegration Request` WHERE name = %s FOR UPDATE",
        (integration_request_name,), as_dict=True)
    if locked and locked[0].status == "Completed":
        frappe.log_error(
            title="M-Pesa Callback: Duplicate",
            message=(f"Ignored a replayed/duplicate callback for CheckoutRequestID "
                     f"{checkout_request_id} — already processed."))
        return {"ResultDesc": "Accepted"}

    integration_request = frappe.get_doc("Integration Request", integration_request_name)
    integration_request.db_set("output", frappe.as_json(payload))

    if result_code != 0:
        integration_request.db_set("status", "Failed")
        integration_request.db_set("error", stk_callback.get("ResultDesc"))
        return {"ResultDesc": "Accepted"}

    items = {
        item["Name"]: item.get("Value")
        for item in stk_callback.get("CallbackMetadata", {}).get("Item", [])
    }
    amount = items.get("Amount")
    mpesa_receipt = items.get("MpesaReceiptNumber")

    # Cross-check the declared amount against what this specific
    # CheckoutRequestID actually requested, rather than trusting the
    # callback's Amount item blindly.
    requested_amount = None
    try:
        requested_amount = frappe.parse_json(integration_request.data or "{}").get("Amount")
    except Exception:
        requested_amount = None
    if requested_amount is not None and amount is not None and \
            int(round(float(amount))) != int(requested_amount):
        integration_request.db_set("status", "Failed")
        integration_request.db_set(
            "error",
            f"Callback amount {amount} does not match requested amount {requested_amount}.")
        frappe.log_error(
            title="M-Pesa Callback: Amount Mismatch",
            message=(f"CheckoutRequestID {checkout_request_id}: callback amount "
                     f"{amount} != requested {requested_amount}."))
        return {"ResultDesc": "Accepted"}

    invoice_name = integration_request.reference_docname
    _create_payment_entry(invoice_name, amount, mpesa_receipt)
    integration_request.db_set("status", "Completed")
    frappe.db.commit()

    return {"ResultDesc": "Accepted"}


def _create_payment_entry(invoice_name, amount, mpesa_receipt):
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    payment = frappe.new_doc("Payment Entry")
    payment.payment_type = "Receive"
    payment.company = invoice.company
    payment.party_type = "Customer"
    payment.party = invoice.customer
    payment.paid_amount = amount
    payment.received_amount = amount
    payment.reference_no = mpesa_receipt
    payment.reference_date = frappe.utils.today()
    payment.mode_of_payment = "M-Pesa" if frappe.db.exists("Mode of Payment", "M-Pesa") else None
    payment.append("references", {
        "reference_doctype": "Sales Invoice",
        "reference_name": invoice_name,
        "allocated_amount": amount,
    })
    payment.insert(ignore_permissions=True)
    payment.submit()
