from frappe import _


def get_data():
	return {
		"fieldname": "assigned_classroom",
		"transactions": [
			{"label": _("Enrollment"), "items": ["Child Profile"]},
		],
	}
