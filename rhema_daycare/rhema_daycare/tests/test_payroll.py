import frappe
import unittest
from rhema_daycare.hr.payroll import (
    calculate_paye, monthly_paye, calculate_nhif, calculate_nssf,
    calculate_housing_levy,
)


class TestStatutoryCalculators(unittest.TestCase):
    """Pure-function checks against the Kenya 2024 KRA/NHIF/NSSF/Housing
    Levy rates. KES 49,500 is the manual's own Module 5 worked example
    gross figure — its stated PAYE/NSSF match these calculators exactly;
    its stated NHIF (1,000) does not (see test_nhif_49500_matches_real_band_not_manual)."""

    def test_paye_bands_match_manual_table(self):
        # 0-288,000 @10%; 288,001-388,000 @25%; 388,001-6,000,000 @30%; above @35%
        # Personal relief KES 28,800/year (KES 2,400/month per the manual).
        self.assertAlmostEqual(calculate_paye(0), 0.0, places=2)
        self.assertAlmostEqual(calculate_paye(288_000), 0.0, places=2)  # 28,800 tax - 28,800 relief
        self.assertAlmostEqual(calculate_paye(388_000), 25_000 + 28_800 - 28_800, places=2)
        # Just above the third band ceiling: verify the 35% top band applies
        over_top = calculate_paye(6_100_000)
        under_top = calculate_paye(6_000_000)
        self.assertAlmostEqual(over_top - under_top, 100_000 * 0.35, places=2)

    def test_monthly_paye_for_manual_worked_example(self):
        # Manual: gross 49,500/month -> PAYE ~KES 7,233
        self.assertAlmostEqual(monthly_paye(49_500), 7_233.33, places=2)

    def test_nssf_tier_i_and_ii_match_manual_exactly(self):
        # Manual: Tier I 6% of first 6,000 = 360; Tier II 6% of 6,001-18,000 = 720; total 1,080
        self.assertEqual(calculate_nssf(49_500), 1_080.0)
        self.assertEqual(calculate_nssf(6_000), 360.0)
        self.assertEqual(calculate_nssf(3_000), 180.0, "below LEL: 6% of actual gross only")

    def test_nhif_49500_matches_real_band_not_manual(self):
        # Real 2024 NHIF band table places 49,500 in the 45,000-49,999
        # bracket -> KES 1,100. The manual's own worked example states
        # KES 1,000 (the 40,000-44,999 bracket's rate) for this same gross
        # figure — a documentation error in the manual, not this code; see
        # the audit's Phase 8 finding. This test locks in the *correct*
        # value so a future "fix" doesn't regress it to match the manual's
        # wrong number.
        self.assertEqual(calculate_nhif(49_500), 1_100.0)
        self.assertEqual(calculate_nhif(44_999), 1_000.0)
        self.assertEqual(calculate_nhif(5_999), 150.0)
        self.assertEqual(calculate_nhif(100_000), 1_700.0)

    def test_housing_levy_is_1_5_percent_of_gross(self):
        self.assertEqual(calculate_housing_levy(49_500), 742.5)


class TestStatutoryDeductionWiring(unittest.TestCase):
    """Integration test for apply_statutory_deductions: confirms the doc-event
    hook (registered on Salary Slip 'validate' in hooks.py, ahead of
    validate_payslip) actually overwrites deduction rows on a real Salary
    Slip with correct amounts, and that the slip's totals are re-summed
    correctly afterwards. This is the P0 fix verified live earlier and
    committed here so a future change to hooks.py ordering or
    calculate_net_pay()'s internals can't silently break it again."""

    COMPANY = "Rhema Daycare"

    def setUp(self):
        frappe.set_user("Administrator")
        self.employee = self._get_or_create_employee()
        self.structure = self._get_or_create_salary_structure()
        self._get_or_create_assignment()

    def tearDown(self):
        frappe.set_user("Administrator")
        frappe.db.rollback()

    def _get_or_create_employee(self):
        full_name = "Test Payroll Teacher"
        existing = frappe.db.get_value("Employee", {"employee_name": full_name}, "name")
        if existing:
            return frappe.get_doc("Employee", existing)
        emp = frappe.new_doc("Employee")
        emp.employee_name = full_name
        emp.first_name = "Test Payroll"
        emp.gender = "Female"
        emp.date_of_birth = "1990-01-01"
        emp.date_of_joining = "2025-01-01"
        emp.company = self.COMPANY
        emp.holiday_list = "_Test Holiday List"
        emp.insert(ignore_permissions=True)
        frappe.db.commit()
        return emp

    def _get_or_create_salary_structure(self):
        name = "Test Payroll Structure"
        if frappe.db.exists("Salary Structure", name):
            return frappe.get_doc("Salary Structure", name)
        ss = frappe.new_doc("Salary Structure")
        ss.name = name
        ss.company = self.COMPANY
        ss.payroll_frequency = "Monthly"
        ss.append("earnings", {
            "salary_component": "Basic Salary", "amount": 49_500, "amount_based_on_formula": 0,
        })
        for component in ("PAYE", "NHIF", "NSSF", "Housing Levy"):
            ss.append("deductions", {
                "salary_component": component, "amount": 0, "amount_based_on_formula": 0,
            })
        ss.insert(ignore_permissions=True)
        ss.submit()
        frappe.db.commit()
        return ss

    def _get_or_create_assignment(self):
        existing = frappe.db.get_value("Salary Structure Assignment", {
            "employee": self.employee.name, "salary_structure": self.structure.name,
            "docstatus": 1,
        }, "name")
        if existing:
            return frappe.get_doc("Salary Structure Assignment", existing)
        sa = frappe.new_doc("Salary Structure Assignment")
        sa.employee = self.employee.name
        sa.salary_structure = self.structure.name
        sa.company = self.COMPANY
        sa.from_date = "2025-01-01"
        sa.base = 49_500
        sa.insert(ignore_permissions=True)
        sa.submit()
        frappe.db.commit()
        return sa

    def test_salary_slip_gets_correct_statutory_deductions(self):
        slip = frappe.new_doc("Salary Slip")
        slip.employee = self.employee.name
        slip.company = self.COMPANY
        slip.start_date = "2026-07-01"
        slip.end_date = "2026-07-31"
        slip.posting_date = "2026-07-15"
        slip.insert(ignore_permissions=True)

        amounts = {row.salary_component: row.amount for row in slip.deductions}
        self.assertAlmostEqual(amounts["PAYE"], 7_233.33, places=2)
        self.assertEqual(amounts["NHIF"], 1_100.0)
        self.assertEqual(amounts["NSSF"], 1_080.0)
        self.assertEqual(amounts["Housing Levy"], 742.5)

        expected_total_deduction = round(7_233.33 + 1_100.0 + 1_080.0 + 742.5, 2)
        self.assertAlmostEqual(slip.total_deduction, expected_total_deduction, places=2)
        self.assertAlmostEqual(slip.net_pay, 49_500 - expected_total_deduction, places=2)

        slip.submit()
        frappe.db.commit()
        self.assertEqual(slip.docstatus, 1)
