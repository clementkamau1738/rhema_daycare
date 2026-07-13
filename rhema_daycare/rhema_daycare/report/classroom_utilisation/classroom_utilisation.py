import frappe


def execute(filters=None):
    filters = filters or {}
    columns = [
        {"label": "Classroom", "fieldname": "classroom_name", "fieldtype": "Data", "width": 180},
        {"label": "Capacity", "fieldname": "capacity_limit", "fieldtype": "Int", "width": 100},
        {"label": "Enrolled", "fieldname": "enrolled", "fieldtype": "Int", "width": 100},
        {"label": "Utilisation %", "fieldname": "utilisation_pct", "fieldtype": "Percent", "width": 130},
        {"label": "Teachers", "fieldname": "teacher_count", "fieldtype": "Int", "width": 90},
        {"label": "Ratio Compliance", "fieldname": "ratio_status", "fieldtype": "Data", "width": 140},
    ]

    # Teacher counts and enrolled-child counts are independent one-to-many
    # relations off Classroom. Joining both in a single query produces a
    # cross product (T teachers x C children rows per classroom), which
    # silently inflates "enrolled" by a factor of the teacher count for any
    # classroom with more than one teacher. Aggregate each relation
    # separately and merge in Python instead.
    classrooms = frappe.db.sql("""
        SELECT name, classroom_name, capacity_limit
        FROM `tabClassroom`
        ORDER BY classroom_name
    """, as_dict=True)

    teacher_counts = dict(frappe.db.sql("""
        SELECT parent, COUNT(*) FROM `tabClassroom Teacher` GROUP BY parent
    """))

    enrolled_counts = dict(frappe.db.sql("""
        SELECT assigned_classroom, COUNT(*) FROM `tabChild Profile`
        WHERE status = 'Active' AND assigned_classroom IS NOT NULL AND assigned_classroom != ''
        GROUP BY assigned_classroom
    """))

    for row in classrooms:
        row["teacher_count"] = teacher_counts.get(row.name, 0)
        row["enrolled"] = enrolled_counts.get(row.name, 0)

    max_ratio = frappe.db.get_single_value("Daycare Settings", "max_children_per_teacher") or 8

    data = []
    for row in classrooms:
        enrolled = row.enrolled or 0
        capacity = row.capacity_limit or 0
        teacher_count = row.teacher_count or 0
        utilisation_pct = round((enrolled / capacity) * 100, 1) if capacity else 0

        if teacher_count == 0:
            ratio_status = "No Teacher" if enrolled else "N/A"
        elif (enrolled / teacher_count) > max_ratio:
            ratio_status = f"Breach (1:{round(enrolled / teacher_count, 1)})"
        else:
            ratio_status = "Compliant"

        data.append({
            "classroom_name": row.classroom_name,
            "capacity_limit": capacity,
            "enrolled": enrolled,
            "utilisation_pct": utilisation_pct,
            "teacher_count": teacher_count,
            "ratio_status": ratio_status,
        })

    return columns, data
