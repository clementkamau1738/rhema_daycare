import frappe
from frappe.model.document import Document


class Classroom(Document):

    def validate(self):
        self.validate_teacher_ratio()

    def validate_teacher_ratio(self):
        # Kenya regulation: 1 teacher per 8 children max
        active_children = frappe.db.count("Child Profile", {
            "assigned_classroom": self.name,
            "status": "Active"
        })

        teacher_count = len(self.assigned_teachers or [])

        if teacher_count == 0:
            # No teachers assigned yet, skip ratio check
            return

        ratio = active_children / teacher_count

        if ratio > 8:
            frappe.msgprint(
                f"Warning: Staff-to-child ratio is 1:{int(ratio)}, "
                "which exceeds the Kenya regulation of 1:8.",
                alert=True
            )