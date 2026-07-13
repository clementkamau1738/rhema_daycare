import frappe
import unittest
from frappe.model.workflow import apply_workflow
from rhema_daycare.portal.permissions import get_portal_child_detail, get_portal_children


class TestWorkflowPrivilegeEscalation(unittest.TestCase):
    """Regression test for the Phase 9 enrollment-workflow audit finding:
    a Teacher must not be able to force a Child Profile from Draft straight
    to Approved/Active by writing workflow_state/status directly, bypassing
    the Approve transition (which only Daycare Manager/System Manager may
    take). Frappe core closes this automatically via validate_workflow()'s
    role-gated transition check, but that's a framework guarantee this app
    depends on — worth a permanent regression test rather than trusting it
    silently forever."""

    def setUp(self):
        frappe.set_user("Administrator")
        self.guardian = self._get_or_create_guardian("Test Guardian - PrivEsc")
        self.teacher_user = self._get_or_create_user(
            "privesc-teacher@example.com", "PrivEsc", "Teacher", ["Teacher"])
        self.manager_user = self._get_or_create_user(
            "privesc-manager@example.com", "PrivEsc", "Manager", ["Daycare Manager"])

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def _get_or_create_guardian(self, name):
        if frappe.db.exists("Customer", name):
            return frappe.get_doc("Customer", name)
        guardian = frappe.new_doc("Customer")
        guardian.customer_name = name
        guardian.customer_type = "Individual"
        guardian.email_id = f"{frappe.scrub(name)}@example.com"
        guardian.insert(ignore_permissions=True)
        frappe.db.commit()
        return guardian

    def _get_or_create_user(self, email, first_name, last_name, roles):
        if frappe.db.exists("User", email):
            return frappe.get_doc("User", email)
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.send_welcome_email = 0
        for role in roles:
            user.append("roles", {"role": role})
        user.insert(ignore_permissions=True)
        frappe.db.commit()
        return user

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
        c = frappe.new_doc("Child Profile")
        c.full_name = full_name
        c.date_of_birth = "2020-01-01"
        c.gender = "Female"
        c.guardian = self.guardian.name
        c.append("emergency_contacts", {
            "contact_name": "Emergency Contact",
            "phone_number": "0712345678",
            "relationship": "Mother"
        })
        c.insert(ignore_permissions=True)
        frappe.db.commit()
        return c

    def test_teacher_cannot_force_approve_via_direct_field_write(self):
        child = self._get_or_create_draft_child("PrivEsc Test Child")

        frappe.set_user(self.teacher_user.name)
        doc = frappe.get_doc("Child Profile", child.name)
        doc.workflow_state = "Approved"
        doc.status = "Active"
        with self.assertRaises(frappe.model.workflow.WorkflowPermissionError):
            doc.save()

        frappe.set_user("Administrator")
        final = frappe.db.get_value(
            "Child Profile", child.name, ["workflow_state", "status"], as_dict=True)
        self.assertEqual(final.workflow_state, "Draft",
            "a blocked bypass attempt must not partially apply")
        self.assertNotEqual(final.status, "Active")

    def test_teacher_can_still_use_legitimate_submit_transition(self):
        # Confirms the block above is workflow-permission-specific, not a
        # side effect of the Teacher role losing write access entirely.
        child = self._get_or_create_draft_child("PrivEsc Legit Test Child")

        frappe.set_user(self.teacher_user.name)
        doc = frappe.get_doc("Child Profile", child.name)
        doc = apply_workflow(doc, "Submit for Approval")
        self.assertEqual(doc.workflow_state, "Pending Approval")
        frappe.db.commit()

    def test_manager_can_also_submit_for_approval(self):
        # Gap fix regression: the manual's own state table lists "Teacher,
        # Manager" as allowed for Draft -> Pending Approval, but the
        # transition originally only granted it to Teacher. A Daycare
        # Manager's only path to move a Draft record forward was Force
        # Approve, which skips review and leaves a permanent bypass-audit
        # entry — a disproportionate tool for a routine action.
        child = self._get_or_create_draft_child("PrivEsc Manager Submit Test Child")

        frappe.set_user(self.manager_user.name)
        doc = frappe.get_doc("Child Profile", child.name)
        doc = apply_workflow(doc, "Submit for Approval")
        self.assertEqual(doc.workflow_state, "Pending Approval")
        frappe.db.commit()


