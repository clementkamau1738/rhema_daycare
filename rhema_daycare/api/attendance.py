import re
import frappe
from frappe import _
from frappe.utils import now_datetime, today, get_time, get_datetime, time_diff_in_hours
from rhema_daycare.notifications import hub


@frappe.whitelist(methods=["POST"])
def checkin_child(child_id: str):
    # 1. Authentication
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    # 2. Permission
    if not frappe.has_permission("Child Attendance Log", "create"):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    # 3. Input validation
    if not child_id or not isinstance(child_id, str):
        frappe.throw(_("child_id must be a non-empty string."))
    if not re.match(r'^[\w\-]+$', child_id.strip()):
        frappe.throw(_("Invalid child_id format."))
    if len(child_id) > 140:
        frappe.throw(_("child_id too long."))

    # 4. Rate limit — checked here (fail fast on an in-flight/recent
    # duplicate), but only *set* once we know this attempt will actually
    # succeed (see below) so a failed attempt (bad child_id, already
    # checked in) doesn't burn a legitimate retry's 5-minute cooldown.
    cache_key = f"rhema_checkin_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw(_("Rate limit: please wait before retrying."))

    # 5. Child must exist and be Active
    child = frappe.db.get_value(
        "Child Profile",
        {"name": child_id.strip(), "status": "Active"},
        ["name", "full_name", "guardian", "assigned_classroom", "allergies"],
        as_dict=True
    )
    if not child:
        frappe.throw(
            _("Active child not found: '{0}'.").format(child_id),
            frappe.DoesNotExistError
        )

    # Lock this child's row so two near-simultaneous check-in requests (e.g.
    # a faulty scanner double-firing) can't both pass the duplicate-check-in
    # guard before either has inserted. The Redis rate limit above already
    # blocks most of these, but that check-then-set is itself non-atomic —
    # this lock is the real guarantee.
    frappe.db.sql(
        "SELECT name FROM `tabChild Profile` WHERE name = %s FOR UPDATE",
        (child.name,))

    # 6. Duplicate check-in guard — a locking read, not a plain frappe.db.exists(),
    # so it can't return a stale pre-lock snapshot under REPEATABLE READ.
    open_log = frappe.db.sql(
        """SELECT name FROM `tabChild Attendance Log`
           WHERE child = %s AND check_in >= %s AND check_out IS NULL
           FOR UPDATE""",
        (child.name, today()))
    if open_log:
        frappe.throw(
            _("'{0}' is already checked in. Check them out first.").format(
                child.full_name
            )
        )

    # Passed every check — this attempt will succeed, so it's now safe to
    # start the cooldown.
    frappe.cache().set(cache_key, 1, ex=300)

    # 7. Create log
    log = frappe.new_doc("Child Attendance Log")
    log.child         = child.name
    log.check_in      = now_datetime()
    log.status        = "Present"
    log.checked_in_by = frappe.session.user
    log.insert()
    frappe.db.commit()

    # 8. Notify guardian — never crashes check-in
    hub.send_checkin_notification(child)

    return {
        "status": "success",
        "child":  child.full_name,
        "log":    log.name,
        "time":   str(log.check_in),
        "allergy_alert": bool(child.get("allergies"))
    }


@frappe.whitelist(methods=["POST"])
def checkout_child(child_id: str):
    # 1. Authentication
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    # 2. Permission
    if not frappe.has_permission("Child Attendance Log", "write"):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    # 3. Input validation
    if not child_id or not isinstance(child_id, str):
        frappe.throw(_("child_id must be a non-empty string."))
    if not re.match(r'^[\w\-]+$', child_id.strip()):
        frappe.throw(_("Invalid child_id format."))
    if len(child_id) > 140:
        frappe.throw(_("child_id too long."))

    # 4. Rate limit — see checkin_child for why the set is deferred.
    cache_key = f"rhema_checkout_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw(_("Rate limit: please wait before retrying."))

    # 5. Child must exist and be Active
    child = frappe.db.get_value(
        "Child Profile",
        {"name": child_id.strip(), "status": "Active"},
        ["name", "full_name", "guardian", "assigned_classroom"],
        as_dict=True
    )
    if not child:
        frappe.throw(
            _("Active child not found: '{0}'.").format(child_id),
            frappe.DoesNotExistError
        )

    # Lock this child's row for the same reason as checkin_child — makes the
    # lookup below immune to a concurrently in-flight check-in/check-out.
    frappe.db.sql(
        "SELECT name FROM `tabChild Profile` WHERE name = %s FOR UPDATE",
        (child.name,))

    # 6. Find open log for today — locking read, see checkin_child for why.
    open_log_row = frappe.db.sql(
        """SELECT name FROM `tabChild Attendance Log`
           WHERE child = %s AND check_in >= %s AND check_out IS NULL
           FOR UPDATE""",
        (child.name, today()))
    open_log_name = open_log_row[0][0] if open_log_row else None

    if not open_log_name:
        frappe.throw(
            _("No open check-in found for '{0}' today.").format(
                child.full_name
            ),
            frappe.DoesNotExistError
        )

    # Found a real open log to close out — safe to start the cooldown now.
    frappe.cache().set(cache_key, 1, ex=300)

    # 7. Record checkout
    now = now_datetime()
    frappe.db.set_value("Child Attendance Log", open_log_name, {
        "check_out":      now,
        "checked_out_by": frappe.session.user,
        "status":         "Present"
    })
    frappe.db.commit()

    hub.send_checkout_notification(child, now)

    return {
        "status":  "success",
        "child":   child.full_name,
        "log":     open_log_name,
        "time":    str(now)
    }


