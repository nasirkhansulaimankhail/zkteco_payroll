from __future__ import annotations

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def ensure_custom_fields():
	custom_fields = {
		"Employee": [
			{
				"fieldname": "zkteco_payroll_section",
				"fieldtype": "Section Break",
				"label": "ZKTeco Payroll",
				"insert_after": "attendance_device_id",
			},
			{
				"fieldname": "zkteco_hourly_payroll_enabled",
				"fieldtype": "Check",
				"label": "Enable Hourly Payroll",
				"default": "0",
				"insert_after": "zkteco_payroll_section",
			},
			{
				"fieldname": "zkteco_hourly_rate",
				"fieldtype": "Currency",
				"label": "Hourly Rate",
				"insert_after": "zkteco_hourly_payroll_enabled",
				"depends_on": "eval:doc.zkteco_hourly_payroll_enabled",
			},
			{
				"fieldname": "zkteco_hourly_salary_component",
				"fieldtype": "Link",
				"label": "Hourly Salary Component",
				"options": "Salary Component",
				"insert_after": "zkteco_hourly_rate",
				"depends_on": "eval:doc.zkteco_hourly_payroll_enabled",
			},
			{
				"fieldname": "zkteco_hourly_round_to_minutes",
				"fieldtype": "Int",
				"label": "Round Hours to Minutes",
				"default": "15",
				"insert_after": "zkteco_hourly_salary_component",
				"depends_on": "eval:doc.zkteco_hourly_payroll_enabled",
			},
			{
				"fieldname": "zkteco_overtime_multiplier",
				"fieldtype": "Float",
				"label": "Overtime Multiplier",
				"default": "1",
				"insert_after": "zkteco_hourly_round_to_minutes",
				"depends_on": "eval:doc.zkteco_hourly_payroll_enabled",
			},
			{
				"fieldname": "zkteco_working_hours_per_day",
				"fieldtype": "Float",
				"label": "Working Hours Per Day",
				"default": "8",
				"insert_after": "zkteco_overtime_multiplier",
				"depends_on": "eval:doc.zkteco_hourly_payroll_enabled",
			},
		],
		"Shift Type": [
			{
				"fieldname": "zkteco_policy_section",
				"fieldtype": "Section Break",
				"label": "ZKTeco Policy",
				"insert_after": "late_entry_grace_period",
			},
			{
				"fieldname": "zkteco_lates_per_absent",
				"fieldtype": "Int",
				"label": "Lates per Absent",
				"default": "3",
				"insert_after": "zkteco_policy_section",
			},
			{
				"fieldname": "zkteco_missing_logs_per_absent",
				"fieldtype": "Int",
				"label": "Missing Checkin/Checkout per Absent",
				"default": "3",
				"insert_after": "zkteco_lates_per_absent",
			},
			{
				"fieldname": "zkteco_convert_penalty_to_paid_leave",
				"fieldtype": "Check",
				"label": "Convert Penalty Absent to Paid Leave",
				"default": "0",
				"insert_after": "zkteco_missing_logs_per_absent",
			},
			{
				"fieldname": "zkteco_paid_leave_type",
				"fieldtype": "Link",
				"label": "Paid Leave Type",
				"options": "Leave Type",
				"insert_after": "zkteco_convert_penalty_to_paid_leave",
				"depends_on": "eval:doc.zkteco_convert_penalty_to_paid_leave",
			},
		],
	}

	create_custom_fields(custom_fields, update=True)
