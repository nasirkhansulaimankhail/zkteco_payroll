from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import frappe
from frappe.utils import add_days, flt, get_datetime

from zkteco_payroll.services.policy import get_penalty_absent_days_for_period


def apply_hourly_payroll_on_salary_slip(doc, _method=None):
	"""Doc event hook for Salary Slip.validate."""
	if not doc.employee:
		return

	settings = frappe.get_cached_doc("ZKTeco Payroll Settings")
	employee_cfg = frappe.db.get_value(
		"Employee",
		doc.employee,
		[
			"zkteco_hourly_payroll_enabled",
			"zkteco_hourly_rate",
			"zkteco_hourly_salary_component",
			"zkteco_hourly_round_to_minutes",
			"zkteco_overtime_multiplier",
			"zkteco_working_hours_per_day",
		],
		as_dict=True,
	)
	if not employee_cfg or not employee_cfg.zkteco_hourly_payroll_enabled:
		return

	worked_hours = get_worked_hours_for_period(doc.employee, doc.start_date, doc.end_date)
	rounded_hours = _round_hours(worked_hours, flt(employee_cfg.zkteco_hourly_round_to_minutes or 15))
	rate = flt(employee_cfg.zkteco_hourly_rate)
	overtime_multiplier = flt(employee_cfg.zkteco_overtime_multiplier or 1)
	hourly_amount = rounded_hours * rate * overtime_multiplier

	salary_component = employee_cfg.zkteco_hourly_salary_component or settings.default_hourly_salary_component
	if not salary_component:
		frappe.throw("Set Hourly Salary Component on Employee or in ZKTeco Payroll Settings.")

	_set_salary_component_amount(doc, salary_component, hourly_amount)

	working_hours_per_day = flt(employee_cfg.zkteco_working_hours_per_day or 8)
	if working_hours_per_day > 0:
		computed_payment_days = rounded_hours / working_hours_per_day
		total_working_days = flt(doc.total_working_days or 0)
		doc.payment_days = min(computed_payment_days, total_working_days) if total_working_days else computed_payment_days

	penalty_days = flt(get_penalty_absent_days_for_period(doc.employee, doc.start_date, doc.end_date))
	if penalty_days > 0:
		doc.leave_without_pay = flt(doc.leave_without_pay or 0) + penalty_days


@frappe.whitelist()
def get_worked_hours_for_period(employee: str, from_date: str, to_date: str) -> float:
	rows = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [from_date, add_days(to_date, 1)]],
		},
		fields=["time", "log_type"],
		order_by="time asc",
	)

	per_day = defaultdict(list)
	for row in rows:
		dt = get_datetime(row.time)
		per_day[dt.date()].append({"time": dt, "log_type": (row.log_type or "").upper()})

	total_seconds = 0.0
	for day_rows in per_day.values():
		in_queue: list[datetime] = []
		for row in day_rows:
			if row["log_type"] == "IN":
				in_queue.append(row["time"])
			elif row["log_type"] == "OUT" and in_queue:
				start = in_queue.pop(0)
				if row["time"] > start:
					total_seconds += (row["time"] - start).total_seconds()

	return total_seconds / 3600


def _set_salary_component_amount(doc, salary_component: str, amount: float):
	for row in doc.earnings:
		if row.salary_component == salary_component:
			row.amount = flt(amount)
			return
	doc.append("earnings", {"salary_component": salary_component, "amount": flt(amount)})


def _round_hours(hours: float, round_to_minutes: float) -> float:
	if round_to_minutes <= 0:
		return flt(hours)
	step = round_to_minutes / 60
	return round(flt(hours) / step) * step
