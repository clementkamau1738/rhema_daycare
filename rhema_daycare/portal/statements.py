import frappe
from frappe import _
from frappe.utils.pdf import get_pdf

STATEMENT_TEMPLATE = """
<div style="font-family: sans-serif;">
  {{ letter_head_content|safe if letter_head_content }}
  <h2>Statement — {{ year }}</h2>
  <p>Guardian: <strong>{{ guardian_name }}</strong></p>
  <table style="width:100%; border-collapse: collapse; margin-top: 16px;">
    <thead>
      <tr style="border-bottom: 2px solid #333; text-align:left;">
        <th style="padding:6px;">Invoice</th>
        <th style="padding:6px;">Posting Date</th>
        <th style="padding:6px;">Due Date</th>
        <th style="padding:6px;">Status</th>
        <th style="padding:6px; text-align:right;">Amount (KES)</th>
        <th style="padding:6px; text-align:right;">Outstanding (KES)</th>
      </tr>
    </thead>
    <tbody>
      {% for inv in invoices %}
      <tr style="border-bottom: 1px solid #ddd;">
        <td style="padding:6px;">{{ inv.name }}</td>
        <td style="padding:6px;">{{ inv.posting_date }}</td>
        <td style="padding:6px;">{{ inv.due_date }}</td>
        <td style="padding:6px;">{{ inv.status }}</td>
        <td style="padding:6px; text-align:right;">{{ "%.2f"|format(inv.grand_total or 0) }}</td>
        <td style="padding:6px; text-align:right;">{{ "%.2f"|format(inv.outstanding_amount or 0) }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <p style="margin-top: 16px;">
    <strong>Total billed:</strong> KES {{ "%.2f"|format(total_billed) }}<br>
    <strong>Total outstanding:</strong> KES {{ "%.2f"|format(total_outstanding) }}
  </p>
</div>
"""


@frappe.whitelist()
def download_statement(year=None):
    """Portal endpoint: PDF of the logged-in guardian's invoices/payments for
    the given (or current) year, using the Company's Letter Head if set."""
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required."), frappe.PermissionError)

    guardian_name = frappe.db.get_value(
        "Customer", {"email_id": frappe.session.user}, "name")
    if not guardian_name:
        frappe.throw(_("Your account is not linked to a guardian record."), frappe.PermissionError)

    year = year or frappe.utils.nowdate()[:4]
    invoices = frappe.get_all(
        "Sales Invoice",
        filters={
            "customer": guardian_name,
            "docstatus": 1,
            "posting_date": ["between", [f"{year}-01-01", f"{year}-12-31"]],
        },
        fields=["name", "posting_date", "due_date", "grand_total",
                "outstanding_amount", "status"],
        order_by="posting_date asc"
    )
    guardian = frappe.db.get_value(
        "Customer", guardian_name, ["customer_name"], as_dict=True)
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    letter_head = frappe.db.get_value("Company", company, "default_letter_head") if company else None
    letter_head_content = ""
    if letter_head:
        letter_head_content = frappe.db.get_value("Letter Head", letter_head, "content") or ""

    html = frappe.render_template(STATEMENT_TEMPLATE, {
        "guardian_name": guardian.customer_name if guardian else guardian_name,
        "year": year,
        "invoices": invoices,
        "letter_head_content": letter_head_content,
        "total_billed": sum(i.grand_total or 0 for i in invoices),
        "total_outstanding": sum(i.outstanding_amount or 0 for i in invoices),
    }, is_path=False)

    frappe.local.response.filename = f"Statement-{guardian_name}-{year}.pdf"
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "pdf"
