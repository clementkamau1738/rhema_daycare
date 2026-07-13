import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time, getdate, nowdate


class Classroom(Document):

    def validate(self):
        self.validate_teacher_ratio()
        self.validate_schedule_overlaps()
        self.validate_capacity_reduction()
        self.validate_teacher_compliance()

    def validate_teacher_ratio(self):
        # Kenya regulation: 1 teacher per 8 children max
        active_children = frappe.db.count("Child Profile", {
            "assigned_classroom": self.name,
            "status": "Active"
        })

        if active_children == 0:
            return

        teacher_count = len(self.assigned_teachers or [])

        if teacher_count == 0:
            frappe.msgprint(
                _("{0} has {1} active child(ren) but no assigned teacher. "
                  "This is a compliance risk — assign at least one teacher "
                  "as soon as possible.").format(self.name, active_children),
                indicator="orange", alert=True)
            return

        ratio = active_children / teacher_count

        if ratio > 8:
            # Non-blocking, matching the zero-teacher branch above and
            # M2-08's explicit "warning, not hard block" framing. A hard
            # throw here previously trapped Managers mid-reassignment: they
            # could not save a partial teacher removal (e.g. 3 -> 1) even
            # though removing every teacher (3 -> 0) was already allowed
            # with just a warning -- the more dangerous state was the one
            # permitted. Enrollment-side enforcement in
            # child_profile.py::_check_classroom_capacity still hard-blocks
            # *new* enrollments that would breach the ratio; this warning
            # only covers edits to an already-saved Classroom.
            frappe.msgprint(
                _("Staff-to-child ratio in {0} is 1:{1}, which exceeds the "
                  "Kenya regulation of 1:8. This is a compliance risk — "
                  "assign another teacher as soon as possible.").format(
                    self.name, round(ratio, 1)),
                indicator="orange", alert=True)

    def validate_schedule_overlaps(self):
        by_day = {}
        for row in self.get("daily_schedule") or []:
            by_day.setdefault(row.day, []).append(row)

        for day, rows in by_day.items():
            intervals = sorted(
                ((get_time(r.start_time), get_time(r.end_time), r) for r in rows),
                key=lambda t: t[0]
            )
            for i in range(1, len(intervals)):
                prev_start, prev_end, prev_row = intervals[i - 1]
                start, end, row = intervals[i]
                if start < prev_end:
                    frappe.throw(
                        _("Daily Schedule: '{0}' ({1}–{2}) overlaps with '{3}' "
                          "({4}–{5}) on {6}.").format(
                            row.activity, row.start_time, row.end_time,
                            prev_row.activity, prev_row.start_time, prev_row.end_time,
                            day))

    def validate_capacity_reduction(self):
        if self.is_new() or not self.has_value_changed("capacity_limit"):
            return
        before = self.get_doc_before_save()
        if not before or (before.capacity_limit or 0) <= (self.capacity_limit or 0):
            return
        enrolled = frappe.db.count("Child Profile", {
            "assigned_classroom": self.name,
            "status": "Active"
        })
        if self.capacity_limit < enrolled:
            frappe.throw(
                _("Cannot reduce capacity to {0}: {1} are already actively "
                  "enrolled in {2}. Reassign children first.").format(
                    self.capacity_limit, enrolled, self.name))

    def validate_teacher_compliance(self):
        """Mirrors the block enforced on the Employee side
        (hr.employee.validate_background_check / validate_cpr_certification)
        so a Manager can't route around it by adding a non-compliant teacher
        from the Classroom's Assigned Teachers table instead. The manual is
        explicit that a Failed background check 'blocks saving and prevents
        assignment to any classroom' — that has to hold from both directions."""
        require_cpr = frappe.db.get_single_value(
            "Daycare Settings", "require_cpr_for_teachers")

        for row in self.get("assigned_teachers") or []:
            if not row.teacher:
                continue
            emp = frappe.db.get_value(
                "Employee", row.teacher,
                ["employee_name", "background_check_status",
                 "cpr_certified", "cpr_expiry_date"],
                as_dict=True
            )
            if not emp:
                continue

            if emp.background_check_status == "Failed":
                frappe.throw(
                    _("{0} has a Failed background check and cannot be "
                      "assigned to {1}. Remove them from Assigned Teachers "
                      "first.").format(
                        emp.employee_name or row.teacher, self.name),
                    frappe.ValidationError
                )

            if not require_cpr:
                continue

            if not emp.cpr_certified:
                frappe.throw(
                    _("{0} is not CPR certified and cannot be assigned to "
                      "{1}. Daycare Settings requires CPR certification for "
                      "teachers.").format(
                        emp.employee_name or row.teacher, self.name),
                    frappe.ValidationError
                )
            if emp.cpr_expiry_date and getdate(emp.cpr_expiry_date) < getdate(nowdate()):
                frappe.throw(
                    _("{0}'s CPR certification expired on {1} and cannot be "
                      "assigned to {2} until it is renewed.").format(
                        emp.employee_name or row.teacher,
                        emp.cpr_expiry_date, self.name),
                    frappe.ValidationError
                )


def before_delete_classroom(doc, method):
    """Doc event: block deletion if children are still assigned to this classroom."""
    assigned_children = frappe.db.count("Child Profile", {
        "assigned_classroom": doc.name
    })
    if assigned_children:
        frappe.throw(
            _("Cannot delete {0}: {1} child profile(s) are still assigned to "
              "this classroom. Reassign them first.").format(
                doc.name, assigned_children))
