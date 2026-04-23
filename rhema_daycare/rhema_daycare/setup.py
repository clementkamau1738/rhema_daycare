import frappe


def add_custom_fields():
    """
    Adds custom fields to the Employee DocType.
    Called automatically after every bench migrate.
    """
    custom_fields = {
        "Employee": [
            {
                "fieldname": "cpr_certified",
                "fieldtype": "Check",
                "label": "CPR Certified",
                "insert_after": "department"
            },
            {
                "fieldname": "first_aid_certified",
                "fieldtype": "Check",
                "label": "First Aid Certified",
                "insert_after": "cpr_certified"
            },
            {
                "fieldname": "background_check_status",
                "fieldtype": "Select",
                "options": "Pending\nCleared\nFailed",
                "label": "Background Check Status",
                "insert_after": "first_aid_certified"
            },
            {
                "fieldname": "assigned_classroom",
                "fieldtype": "Link",
                "options": "Classroom",
                "label": "Assigned Classroom",
                "insert_after": "background_check_status"
            },
            {
                "fieldname": "training_records",
                "fieldtype": "Table",
                "options": "Employee Training Record",
                "label": "Training Records",
                "insert_after": "assigned_classroom"
            }
        ]
    }

    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
    create_custom_fields(custom_fields)
    frappe.db.commit()
    print("Custom fields added to Employee DocType.")


def setup_kenya_defaults():
    """Set Kenya as default country and currency"""

    frappe.db.set_value("System Settings", "System Settings", "country", "Kenya")
    frappe.db.set_value("System Settings", "System Settings", "default_currency", "KES")
    frappe.db.commit()
    print("Kenya defaults configured!")


def setup_tax_templates():
    """Create Kenya standard tax template"""

    if frappe.db.exists("Sales Taxes and Charges Template", "Kenya Standard Tax"):
        print("Tax template already exists!")
        return

    tax = frappe.new_doc("Sales Taxes and Charges Template")
    tax.title = "Kenya Standard Tax"
    tax.company = frappe.db.get_single_value("Global Defaults", "default_company")
    tax.is_default = 1

    tax.append("taxes", {
        "charge_type": "On Net Total",
        "account_head": "VAT - " + frappe.db.get_single_value("Global Defaults", "default_company"),
        "description": "VAT 16%",
        "rate": 16
    })

    tax.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Kenya tax template created!")
