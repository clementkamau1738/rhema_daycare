
def send_daily_summary():
    """Send daily attendance summary to managers."""
    import frappe
    try:
        managers = frappe.get_all("User", filters={"role_profile_name": "Daycare Manager"}, fields=["email"])
        if not managers:
            return
        today = frappe.utils.today()
        total = frappe.db.count("Child Attendance Log", {"check_in": [">=", today + " 00:00:00"]})
        checked_out = frappe.db.count("Child Attendance Log", {
            "check_in": [">=", today + " 00:00:00"],
            "check_out": ["is", "set"]
        })
        for mgr in managers:
            frappe.sendmail(
                recipients=[mgr.email],
                subject=f"Daily Attendance Summary — {today} | Rhema Daycare",
                message=f"<p>Total check-ins: {total}<br>Checked out: {checked_out}<br>Still present: {total - checked_out}</p>"
            )
    except Exception as e:
        frappe.log_error(str(e), "Daily Summary Error")
