import frappe
from frappe.model.document import Document


class ChildProfile(Document):

    def validate(self):
        self.validate_age()
        self.check_classroom_capacity()

    def validate_age(self):
        from frappe.utils import date_diff, nowdate, getdate
        if not self.date_of_birth:
            return
        age_days = date_diff(nowdate(), getdate(self.date_of_birth))
        if age_days < 0:
            frappe.throw("Date of birth cannot be in the future.")

    def check_classroom_capacity(self):
        if not self.assigned_classroom:
            return
        classroom = frappe.get_doc("Classroom", self.assigned_classroom)
        if not hasattr(classroom, "capacity_limit") or not classroom.capacity_limit:
            return
        enrolled = frappe.db.count("Child Profile", {
            "assigned_classroom": self.assigned_classroom,
            "status": "Active",
            "name": ["!=", self.name]
        })
        if enrolled >= classroom.capacity_limit:
            frappe.throw(f"Classroom {self.assigned_classroom} is at full capacity.")
