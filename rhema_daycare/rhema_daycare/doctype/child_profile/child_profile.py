import base64
from io import BytesIO

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import date_diff, nowdate, getdate
from rhema_daycare.notifications import hub


class ChildProfile(Document):

    def validate(self):
        self._check_duplicate()
        self._validate_dob()
        self._validate_guardian()
        self._validate_emergency_contacts()
        self._validate_workflow_state()
        self._validate_edit_lock()
        if self.assigned_classroom:
            self._check_classroom_capacity()

    def _validate_edit_lock(self):
        """While a record is Pending Approval, only the reviewing role
        (Daycare Manager) or System Manager may save changes to it — the
        manual is explicit that 'the Teacher can no longer edit the record
        while it awaits approval' (Module 6, Part A). Workflow's per-state
        allow_edit is otherwise only a client-side hint in Frappe, not a
        server-side lock, so this is what actually enforces it. Scoped to
        the Pending Approval state only — Draft/Rejected stay editable by
        the Teacher (they're expected to fix and resubmit), and Approved
        stays editable by staff for ordinary record maintenance."""
        if self.is_new():
            return
        before = self.get_doc_before_save()
        if not before or before.workflow_state != "Pending Approval":
            return
        if {"Daycare Manager", "System Manager"}.intersection(frappe.get_roles(frappe.session.user)):
            return
        frappe.throw(
            _("{0} is Pending Approval and can only be edited by a Daycare "
              "Manager until the review is complete.").format(
                self.full_name or self.name),
            frappe.PermissionError
        )

    def _validate_dob(self):
        if not self.date_of_birth:
            frappe.throw(_("Date of birth is required."))
        dob = getdate(self.date_of_birth)
        today = getdate(nowdate())
        if dob > today:
            frappe.throw(_("Date of birth cannot be in the future."))
        age_months = date_diff(today, dob) / 30.44
        try:
            max_months = int(frappe.db.get_single_value(
                "Daycare Settings", "max_child_age_months") or 84)
        except Exception:
            max_months = 84
        if age_months > max_months:
            frappe.throw(
                _("Child is older than the maximum enrolment age of {0} months.").format(
                    max_months))

    def _validate_guardian(self):
        if not self.guardian:
            frappe.throw(_("A guardian (Customer record) must be linked."))

    def _validate_emergency_contacts(self):
        if not self.get("emergency_contacts"):
            frappe.throw(
                _("At least one emergency contact is required before saving."))

    def _validate_workflow_state(self):
        if self.status == "Active" and self.workflow_state != "Approved":
            frappe.throw(
                _("Child cannot be set to Active without enrollment approval."),
                frappe.PermissionError)

    def _check_duplicate(self):
        if not (self.full_name and self.date_of_birth and self.guardian):
            return
        existing = frappe.db.get_value("Child Profile", {
            "full_name":     self.full_name,
            "date_of_birth": self.date_of_birth,
            "guardian":      self.guardian,
            "name":          ["!=", self.name or ""]
        }, "name")
        if existing:
            frappe.throw(
                _("A child profile for {0} (DOB: {1}) under guardian {2} already exists: {3}").format(
                    self.full_name, self.date_of_birth,
                    self.guardian, existing),
                frappe.DuplicateEntryError)

    def _check_classroom_capacity(self):
        if not frappe.db.exists("Classroom", self.assigned_classroom):
            frappe.throw(
                _("Classroom {0} does not exist.").format(self.assigned_classroom))

        frappe.db.sql(
            "SELECT name FROM `tabClassroom` WHERE name = %s FOR UPDATE",
            (self.assigned_classroom,))

        classroom = frappe.get_doc("Classroom", self.assigned_classroom)

        if not classroom.capacity_limit:
            frappe.throw(
                _("Classroom {0} has no capacity limit configured. "
                  "Set one before assigning children.").format(self.assigned_classroom))

        try:
            max_ratio = int(frappe.db.get_single_value(
                "Daycare Settings", "max_children_per_teacher") or 8)
        except Exception:
            max_ratio = 8

        # Plain reads (frappe.db.count/get_value) are pinned to the snapshot
        # taken at this transaction's first read under MySQL/MariaDB's
        # default REPEATABLE-READ isolation, so they can still return a
        # stale pre-lock count even after the classroom row lock above is
        # granted. A locking read (FOR UPDATE) always reads the latest
        # committed data, which is required for the row lock above to
        # actually prevent concurrent over-enrollment.
        enrolled = frappe.db.sql(
            """SELECT COUNT(*) FROM `tabChild Profile`
               WHERE assigned_classroom = %s AND status = 'Active' AND name != %s
               FOR UPDATE""",
            (self.assigned_classroom, self.name or ""))[0][0]

        if enrolled >= classroom.capacity_limit:
            frappe.throw(
                _("Classroom {0} is full ({1}/{2}).").format(
                    self.assigned_classroom, enrolled,
                    classroom.capacity_limit),
                frappe.ValidationError)

        teachers = len(classroom.get("assigned_teachers") or [])
        if teachers == 0:
            frappe.throw(
                _("Classroom {0} has no teacher assigned. Assign at least "
                  "one teacher before enrolling children.").format(
                    self.assigned_classroom),
                frappe.ValidationError)

        if (enrolled + 1) > (teachers * max_ratio):
            frappe.throw(
                _("Adding this child would breach the 1:{0} teacher-to-child ratio "
                  "in {1}. Assign another teacher first.").format(
                    max_ratio, self.assigned_classroom),
                frappe.ValidationError)


