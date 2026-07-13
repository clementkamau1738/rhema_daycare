import frappe
import unittest
from frappe.model.workflow import apply_workflow
from rhema_daycare.rhema_daycare.report.child_attendance_summary import child_attendance_summary


class TestChildAttendanceSummary(unittest.TestCase):
    """Regression test for the Phase 12 audit finding: the manual promises a
    'Child Attendance Summary' report showing attendance percentage for a
    period, which no existing report computed. Confirms the new report
    actually derives a correct percentage from real attendance logs."""

    def setUp(self):
        frappe.set_user("Administrator")
        self.guardian = self._get_or_create_guardian("Test Guardian - Report")
        self.child = self._get_or_create_active_child("Report Test Child", self.guardian.name)
        frappe.db.delete("Child Attendance Log", {"child": self.child.name})
        frappe.db.commit()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Child Attendance Log", {"child": self.child.name})
        frappe.db.commit()

    def _get_or_create_guardian(self, name):
        existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
        if existing:
            return frappe.get_doc("Customer", existing)
        guardian = frappe.new_doc("Customer")
        guardian.customer_name = name
        guardian.customer_type = "Individual"
        guardian.email_id = f"{frappe.scrub(name)}@example.com"
        guardian.insert(ignore_permissions=True)
        frappe.db.commit()
        return guardian

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

    def _log_checkin(self, when):
        log = frappe.new_doc("Child Attendance Log")
        log.child = self.child.name
        log.check_in = when
        log.status = "Present"
        log.insert(ignore_permissions=True)
        log.reload()  # evaluate_late_pickup's on_update hook may touch the row
        log.submit()
        return log

    def test_attendance_percentage_reflects_real_logs(self):
        today = frappe.utils.today()
        self._log_checkin(f"{today} 08:00:00")

        cols, data = child_attendance_summary.execute({"from_date": today, "to_date": today})
        row = next(r for r in data if r["child_name"] == "Report Test Child")

        self.assertEqual(row["days_present"], 1)
        self.assertEqual(row["days_operated"], 1)
        self.assertEqual(row["attendance_pct"], 100.0)

    def test_no_attendance_in_period_yields_zero_percent_not_error(self):
        far_past = "2020-01-01"
        cols, data = child_attendance_summary.execute({"from_date": far_past, "to_date": far_past})
        row = next(r for r in data if r["child_name"] == "Report Test Child")
        self.assertEqual(row["days_operated"], 0)
        self.assertEqual(row["attendance_pct"], 0)
