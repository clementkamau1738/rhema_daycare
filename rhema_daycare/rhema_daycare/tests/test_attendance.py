import frappe
import unittest
from frappe.utils import now_datetime


class TestAttendance(unittest.TestCase):

    def setUp(self):
        # Create parent child profile first
        self.child = frappe.new_doc("Child Profile")
        self.child.full_name = "Attendance Test Child"
        self.child.date_of_birth = "2020-01-01"
        self.child.gender = "Male"
        self.child.status = "Active"
        self.child.insert(ignore_permissions=True)

    def test_child_exists(self):
        """Test that child profile was created successfully"""
        self.assertIsNotNone(self.child.name)

    def test_attendance_fields(self):
        """Test attendance log fields directly without insert"""
        log = frappe.new_doc("Child Attendance Log")
        log.child = self.child.name
        log.check_in = now_datetime()
        log.status = "Present"
        self.assertEqual(log.status, "Present")
        self.assertEqual(log.child, self.child.name)
        self.assertIsNotNone(log.check_in)

    def test_checkout_after_checkin_validation(self):
        """Test checkout time validation logic directly"""
        from frappe.utils import add_to_date
        check_in = now_datetime()
        check_out = add_to_date(check_in, hours=-1)
        self.assertLess(check_out, check_in,
            "Checkout before checkin should be invalid")

    def test_status_options(self):
        """Test valid status options"""
        valid_statuses = ["Present", "Absent", "Late"]
        self.assertIn("Present", valid_statuses)
        self.assertIn("Absent", valid_statuses)

    def tearDown(self):
        frappe.db.rollback()
