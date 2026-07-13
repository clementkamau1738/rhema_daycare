import frappe
import unittest
from rhema_daycare.billing.mpesa import build_stk_push_payload, _format_phone


class TestMpesaRequestBuilding(unittest.TestCase):
    """No live Safaricom credentials exist in this environment, so this only
    verifies the request payload/format logic — not an actual STK push."""

    def setUp(self):
        frappe.set_user("Administrator")
        settings = frappe.get_cached_doc("Daycare Settings")
        settings.mpesa_shortcode = "174379"
        settings.mpesa_passkey = "test-passkey"
        settings.flags.ignore_mandatory = True
        settings.save(ignore_permissions=True)
        frappe.clear_cache()

    def tearDown(self):
        frappe.db.rollback()

    def test_phone_normalisation(self):
        self.assertEqual(_format_phone("0712345678"), "254712345678")
        self.assertEqual(_format_phone("712345678"), "254712345678")
        self.assertEqual(_format_phone("254712345678"), "254712345678")

    def test_stk_push_payload_shape(self):
        payload = build_stk_push_payload(
            "0712345678", 12500, "SINV-0001", "https://example.com/callback")
        self.assertEqual(payload["BusinessShortCode"], "174379")
        self.assertEqual(payload["Amount"], 12500)
        self.assertEqual(payload["PartyA"], "254712345678")
        self.assertEqual(payload["PhoneNumber"], "254712345678")
        self.assertEqual(payload["AccountReference"], "SINV-0001")
        self.assertEqual(payload["CallBackURL"], "https://example.com/callback")
        self.assertTrue(payload["Password"])
        self.assertEqual(len(payload["Timestamp"]), 14)
