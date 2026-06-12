import frappe
from frappe.model.document import Document


class ChildProfile(Document):

    def validate(self):
        self.validate_age()
        self.validate_guardian()
        self.set_defaults()
        self.check_classroom_capacity()

    def validate_age(self):
        from frappe.utils import date_diff, nowdate, getdate
        if not self.date_of_birth:
            return
        age_days = date_diff(nowdate(), getdate(self.date_of_birth))
        if age_days < 0:
            frappe.throw("Date of birth cannot be in the future.", frappe.ValidationError)

    def validate_guardian(self):
        if not self.guardian and self.status == "Active":
            frappe.msgprint("Warning: Active child has no guardian assigned.", alert=True)

    def set_defaults(self):
        if not self.status:
            self.status = "Active"

    def check_classroom_capacity(self):
        if not self.assigned_classroom:
            return
        if not frappe.db.exists("Classroom", self.assigned_classroom):
            frappe.throw(f"Classroom {self.assigned_classroom} does not exist.")
        frappe.db.sql("SELECT capacity_limit FROM `tabClassroom` WHERE name = %s FOR UPDATE", self.assigned_classroom)
        classroom = frappe.get_doc("Classroom", self.assigned_classroom)
        if not classroom.capacity_limit:
            return
        enrolled = frappe.db.count("Child Profile", {
            "assigned_classroom": self.assigned_classroom,
            "status": "Active",
            "name": ["!=", self.name]
        })
        if enrolled >= classroom.capacity_limit:
            frappe.throw(f"Classroom {self.assigned_classroom} is at full capacity ({enrolled}/{classroom.capacity_limit}).", frappe.ValidationError)
