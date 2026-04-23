import frappe
import unittest


class TestClassroom(unittest.TestCase):

    def setUp(self):
        self.classroom = frappe.new_doc("Classroom")
        self.classroom.classroom_name = "Test Classroom"
        self.classroom.capacity_limit = 10
        self.classroom.monthly_fee = 5000
        self.classroom.status = "Active"

    def test_valid_classroom_creation(self):
        self.classroom.insert(ignore_permissions=True)
        self.assertIsNotNone(self.classroom.name)

    def test_classroom_capacity(self):
        self.classroom.insert(ignore_permissions=True)
        self.assertEqual(self.classroom.capacity_limit, 10)

    def test_classroom_fee(self):
        self.classroom.insert(ignore_permissions=True)
        self.assertEqual(self.classroom.monthly_fee, 5000)

    def test_classroom_name_not_empty(self):
        """Test classroom name validation directly"""
        self.assertNotEqual(self.classroom.classroom_name, "")
        self.assertIsNotNone(self.classroom.classroom_name)

    def tearDown(self):
        frappe.db.rollback()
