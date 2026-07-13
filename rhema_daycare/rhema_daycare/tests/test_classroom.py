import frappe
import unittest
from frappe.model.workflow import apply_workflow


class TestClassroom(unittest.TestCase):

    def setUp(self):
        frappe.set_user("Administrator")
        employees = frappe.get_all("Employee", limit=1, pluck="name")
        if not employees:
            self.skipTest("No Employee record available in this site to use as a teacher")
        self.teacher = employees[0]

    def tearDown(self):
        frappe.db.rollback()

    def _get_or_create_classroom(self, name, capacity=10, with_teacher=True):
        existing = frappe.db.get_value("Classroom", {"classroom_name": name}, "name")
        if existing:
            c = frappe.get_doc("Classroom", existing)
            if with_teacher and not c.assigned_teachers:
                c.append("assigned_teachers", {"teacher": self.teacher})
                c.save(ignore_permissions=True)
                frappe.db.commit()
            return c
        c = frappe.new_doc("Classroom")
        c.classroom_name = name
        c.capacity_limit = capacity
        c.monthly_fee = 5000
        c.age_group = "Toddler"
        if with_teacher:
            c.append("assigned_teachers", {"teacher": self.teacher})
        c.insert(ignore_permissions=True)
        frappe.db.commit()
        return c

    def _get_or_create_guardian(self, name):
        if frappe.db.exists("Customer", name):
            return frappe.get_doc("Customer", name)
        guardian = frappe.new_doc("Customer")
        guardian.customer_name = name
        guardian.customer_type = "Individual"
        guardian.email_id = f"{frappe.scrub(name)}@example.com"
        guardian.insert(ignore_permissions=True)
        return guardian

    def _get_or_create_active_child(self, full_name, guardian_name, classroom_name):
        existing = frappe.db.get_value("Child Profile", {
            "full_name": full_name, "guardian": guardian_name
        }, "name")
        if existing:
            child = frappe.get_doc("Child Profile", existing)
            if child.assigned_classroom != classroom_name:
                child.assigned_classroom = classroom_name
                child.save(ignore_permissions=True)
                frappe.db.commit()
            if child.status != "Active":
                child = apply_workflow(child, "Force Approve")
                frappe.db.commit()
            return child

        child = frappe.new_doc("Child Profile")
        child.full_name = full_name
        child.date_of_birth = "2020-01-01"
        child.gender = "Male"
        child.guardian = guardian_name
        child.assigned_classroom = classroom_name
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

    def test_valid_classroom_creation(self):
        c = self._get_or_create_classroom("Test Classroom A")
        self.assertTrue(c.name.startswith("RD-Class"))
        self.assertEqual(c.capacity_limit, 10)
        self.assertEqual(c.monthly_fee, 5000)

    def test_removing_all_teachers_with_active_child_warns_but_does_not_block(self):
        # Manual: "generates compliance warning" (non-blocking) — not a hard stop.
        classroom = self._get_or_create_classroom("Test Classroom B")
        guardian = self._get_or_create_guardian("Test Guardian - Classroom")
        child = self._get_or_create_active_child(
            "Classroom Ratio Test Child", guardian.name, classroom.name)
        self.assertEqual(child.status, "Active")

        classroom.reload()
        classroom.assigned_teachers = []
        frappe.clear_messages()
        classroom.save(ignore_permissions=True)  # should not raise
        self.assertTrue(
            any("no assigned teacher" in (m.get("message") or "") for m in frappe.message_log),
            "expected a compliance warning to be surfaced")

    def test_classroom_full_blocks_further_enrollment(self):
        classroom = self._get_or_create_classroom("Test Classroom C", capacity=1)
        guardian = self._get_or_create_guardian("Test Guardian - Classroom Full")
        self._get_or_create_active_child(
            "Full Classroom Child 1", guardian.name, classroom.name)

        second_name = "Full Classroom Child 2"
        existing = frappe.db.get_value("Child Profile", {
            "full_name": second_name, "guardian": guardian.name
        }, "name")
        if existing:
            frappe.db.delete("Child Profile", {"name": existing})
            frappe.db.commit()

        second = frappe.new_doc("Child Profile")
        second.full_name = second_name
        second.date_of_birth = "2020-01-01"
        second.gender = "Female"
        second.guardian = guardian.name
        second.assigned_classroom = classroom.name
        second.append("emergency_contacts", {
            "contact_name": "Emergency Contact",
            "phone_number": "0712345678",
            "relationship": "Mother"
        })
        with self.assertRaises(frappe.ValidationError):
            second.insert(ignore_permissions=True)

    def test_overlapping_daily_schedule_is_blocked(self):
        c = self._get_or_create_classroom("Test Classroom D — Schedule")
        c.set("daily_schedule", [])
        c.append("daily_schedule", {
            "day": "Monday", "activity": "Morning circle",
            "start_time": "08:00:00", "end_time": "08:30:00"})
        c.append("daily_schedule", {
            "day": "Monday", "activity": "Learning play",
            "start_time": "08:15:00", "end_time": "09:00:00"})
        with self.assertRaises(frappe.ValidationError):
            c.save(ignore_permissions=True)

    def test_non_overlapping_daily_schedule_succeeds(self):
        c = self._get_or_create_classroom("Test Classroom E — Schedule OK")
        c.set("daily_schedule", [])
        c.append("daily_schedule", {
            "day": "Monday", "activity": "Morning circle",
            "start_time": "08:00:00", "end_time": "08:30:00"})
        c.append("daily_schedule", {
            "day": "Monday", "activity": "Learning play",
            "start_time": "08:30:00", "end_time": "10:00:00"})
        c.save(ignore_permissions=True)  # should not raise
        self.assertEqual(len(c.daily_schedule), 2)

    def test_capacity_reduction_below_enrollment_is_blocked(self):
        classroom = self._get_or_create_classroom("Test Classroom F — Capacity", capacity=5)
        guardian = self._get_or_create_guardian("Test Guardian - Capacity Reduction")
        self._get_or_create_active_child(
            "Capacity Reduction Test Child", guardian.name, classroom.name)

        classroom.reload()
        classroom.capacity_limit = 0
        with self.assertRaises(frappe.ValidationError):
            classroom.save(ignore_permissions=True)
