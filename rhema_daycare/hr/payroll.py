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

