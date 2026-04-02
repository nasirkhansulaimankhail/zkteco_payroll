from __future__ import annotations

from frappe.utils import getdate, nowdate

from zkteco_payroll.services.attendance_analytics import get_employee_hours_summary


def execute(filters=None):
	filters = filters or {}
	from_date = filters.get("from_date") or nowdate()
	to_date = filters.get("to_date") or nowdate()

	columns = [
		{"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 150},
		{"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
		{"label": "Present Hours", "fieldname": "present_hours", "fieldtype": "Float", "width": 130},
		{"label": "Expected Hours", "fieldname": "expected_hours", "fieldtype": "Float", "width": 130},
		{"label": "Short Hours", "fieldname": "short_hours", "fieldtype": "Float", "width": 120},
		{"label": "Excess Hours", "fieldname": "excess_hours", "fieldtype": "Float", "width": 120},
	]

	data = get_employee_hours_summary(
		from_date=str(getdate(from_date)),
		to_date=str(getdate(to_date)),
		employee=filters.get("employee"),
		company=filters.get("company"),
	)

	return columns, data