def notify_on_approval(doc, method):
    """Doc event: fire the enrollment-approved notification exactly once,
    the moment workflow_state transitions into Approved."""
    if doc.workflow_state == "Approved" and doc.has_value_changed("workflow_state"):
        hub.send_enrollment_approved(doc)
        _warn_if_guardian_has_no_email(doc)
        _warn_if_no_immunization_record(doc)


def _warn_if_guardian_has_no_email(doc):
    """Non-blocking reminder for the approving Manager — matches the manual's own
    'Common Mistakes' framing (missing email degrades notifications, it does not
    block enrollment), so this warns rather than throws."""
    if not doc.guardian:
        return
    email = frappe.db.get_value("Customer", doc.guardian, "email_id")
    if not email:
        frappe.msgprint(
            _("{0}'s guardian has no email on file — enrollment and billing "
              "notifications will be silently skipped until one is added.").format(
                doc.full_name),
            indicator="orange", alert=True)


def _warn_if_no_immunization_record(doc):
    """Non-blocking reminder for the approving Manager. The manual's own
    Module 6 checklist lists 'documents attached' as something to verify
    before approving, and its Common Mistakes table frames a missing
    immunization record as something a Manager catches and rejects on
    review — a human judgement call, not a system-enforced block — so this
    warns rather than throws."""
    if not doc.immunization_records:
        frappe.msgprint(
            _("{0} has no immunization record attached. Per the pre-approval "
              "checklist, confirm documents are attached before proceeding — "
              "or reject and ask the Teacher to attach one.").format(doc.full_name),
            indicator="orange", alert=True)


def on_trash_child(doc, method):
    """Doc event: block deletion if open attendance logs exist."""
    open_logs = frappe.db.count("Child Attendance Log", {
        "child":     doc.name,
        "check_out": ["is", "not set"]
    })
    if open_logs:
        frappe.throw(
            _("Cannot delete {0}: {1} open attendance log(s) exist. "
              "Check out the child first.").format(doc.full_name, open_logs))


def get_child_id_qr_data_uri(child_name):
    """Server-side QR generation (not client-side JS) so the code renders
    reliably inside the exported PDF, not just an on-screen preview —
    wkhtmltopdf doesn't reliably execute canvas-drawing JS. Exposed to Print
    Format Jinja templates via the 'jinja' hook in hooks.py. Encodes the
    Child ID only (name/photo/classroom are rendered separately in the
    template) so the QR payload itself carries no medical/personal data."""
    import qrcode

    img = qrcode.make(child_name, box_size=6, border=2)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"

