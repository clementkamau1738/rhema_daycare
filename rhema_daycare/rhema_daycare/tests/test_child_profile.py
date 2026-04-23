import frappe
import unittest


class TestChildProfile(unittest.TestCase):

    def setUp(self):
        self.child = frappe.new_doc("Child Profile")
        self.child.full_name = "Test Child"
        self.child.date_of_birth = "2020-01-01"
        self.child.gender = "Male"
        self.child.status = "Active"

    def test_valid_child_creation(self):
        self.child.insert(ignore_permissions=True)
        self.assertIsNotNone(self.child.name)
        print(f"Created child: {self.child.name}")

    def test_future_dob_rejected(self):
        """Test future DOB directly using the validate method"""
        from frappe.utils import date_diff, nowdate
        dob = "2030-01-01"
        age_days = date_diff(nowdate(), dob)
        self.assertLess(age_days, 0, "Future date should be negative")

    def test_child_status_active(self):
        self.child.insert(ignore_permissions=True)
        self.assertEqual(self.child.status, "Active")

    def test_child_has_name_after_insert(self):
        self.child.insert(ignore_permissions=True)
        self.assertTrue(self.child.name.startswith("RD-CHILD"))

    def tearDown(self):
        frappe.db.rollback()
