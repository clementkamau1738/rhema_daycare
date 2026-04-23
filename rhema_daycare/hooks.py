app_name = "rhema_daycare"
app_title = "Rhema Daycare"
app_publisher = "clement"
app_description = "Rhema Daycare is ideal for daycare centers, preschools, and early learning institutes looking for a modern, cloud-ready solution that keeps parents informed and staff organized—all in one place."
app_email = "remytheeog@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "rhema_daycare",
# 		"logo": "/assets/rhema_daycare/logo.png",
# 		"title": "Rhema Daycare",
# 		"route": "/rhema_daycare",
# 		"has_permission": "rhema_daycare.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/rhema_daycare/css/rhema_daycare.css"
# app_include_js = "/assets/rhema_daycare/js/rhema_daycare.js"

# include js, css files in header of web template
# web_include_css = "/assets/rhema_daycare/css/rhema_daycare.css"
# web_include_js = "/assets/rhema_daycare/js/rhema_daycare.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "rhema_daycare/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "rhema_daycare/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "rhema_daycare.utils.jinja_methods",
# 	"filters": "rhema_daycare.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "rhema_daycare.install.before_install"
# after_install = "rhema_daycare.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "rhema_daycare.uninstall.before_uninstall"
# after_uninstall = "rhema_daycare.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "rhema_daycare.utils.before_app_install"
# after_app_install = "rhema_daycare.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "rhema_daycare.utils.before_app_uninstall"
# after_app_uninstall = "rhema_daycare.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "rhema_daycare.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"rhema_daycare.tasks.all"
# 	],
# 	"daily": [
# 		"rhema_daycare.tasks.daily"
# 	],
# 	"hourly": [
# 		"rhema_daycare.tasks.hourly"
# 	],
# 	"weekly": [
# 		"rhema_daycare.tasks.weekly"
# 	],
# 	"monthly": [
# 		"rhema_daycare.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "rhema_daycare.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "rhema_daycare.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "rhema_daycare.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["rhema_daycare.utils.before_request"]
# after_request = ["rhema_daycare.utils.after_request"]

# Job Events
# ----------
# before_job = ["rhema_daycare.utils.before_job"]
# after_job = ["rhema_daycare.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"rhema_daycare.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# Fixtures
fixtures = [
    {
        "doctype": "Salary Component",
        "filters": [
            ["salary_component", "in", [
                "Basic Salary",
                "Transport Allowance",
                "Meal Allowance",
                "PAYE",
                "NSSF",
                "Housing Levy"
            ]]
        ]
    }
]

website_route_rules = [
    {"from_route": "/parent-portal", "to_route": "parent_portal"},
    {"from_route": "/child/<name>", "to_route": "child_profile"}
]

has_website_permission = {
    "Child Profile": "rhema_daycare.portal.has_website_permission"
}