@frappe.whitelist(methods=["POST"])
def simulate_late_pickup(child_id: str):
    from rhema_daycare.billing.invoicing import _settings, _calculate_fee

    # 1. Authentication
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    # 2. Permission — "write", not "read": this sends a real guardian
    # notification, a write-equivalent side effect, so it needs the same
    # bar as checkout_child, not the lower read-only bar.
    if not frappe.has_permission("Child Attendance Log", "write"):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    # 3. Input validation
    if not child_id or not isinstance(child_id, str):
        frappe.throw(_("child_id must be a non-empty string."))
    if not re.match(r'^[\w\-]+$', child_id.strip()):
        frappe.throw(_("Invalid child_id format."))
    if len(child_id) > 140:
        frappe.throw(_("child_id too long."))

    # 4. Rate limit — same cooldown as checkin/checkout, since this sends a
    # real notification and previously had no throttle at all. Set is
    # deferred until we've confirmed there's an open log to simulate against.
    cache_key = f"rhema_simulate_latepickup_{child_id}"
    if frappe.cache().get(cache_key):
        frappe.throw(_("Rate limit: please wait before retrying."))

    # 5. Child must exist and be Active
    child = frappe.db.get_value(
        "Child Profile",
        {"name": child_id.strip(), "status": "Active"},
        ["name", "full_name", "guardian"],
        as_dict=True
    )
    if not child:
        frappe.throw(
            _("Active child not found: '{0}'.").format(child_id),
            frappe.DoesNotExistError
        )

    # 6. Must actually be checked in right now — otherwise there is nothing
    # to simulate, and without this check any Teacher could alarm any
    # guardian of any Active child at will, whether or not that child was
    # ever at the daycare that day.
    open_log = frappe.db.exists("Child Attendance Log", {
        "child":     child.name,
        "check_in":  [">=", today()],
        "check_out": ["is", "not set"]
    })
    if not open_log:
        frappe.throw(
            _("'{0}' has no open check-in today — nothing to simulate.").format(
                child.full_name))

    frappe.cache().set(cache_key, 1, ex=300)

    # 7. Calculate the fee as if pickup happened right now (no invoice created)
    settings = _settings()
    cutoff = get_time(settings.get("pickup_cutoff_time") or "17:30:00")
    cutoff_dt = get_datetime(f"{today()} {cutoff}")
    hours_late = max(0.0, time_diff_in_hours(now_datetime(), cutoff_dt))
    fee = _calculate_fee(hours_late, settings)

    if child.get("guardian"):
        hub.send_late_pickup_alert(child, hours_late * 60, fee=fee)

    return {
        "status": "success",
        "child": child.full_name,
        "hours_late": round(hours_late, 2),
        "estimated_fee": fee
    }


@frappe.whitelist()
def get_today_log():
    # 1. Authentication
    if frappe.session.user == "Guest":
        frappe.throw(_("Authentication required."), frappe.AuthenticationError)

    # 2. Permission
    if not frappe.has_permission("Child Attendance Log", "read"):
        frappe.throw(_("Insufficient permissions."), frappe.PermissionError)

    logs = frappe.get_all(
        "Child Attendance Log",
        filters={"check_in": [">=", today()]},
        fields=["name", "child", "check_in", "check_out", "status"],
        order_by="check_in desc"
    )
    if not logs:
        return []

    children = frappe.get_all(
        "Child Profile",
        filters={"name": ["in", [log.child for log in logs]]},
        fields=["name", "full_name"]
    )
    full_names = {c.name: c.full_name for c in children}
    for log in logs:
        log["child_name"] = full_names.get(log.child, log.child)

    return logs

