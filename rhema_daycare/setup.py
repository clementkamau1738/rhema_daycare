import frappe


def install_custom_fields():
    """
    after_migrate hook — installs all custom fields on standard ERPNext DocTypes.
    Safe to run multiple times (checks before creating).
    """
    _setup_sales_invoice_fields()
    _setup_employee_fields()
    _setup_customer_fields()
    _setup_attendance_log_fields()
    _ensure_attendance_index()
    _ensure_invoice_index()
    _setup_role_permissions()
    frappe.db.commit()


def _setup_role_permissions():
    """
    Grant 'Daycare Manager' access to the standard ERPNext/HRMS doctypes the
    manual describes as "Full access" for that role, via Custom DocPerm
    (the app doesn't own these doctypes, so their own JSON can't be edited).
    Safe to run multiple times.
    """
    from frappe.permissions import add_permission, update_permission_property

    grants = {
        "Sales Invoice": ["read", "write", "create", "submit", "cancel", "print", "email"],
        "Payroll Entry": ["read", "write", "create", "submit", "cancel"],
        "Salary Slip": ["read", "write", "create", "submit", "cancel", "print", "email"],
        "Salary Structure Assignment": ["read", "write", "create", "submit", "cancel"],
    }
    for doctype, ptypes in grants.items():
        already_exists = frappe.db.get_value(
            "Custom DocPerm",
            {"parent": doctype, "role": "Daycare Manager", "permlevel": 0, "if_owner": 0},
        )
        if already_exists:
            continue
        add_permission(doctype, "Daycare Manager", permlevel=0, ptype=ptypes[0])
        for ptype in ptypes[1:]:
            update_permission_property(doctype, "Daycare Manager", 0, ptype, value=1)


def _setup_sales_invoice_fields():
    existing = {
        f.fieldname
        for f in frappe.get_doc("DocType", "Sales Invoice").fields
    }
    if "rhema_child" in existing:
        return
    if frappe.db.exists("Custom Field", "Sales Invoice-rhema_child"):
        return
    frappe.get_doc({
        "doctype":      "Custom Field",
        "dt":           "Sales Invoice",
        "fieldname":    "rhema_child",
        "fieldtype":    "Link",
        "options":      "Child Profile",
        "label":        "Child",
        "read_only":    1,
        "search_index": 1,
        "insert_after": "customer"
    }).insert(ignore_permissions=True)


def _setup_employee_fields():
    existing = {
        f.fieldname
        for f in frappe.get_doc("DocType", "Employee").fields
    }
    fields = [
        {
            "fieldname":   "rhema_section",
            "fieldtype":   "Section Break",
            "label":       "Rhema Daycare",
            "insert_after": "health_insurance_no"
        },
        {
            "fieldname":   "cpr_certified",
            "fieldtype":   "Check",
            "label":       "CPR Certified",
            "insert_after": "rhema_section"
        },
        {
            "fieldname":   "cpr_expiry_date",
            "fieldtype":   "Date",
            "label":       "CPR Expiry Date",
            "insert_after": "cpr_certified"
        },
        {
            "fieldname":   "first_aid_certified",
            "fieldtype":   "Check",
            "label":       "First Aid Certified",
            "insert_after": "cpr_expiry_date"
        },
        {
            "fieldname":   "background_check_status",
            "fieldtype":   "Select",
            "label":       "Background Check Status",
            "options":     "\nPending\nCleared\nFailed",
            "default":     "Pending",
            "insert_after": "first_aid_certified"
        },
        {
            "fieldname":   "background_check_date",
            "fieldtype":   "Date",
            "label":       "Background Check Date",
            "insert_after": "background_check_status"
        },
        {
            "fieldname":   "assigned_classroom",
            "fieldtype":   "Link",
            "options":     "Classroom",
            "label":       "Assigned Classroom",
            "insert_after": "background_check_date"
        },
    ]
    for f in fields:
        if f["fieldname"] in existing:
            continue
        name = f"Employee-{f['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            continue
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt":      "Employee",
            **f
        }).insert(ignore_permissions=True)


