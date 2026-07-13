import frappe
from frappe import _
from frappe.utils import flt


def calculate_paye(annual_gross: float) -> float:
    """Kenya PAYE 2024 KRA progressive bands. Personal relief KES 28,800/year."""
    bands = [
        (288_000,   0.10),
        (100_000,   0.25),
        (5_612_000, 0.30),
    ]
    personal_relief = 28_800.0
    tax = 0.0
    remaining = float(annual_gross)
    for band_size, rate in bands:
        if remaining <= 0:
            break
        taxable = min(remaining, band_size)
        tax += taxable * rate
        remaining -= taxable
    if remaining > 0:
        tax += remaining * 0.35
    return max(0.0, tax - personal_relief)


def monthly_paye(monthly_gross: float) -> float:
    """Monthly PAYE from monthly gross. Annualises, calculates, divides back."""
    return round(calculate_paye(float(monthly_gross) * 12) / 12, 2)


def calculate_nhif(monthly_gross: float) -> float:
    """NHIF fixed-contribution bands 2024."""
    gross = float(monthly_gross)
    bands = [
        (5_999,  150.0),
        (7_999,  300.0),
        (11_999, 400.0),
        (14_999, 500.0),
        (19_999, 600.0),
        (24_999, 750.0),
        (29_999, 850.0),
        (34_999, 900.0),
        (39_999, 950.0),
        (44_999, 1_000.0),
        (49_999, 1_100.0),
        (59_999, 1_200.0),
        (69_999, 1_300.0),
        (79_999, 1_400.0),
        (89_999, 1_500.0),
        (99_999, 1_600.0),
    ]
    for ceiling, contribution in bands:
        if gross <= ceiling:
            return contribution
    return 1_700.0


def calculate_nssf(monthly_gross: float) -> float:
    """NSSF Tier I + II. LEL=6000 UEL=18000 Rate=6%. Employee share only."""
    LEL = 6_000.0
    UEL = 18_000.0
    RATE = 0.06
    gross = float(monthly_gross)
    tier_i  = min(gross, LEL) * RATE
    tier_ii = max(0.0, min(gross, UEL) - LEL) * RATE
    return round(tier_i + tier_ii, 2)


def calculate_housing_levy(monthly_gross: float) -> float:
    """Affordable Housing Levy — employee share, 1.5% of gross salary.
    Matches the rate documented on the 'Housing Levy' Salary Component
    fixture (fixtures/salary_component.json); no ceiling/floor is applied."""
    return round(float(monthly_gross) * 0.015, 2)


STATUTORY_DEDUCTION_CALCULATORS = {
    "PAYE":         monthly_paye,
    "NHIF":         calculate_nhif,
    "NSSF":         calculate_nssf,
    "Housing Levy": calculate_housing_levy,
}


def apply_statutory_deductions(doc, method):
    """Doc event on Salary Slip 'validate' — the actual wiring for Kenya's
    statutory deductions.

    The manual's documented approach (a Salary Structure Deduction row with
    formula "rhema_daycare.hr.payroll.monthly_paye(gross_pay)") cannot work
    under any deployment: HRMS's formula sandbox (_safe_eval's
    whitelisted_globals in salary_slip.py) only exposes a fixed builtin set
    (int/float/round/date/getdate/ceil/floor) with no module-import or
    dotted-attribute access, so rhema_daycare.* is never reachable from a
    formula — confirmed live via NameError: name 'rhema_daycare' is not
    defined.

    This hook is the real fix: it runs after SalarySlip.validate() has
    already called calculate_net_pay() (same point validate_payslip below
    already runs at, and registered before it in hooks.py so its corrected
    totals are what validate_payslip's sanity checks see), overwrites the
    amount on any deduction row whose Salary Component matches one of the
    four statutory components with the value computed from this slip's own
    gross pay, then asks the slip to re-sum its own totals. set_net_pay() is
    a plain re-sum of the already-populated deduction table — unlike
    calculate_net_pay(), it does not re-derive rows from the Salary
    Structure template, so the override survives.

    Rows are only updated if the Salary Structure already includes that
    component (matched by name) — a structure that deliberately omits one
    (e.g. a component below an exemption threshold) is left alone rather
    than having a row force-injected.
    """
    if not doc.get("deductions"):
        return

    changed = False
    for row in doc.deductions:
        calculator = STATUTORY_DEDUCTION_CALCULATORS.get(row.salary_component)
        if not calculator:
            continue
        correct_amount = flt(calculator(flt(doc.gross_pay)), row.precision("amount"))
        if flt(row.amount, row.precision("amount")) != correct_amount:
            row.amount = correct_amount
            row.default_amount = correct_amount
            changed = True

    if changed:
        doc.set_net_pay()


def validate_payslip(doc, method):
    """Frappe doc event on Salary Slip. Blocks negative net and deductions > gross."""
    gross      = flt(doc.gross_pay)
    deductions = flt(doc.total_deduction)
    net        = flt(doc.net_pay)
    if deductions > gross:
        frappe.throw(
            _("Total deductions ({0}) cannot exceed gross pay ({1}).").format(
                deductions, gross),
            frappe.ValidationError)
    if net < 0:
        frappe.throw(
            _("Net salary cannot be negative for {0}.").format(
                doc.employee_name or doc.employee),
            frappe.ValidationError)

