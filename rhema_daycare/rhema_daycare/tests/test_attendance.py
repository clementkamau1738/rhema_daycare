import frappe
import unittest
from frappe.model.workflow import apply_workflow
from rhema_daycare.api import attendance as attendance_api


class TestAttendance(unittest.TestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        guardian_name = "Test Guardian - Attendance"
        if frappe.db.exists("Customer", guardian_name):
            self.guardian = frappe.get_doc("Customer", guardian_name)
        else:
            self.guardian = frappe.new_doc("Customer")
            self.guardian.customer_name = guardian_name
            self.guardian.customer_type = "Individual"
            self.guardian.email_id = "guardian-attendance@example.com"
            self.guardian.insert(ignore_permissions=True)

        existing = frappe.db.get_value("Child Profile", {
            "full_name": "Attendance Test Child",
            "guardian": self.guardian.name
        }, "name")
        if existing:
            self.child = frappe.get_doc("Child Profile", existing)
            if self.child.status != "Active":
                self.child = apply_workflow(self.child, "Force Approve")
                frappe.db.commit()
        else:
            child = frappe.new_doc("Child Profile")
            child.full_name = "Attendance Test Child"
            child.date_of_birth = "2020-01-01"
            child.gender = "Male"
            child.guardian = self.guardian.name
            child.append("emergency_contacts", {
                "contact_name": "Emergency Contact",
                "phone_number": "0712345678",
                "relationship": "Mother"
            })
            child.insert(ignore_permissions=True)
            frappe.db.commit()
            self.child = apply_workflow(child, "Force Approve")
            frappe.db.commit()
        self.assertEqual(self.child.status, "Active")

        # each test needs a clean attendance slate for this child
        frappe.db.delete("Child Attendance Log", {"child": self.child.name})
        frappe.db.commit()

        # clear any rate-limit cache left over from a previous run against this child
        frappe.cache().delete(f"rhema_checkin_{self.child.name}")
        frappe.cache().delete(f"rhema_checkout_{self.child.name}")

    def tearDown(self):
        frappe.db.rollback()

    def test_checkin_creates_open_log(self):
        result = attendance_api.checkin_child(self.child.name)
        self.assertEqual(result["status"], "success")
        log = frappe.get_doc("Child Attendance Log", result["log"])
        self.assertEqual(log.child, self.child.name)
        self.assertIsNone(log.check_out)

    def test_duplicate_checkin_is_rejected(self):
        attendance_api.checkin_child(self.child.name)
        frappe.cache().delete(f"rhema_checkin_{self.child.name}")
        with self.assertRaises(frappe.ValidationError):
            attendance_api.checkin_child(self.child.name)

    def test_checkout_without_checkin_is_rejected(self):
        with self.assertRaises(frappe.DoesNotExistError):
            attendance_api.checkout_child(self.child.name)

    def test_checkout_after_checkin_succeeds(self):
        checkin_result = attendance_api.checkin_child(self.child.name)
        frappe.cache().delete(f"rhema_checkout_{self.child.name}")
        checkout_result = attendance_api.checkout_child(self.child.name)
        self.assertEqual(checkout_result["status"], "success")
        log = frappe.get_doc("Child Attendance Log", checkin_result["log"])
        self.assertIsNotNone(log.check_out)
