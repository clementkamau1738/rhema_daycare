import frappe
from frappe.model.document import Document


class ChildAttendanceLog(Document):

    def validate(self):
        self.validate_checkout_time()

    def validate_checkout_time(self):
        if self.check_out and self.check_in:
            if self.check_out <= self.check_in:
                frappe.throw(
                    "Check-out time must be after check-in time."
                )