class TestPortalIDOR(unittest.TestCase):
    """Regression test for the Phase 10 parent-portal audit: a guardian must
    never be able to read another family's child (cross-family IDOR via
    name-guessing), an inactive child of their own, or receive
    medical/health fields in any portal response (Kenya Data Protection
    Act 2019 — staff-only data)."""

    def setUp(self):
        frappe.set_user("Administrator")
        self.guardian_a = self._get_or_create_guardian("IDOR Guardian A", "idor-a@example.com")
        self.guardian_b = self._get_or_create_guardian("IDOR Guardian B", "idor-b@example.com")
        self.user_a = self._get_or_create_user("idor-a@example.com")
        self.user_b = self._get_or_create_user("idor-b@example.com")
        self.child_a = self._get_or_create_active_child("IDOR Child A", self.guardian_a.name)
        self.child_b = self._get_or_create_active_child("IDOR Child B", self.guardian_b.name)

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def _get_or_create_guardian(self, name, email):
        existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
        if existing:
            return frappe.get_doc("Customer", existing)
        guardian = frappe.new_doc("Customer")
        guardian.customer_name = name
        guardian.customer_type = "Individual"
        guardian.email_id = email
        guardian.insert(ignore_permissions=True)
        frappe.db.commit()
        return guardian

    def _get_or_create_user(self, email):
        if frappe.db.exists("User", email):
            return frappe.get_doc("User", email)
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = email.split("@")[0]
        user.send_welcome_email = 0
        user.append("roles", {"role": "Customer"})
        user.insert(ignore_permissions=True)
        frappe.db.commit()
        return user

    def _get_or_create_active_child(self, full_name, guardian_name):
        existing = frappe.db.get_value("Child Profile", {
            "full_name": full_name, "guardian": guardian_name
        }, "name")
        if existing:
            child = frappe.get_doc("Child Profile", existing)
            if child.status != "Active":
                child = apply_workflow(child, "Force Approve")
                frappe.db.commit()
            return child
        child = frappe.new_doc("Child Profile")
        child.full_name = full_name
        child.date_of_birth = "2021-01-01"
        child.gender = "Male"
        child.guardian = guardian_name
        child.append("emergency_contacts", {
            "contact_name": "Emergency Contact",
            "phone_number": "0712345678",
            "relationship": "Mother"
        })
        child.insert(ignore_permissions=True)
        frappe.db.commit()
        child = apply_workflow(child, "Force Approve")
        frappe.db.commit()
        return child

    def test_cross_family_child_access_denied(self):
        frappe.set_user(self.user_a.name)
        with self.assertRaises(frappe.PermissionError):
            get_portal_child_detail(self.child_b.name, self.user_a.name)

    def test_child_list_scoped_to_own_family(self):
        frappe.set_user(self.user_a.name)
        names = [c.name for c in get_portal_children(self.user_a.name)]
        self.assertIn(self.child_a.name, names)
        self.assertNotIn(self.child_b.name, names,
            "guardian A's child list must never include guardian B's child")

    def test_inactive_own_child_access_denied(self):
        frappe.set_user("Administrator")
        frappe.db.set_value("Child Profile", self.child_a.name, "status", "Inactive")

        frappe.set_user(self.user_a.name)
        with self.assertRaises(frappe.PermissionError):
            get_portal_child_detail(self.child_a.name, self.user_a.name)

        frappe.set_user("Administrator")
        frappe.db.set_value("Child Profile", self.child_a.name, "status", "Active")

    def test_medical_fields_excluded_from_portal_response(self):
        frappe.set_user("Administrator")
        frappe.db.set_value("Child Profile", self.child_b.name,
            "allergies", "Peanuts — anaphylactic — carries EpiPen")
        frappe.db.set_value("Child Profile", self.child_b.name,
            "medical_conditions", "Mild asthma")

        frappe.set_user(self.user_b.name)
        detail = get_portal_child_detail(self.child_b.name, self.user_b.name)

        for field in ("allergies", "medical_conditions", "immunization_records"):
            self.assertNotIn(field, detail,
                f"portal response leaked staff-only field: {field}")
