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
        "before_delete": "rhema_daycare.rhema_daycare.doctype.classroom.classroom.before_delete_classroom"
    },
    "Child Profile": {
        "on_trash": "rhema_daycare.rhema_daycare.doctype.child_profile.child_profile.on_trash_child",
        "on_update": "rhema_daycare.rhema_daycare.doctype.child_profile.child_profile.notify_on_approval"
    },
    "Sales Invoice": {
        "on_submit": "rhema_daycare.billing.invoicing.on_invoice_submit"
    },
    "Salary Slip": {
        "validate": [
            "rhema_daycare.hr.payroll.apply_statutory_deductions",
            "rhema_daycare.hr.payroll.validate_payslip"
        ]
    },
    "Employee": {
        "validate": [
            "rhema_daycare.hr.employee.validate_background_check",
            "rhema_daycare.hr.employee.validate_cpr_certification"
        ]
    },
}

scheduler_events = {
    "hourly": [
        "rhema_daycare.attendance.alerts.check_active_late_pickups",
        "rhema_daycare.billing.invoicing.calculate_late_pickup_fees",
        # hourly + self-gated on Daycare Settings.absence_alert_time (not a
        # fixed daily cron) so a Manager changing that setting to later than
        # 9:30 AM can't cause the alert to silently never fire that day
        "rhema_daycare.billing.invoicing.check_missing_children",
        "rhema_daycare.notifications.hub.reconcile_queued_notifications"
    ],
    "cron": {
        # midnight on the 1st of the month
        "0 0 1 * *": [
            "rhema_daycare.billing.invoicing.generate_monthly_invoices"
        ],
        # 9:00 AM daily
        "0 9 * * *": [
            "rhema_daycare.billing.invoicing.send_payment_reminders"
        ]
    }
}

fixtures = [
    {"dt": "DocType", "filters": [["module", "=", "Rhema Daycare"]]},
    {"dt": "Role", "filters": [["role_name", "in", [
        "Daycare Manager", "Teacher", "Parent Portal User"
    ]]]},
    {"dt": "Salary Component", "filters": [["name", "in", [
        "Basic Salary", "Transport Allowance", "Meal Allowance",
        "PAYE", "NHIF", "NSSF", "Housing Levy"
    ]]]},
    {"dt": "Currency", "filters": [["name", "=", "KES"]]},
    {"dt": "Workflow", "filters": [["document_type", "=", "Child Profile"]]},
    {"dt": "Custom Field", "filters": [["dt", "in", [
        "Employee", "Customer", "Sales Invoice", "Child Attendance Log"
    ]]]},
    {"dt": "Email Template", "filters": [["name", "like", "Rhema:%"]]},
    {"dt": "Print Format", "filters": [["name", "=", "Child ID Card"]]},
]

website_route_rules = [
    {"from_route": "/parent-portal",      "to_route": "parent_portal"},
    {"from_route": "/child/<child_name>", "to_route": "child_detail"},
    {"from_route": "/qr-scanner",         "to_route": "qr_scanner"}
]

has_website_permission = {
    "Child Profile": "rhema_daycare.portal.permissions.has_website_permission"
}

jinja = {
    "methods": [
        "rhema_daycare.rhema_daycare.doctype.child_profile.child_profile.get_child_id_qr_data_uri",
    ]
}