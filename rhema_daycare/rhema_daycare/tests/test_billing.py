import frappe
import unittest
from frappe.model.workflow import apply_workflow
from frappe.utils import get_first_day, get_last_day, today
from rhema_daycare.billing import invoicing


class TestInvoiceIdempotency(unittest.TestCase):
    """Regression test for the P0 fix verified live earlier this cycle:
    _create_invoice() must create exactly one invoice per child per period,
    even across repeated/concurrent calls, via the FOR UPDATE row lock
    ahead of the duplicate-invoice check."""

    COMPANY = "Rhema Daycare"

    def setUp(self):
        frappe.set_user("Administrator")
        employees = frappe.get_all("Employee", limit=1, pluck="name")
        if not employees:
            self.skipTest("No Employee record available in this site to use as a teacher")
        self.teacher = employees[0]
        self.guardian = self._get_or_create_guardian("Test Guardian - Billing")
        self.classroom = self._get_or_create_classroom("Test Billing Classroom", monthly_fee=5000)
        self.child = self._get_or_create_active_child(
            "Billing Test Child", self.guardian.name, self.classroom.name)
        self.tuition_item = self._get_or_create_item("Test Tuition Fee")
        self._cleanup_this_period_invoices()

    def tearDown(self):
        frappe.set_user("Administrator")
        self._cleanup_this_period_invoices()
        frappe.db.rollback()

    def _cleanup_this_period_invoices(self):
        names = frappe.get_all("Sales Invoice", filters={
            "customer": self.guardian.name, "rhema_child": self.child.name,
        }, pluck="name")
        for name in names:
            doc = frappe.get_doc("Sales Invoice", name)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("Sales Invoice", name, force=True, ignore_permissions=True)
        if names:
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

    def _get_or_create_classroom(self, name, monthly_fee):
        existing = frappe.db.get_value("Classroom", {"classroom_name": name}, "name")
        if existing:
            c = frappe.get_doc("Classroom", existing)
            if not c.assigned_teachers:
                c.append("assigned_teachers", {"teacher": self.teacher})
                c.save(ignore_permissions=True)
                frappe.db.commit()
            return c
        c = frappe.new_doc("Classroom")
        c.classroom_name = name
        c.capacity_limit = 10
        c.monthly_fee = monthly_fee
        c.age_group = "Toddler"
        c.append("assigned_teachers", {"teacher": self.teacher})
        c.insert(ignore_permissions=True)
        frappe.db.commit()
        return c

    def _get_or_create_active_child(self, full_name, guardian_name, classroom_name):
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

    def _get_or_create_item(self, name):
        if frappe.db.exists("Item", name):
            return name
        item = frappe.new_doc("Item")
        item.item_code = name
        item.item_name = name
        item.item_group = "Services" if frappe.db.exists("Item Group", "Services") else "All Item Groups"
        item.is_stock_item = 0
        item.insert(ignore_permissions=True)
        frappe.db.commit()
        return item.name

    def test_first_call_creates_second_call_skips(self):
        period_start = get_first_day(today())
        period_end = get_last_day(today())
        classrooms = {self.classroom.name: {"name": self.classroom.name, "monthly_fee": 5000}}
        child_dict = {
            "name": self.child.name, "full_name": self.child.full_name,
            "guardian": self.guardian.name, "assigned_classroom": self.classroom.name,
        }

        first = invoicing._create_invoice(
            child_dict, period_start, period_end, classrooms, self.tuition_item, self.COMPANY)
        self.assertEqual(first, "created")

        second = invoicing._create_invoice(
            child_dict, period_start, period_end, classrooms, self.tuition_item, self.COMPANY)
        self.assertEqual(second, "skipped",
            "a second call for the same child/period must not create a duplicate invoice")

        count = frappe.db.count("Sales Invoice", {
            "customer": self.guardian.name, "rhema_child": self.child.name,
            "posting_date": ["between", [period_start, period_end]],
        })
        self.assertEqual(count, 1)

    def test_no_guardian_is_skipped(self):
        child_dict = {"name": self.child.name, "full_name": "No Guardian Child", "guardian": None}
        result = invoicing._create_invoice(
            child_dict, get_first_day(today()), get_last_day(today()),
            {}, self.tuition_item, self.COMPANY)
        self.assertEqual(result, "skipped")

    def test_classroom_without_monthly_fee_is_skipped(self):
        classrooms = {self.classroom.name: {"name": self.classroom.name, "monthly_fee": 0}}
        child_dict = {
            "name": self.child.name, "full_name": self.child.full_name,
            "guardian": self.guardian.name, "assigned_classroom": self.classroom.name,
        }
        result = invoicing._create_invoice(
            child_dict, get_first_day(today()), get_last_day(today()),
            classrooms, self.tuition_item, self.COMPANY)
        self.assertEqual(result, "skipped")


class TestLateFeeCalculation(unittest.TestCase):
    """Pure-function checks for _calculate_fee against the manual's own
    defaults: grace period 10 min, KES 200/hour, max KES 2,000/day."""

    def _settings(self, grace=10, rate=200, minimum=0, maximum=2000):
        return {
            "grace_period_minutes": grace,
            "late_fee_per_hour": rate,
            "late_pickup_minimum_fee": minimum,
            "late_pickup_maximum_fee": maximum,
        }

    def test_within_grace_period_is_free(self):
        # 8 minutes late, 10 minute grace -> no charge
        fee = invoicing._calculate_fee(8 / 60, self._settings())
        self.assertEqual(fee, 0.0)

    def test_one_hour_past_grace_charges_one_hour(self):
        # 10 min grace + 60 min billable = 70 minutes late total
        fee = invoicing._calculate_fee(70 / 60, self._settings())
        self.assertEqual(fee, 200.0)

    def test_fee_caps_at_daily_maximum(self):
        # 20 hours late would be 4,000 at KES200/hr; capped at 2,000
        fee = invoicing._calculate_fee(20, self._settings())
        self.assertEqual(fee, 2000.0)