def _setup_customer_fields():
    existing = {
        f.fieldname
        for f in frappe.get_doc("DocType", "Customer").fields
    }
    fields = [
        {
            "fieldname":   "portal_section",
            "fieldtype":   "Section Break",
            "label":       "Parent Portal",
            "insert_after": "website"
        },
        {
            "fieldname":   "portal_access_enabled",
            "fieldtype":   "Check",
            "label":       "Portal Access Enabled",
            "default":     "0",
            "insert_after": "portal_section"
        },
        {
            "fieldname":   "communication_preference",
            "fieldtype":   "Select",
            "label":       "Communication Preference",
            "options":     "Email\nSMS\nBoth",
            "default":     "Email",
            "insert_after": "portal_access_enabled"
        },
        {
            "fieldname":   "guardian_mobile_no",
            "fieldtype":   "Data",
            "options":     "Phone",
            "label":       "Guardian Mobile No (for SMS)",
            "insert_after": "communication_preference"
        },
        {
            "fieldname":   "relationship_to_child",
            "fieldtype":   "Select",
            "label":       "Relationship to Child",
            "options":     "\nMother\nFather\nGrandparent\nGuardian\nOther",
            "insert_after": "guardian_mobile_no"
        },
        {
            "fieldname":   "authorized_pickup_persons",
            "fieldtype":   "Table",
            "label":       "Authorized Pickup Persons",
            "options":     "Authorized Pickup Person",
            "insert_after": "relationship_to_child"
        },
    ]
    for f in fields:
        if f["fieldname"] in existing:
            continue
        name = f"Customer-{f['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            continue
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt":      "Customer",
            **f
        }).insert(ignore_permissions=True)


def _setup_attendance_log_fields():
    # Get fieldnames already on the DocType (built-in or previously added)
    existing = {
        f.fieldname
        for f in frappe.get_doc("DocType", "Child Attendance Log").fields
    }

    fields = [
        {
            "fieldname":   "checked_in_by",
            "fieldtype":   "Link",
            "options":     "User",
            "label":       "Checked In By",
            "read_only":   1,
            "insert_after": "status"
        },
        {
            "fieldname":   "checked_out_by",
            "fieldtype":   "Link",
            "options":     "User",
            "label":       "Checked Out By",
            "read_only":   1,
            "insert_after": "checked_in_by"
        },
        {
            "fieldname":   "late_fee_charged",
            "fieldtype":   "Check",
            "label":       "Late Fee Charged",
            "default":     "0",
            "read_only":   1,
            "insert_after": "checked_out_by"
        },
        {
            "fieldname":   "late_alert_sent",
            "fieldtype":   "Check",
            "label":       "Late Alert Sent",
            "default":     "0",
            "read_only":   1,
            "insert_after": "late_fee_charged"
        },
    ]
    for f in fields:
        # Skip if already on the DocType OR already a Custom Field
        if f["fieldname"] in existing:
            continue
        name = f"Child Attendance Log-{f['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            continue
        frappe.get_doc({
            "doctype": "Custom Field",
            "dt":      "Child Attendance Log",
            **f
        }).insert(ignore_permissions=True)


def _ensure_attendance_index():
    # sql_ddl commits first, then runs — CREATE INDEX autocommits in MariaDB
    # and would otherwise trip frappe's implicit-commit guard mid-transaction.
    frappe.db.sql_ddl("""
        CREATE INDEX IF NOT EXISTS idx_att_child_checkin
        ON `tabChild Attendance Log` (child, check_in)
    """)


def _ensure_invoice_index():
    frappe.db.sql_ddl("""
        CREATE INDEX IF NOT EXISTS idx_inv_rhema_child_date
        ON `tabSales Invoice` (rhema_child, posting_date)
    """)

