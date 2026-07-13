import frappe
import unittest
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate


class TestChildProfile(unittest.TestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        self.guardian = self._get_or_create_guardian("Test Guardian - Child Profile")

    def tearDown(self):
        frappe.db.rollback()

    def _get_or_create_guardian(self, name):
        if frappe.db.exists("Customer", name):
            return frappe.get_doc("Customer", name)
        cust = frappe.new_doc("Customer")
        cust.customer_name = name
        cust.customer_type = "Individual"
        cust.email_id = "guardian@example.com"
        cust.insert(ignore_permissions=True)
        return cust

    def _valid_child(self, full_name="Valid Test Child"):
        c = frappe.new_doc("Child Profile")
        c.full_name = full_name
        c.date_of_birth = "2020-01-01"
        c.gender = "Male"
        c.guardian = self.guardian.name
        c.append("emergency_contacts", {
            "contact_name": "Emergency Contact",
            "phone_number": "0712345678",
            "relationship": "Mother"
        })
        return c

    def test_valid_child_creation_starts_as_draft(self):
        c = self._valid_child()
        c.insert(ignore_permissions=True)
        self.assertTrue(c.name.startswith("RD-CHILD"))
        self.assertEqual(c.workflow_state, "Draft")
        self.assertNotEqual(c.status, "Active",
            "a freshly created child must not silently start Active")

    def test_missing_guardian_is_blocked(self):
        c = self._valid_child()
        c.guardian = None
        with self.assertRaises(frappe.ValidationError):
            c.insert(ignore_permissions=True)

    def test_missing_emergency_contact_is_blocked(self):
        c = self._valid_child()
        c.emergency_contacts = []
        with self.assertRaises(frappe.ValidationError):
            c.insert(ignore_permissions=True)

    def test_future_dob_is_blocked(self):
        c = self._valid_child()
        c.date_of_birth = add_days(nowdate(), 30)
        with self.assertRaises(frappe.ValidationError):
            c.insert(ignore_permissions=True)

    def test_duplicate_child_is_blocked(self):
        c1 = self._valid_child("Duplicate Test Child")
        c1.insert(ignore_permissions=True)

        c2 = self._valid_child("Duplicate Test Child")
        with self.assertRaises(frappe.DuplicateEntryError):
            c2.insert(ignore_permissions=True)

    def test_status_active_without_approval_is_blocked(self):
        c = self._valid_child()
        c.status = "Active"
        with self.assertRaises(frappe.PermissionError):
            c.insert(ignore_permissions=True)

    def _get_or_create_draft_child(self, full_name):
        existing = frappe.db.get_value("Child Profile", {
            "full_name": full_name, "guardian": self.guardian.name
        }, "name")
        if existing:
            c = frappe.get_doc("Child Profile", existing)
            if c.workflow_state != "Draft" or c.status == "Active":
                frappe.db.delete("Child Profile", {"name": existing})
                frappe.db.commit()
            else:
                return c
        c = self._valid_child(full_name)
        c.insert(ignore_permissions=True)
        frappe.db.commit()
        return c

    def test_approval_workflow_activates_child(self):
        c = self._get_or_create_draft_child("Workflow Test Child")

        c = apply_workflow(c, "Submit for Approval")
        self.assertEqual(c.workflow_state, "Pending Approval")
        self.assertNotEqual(c.status, "Active")

        c = apply_workflow(c, "Approve")
        self.assertEqual(c.workflow_state, "Approved")
        self.assertEqual(c.status, "Active",
            "approval must automatically activate the child")
        frappe.db.commit()

    def test_force_approve_from_draft(self):
        c = self._get_or_create_draft_child("Force Approve Test Child")

        c = apply_workflow(c, "Force Approve")
        self.assertEqual(c.workflow_state, "Approved")
        self.assertEqual(c.status, "Active")

        actions = frappe.get_all("Workflow Action",
            filters={"reference_name": c.name})
        self.assertTrue(actions, "force approve must leave an audit trail entry")
        frappe.db.commit()
