app_name = "rhema_daycare"
app_title = "Rhema Daycare"
app_publisher = "clement"
app_description = "Rhema Daycare management system"
app_email = "remytheeog@gmail.com"
app_license = "mit"

after_migrate = ["rhema_daycare.setup.install_custom_fields"]

doc_events = {
    "Child Attendance Log": {
        "on_update": "rhema_daycare.attendance.alerts.evaluate_late_pickup"
    },
    "Classroom": {
        "before_delete": "rhema_daycare.doctypes.classroom.classroom.before_delete_classroom"
    },
    "Child Profile": {
        "on_trash": "rhema_daycare.doctypes.child_profile.child_profile.on_trash_child"
    },
    "Sales Invoice": {
        "on_submit": "rhema_daycare.billing.invoicing.on_invoice_submit"
    },
    "Salary Slip": {
        "validate": "rhema_daycare.hr.payroll.validate_payslip"
    },
}

scheduler_events = {
    "monthly": [
        "rhema_daycare.billing.invoicing.generate_monthly_invoices"
    ],
    "daily": [
        "rhema_daycare.billing.invoicing.send_payment_reminders",
        "rhema_daycare.billing.invoicing.calculate_late_pickup_fees",
        "rhema_daycare.billing.invoicing.check_missing_children"
    ],
    "hourly": [
        "rhema_daycare.attendance.alerts.check_active_late_pickups"
    ]
}

fixtures = [
    {"dt": "DocType", "filters": [["module", "=", "Rhema Daycare"]]},
    {"dt": "Role", "filters": [["role_name", "in", [
        "Daycare Manager", "Teacher", "Parent Portal User"
    ]]]},
    {"dt": "Salary Component", "filters": [["name", "in", [
        "Basic Salary", "Transport Allowance", "Meal Allowance",
        "PAYE", "NHIF", "NSSF"
    ]]]},
    {"dt": "Workflow", "filters": [["document_type", "=", "Child Profile"]]},
    {"dt": "Custom Field", "filters": [["dt", "in", [
        "Employee", "Customer", "Sales Invoice", "Child Attendance Log"
    ]]]},
]

website_route_rules = [
    {"from_route": "/parent-portal",      "to_route": "parent_portal"},
    {"from_route": "/child/<child_name>", "to_route": "child_detail"}
]

has_website_permission = {
    "Child Profile": "rhema_daycare.portal.permissions.has_website_permission"
}