app_name = "rhema_daycare"
app_title = "Rhema Daycare"
app_publisher = "clement"
app_description = "Rhema Daycare is ideal for daycare centers, preschools, and early learning institutes looking for a modern, cloud-ready solution that keeps parents informed and staff organized—all in one place."
app_email = "remytheeog@gmail.com"
app_license = "mit"

# After Migrate
after_migrate = [
    "rhema_daycare.rhema_daycare.setup.add_custom_fields",
    "rhema_daycare.rhema_daycare.setup.setup_kenya_defaults"
]

# Document Events
doc_events = {
    "Child Attendance Log": {
        "on_update": "rhema_daycare.rhema_daycare.alerts.check_late_pickup"
    }
}

# Scheduled Tasks
scheduler_events = {
    "monthly": [
        "rhema_daycare.rhema_daycare.billing.generate_monthly_invoices"
    ],
    "daily": [
        "rhema_daycare.rhema_daycare.billing.send_payment_reminders",
        "rhema_daycare.rhema_daycare.attendance.send_daily_summary"
    ],
    "hourly": [
        "rhema_daycare.rhema_daycare.billing.calculate_late_pickup_fees"
    ]
}

# Fixtures
# hooks.py
fixtures = [
    # Export ALL your custom DocType definitions
    {"dt": "DocType", "filters": [
        ["module", "=", "Rhema Daycare"]
    ]},

    # Export roles
    {"dt": "Role", "filters": [
        ["role_name", "in", [
            "Daycare Manager",
            "Teacher",
            "Parent Portal User"
        ]]
    ]},

    # Export salary components
    {"dt": "Salary Component", "filters": [
        ["name", "in", [
            "Basic Salary",
            "Transport Allowance",
            "Meal Allowance",
            "PAYE",
            "NHIF",
            "NSSF"
        ]]
    ]},

    # Export the enrollment workflow
    {"dt": "Workflow", "filters": [
        ["document_type", "=", "Child Profile"]
    ]},

    # Export custom fields added to standard ERPNext DocTypes
    {"dt": "Custom Field", "filters": [
        ["dt", "in", [
            "Employee",
            "Customer",
            "Sales Invoice",
            "Child Attendance Log"
        ]]
    ]},
]

# Website Route Rules
website_route_rules = [
    {"from_route": "/parent-portal", "to_route": "parent_portal"},
    {"from_route": "/child/<name>", "to_route": "child_profile"},
    {"from_route": "/qr-scanner", "to_route": "qr_scanner"}
]

# Website Permissions
has_website_permission = {
    "Child Profile": "rhema_daycare.rhema_daycare.portal.has_website_permission"
}