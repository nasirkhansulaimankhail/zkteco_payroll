from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import frappe
from frappe.utils import add_days, flt, get_datetime, getdate


@dataclass
class DayHours:
	present_hours: float = 0.0
	expected_hours: float = 0.0
	shift_type: str | None = None
	first_in: datetime | None = None
	last_out: datetime | None = None


@frappe.whitelist()
def get_employee_hours_summary(from_date: str, to_date: str, employee: str | None = None, company: str | None = None) -> list[dict]:
	from_d = getdate(from_date)
	to_d = getdate(to_date)
	if from_d > to_d:
		frappe.throw("From Date cannot be after To Date")

	employee_filters = {"status": "Active"}
	if employee:
		employee_filters["name"] = employee
	if company:
		employee_filters["company"] = company

	employees = frappe.get_all(
		"Employee",
		filters=employee_filters,
		fields=["name", "employee_name", "company", "attendance_device_id"],
		order_by="employee_name asc",
	)
	if not employees:
		return []

	emp_ids = [row.name for row in employees]
	checkins = _get_checkins(emp_ids, from_d, to_d)
	assignments = _get_shift_assignments(emp_ids, from_d, to_d)
	shift_hours = _get_shift_hours(assignments)

	rows: list[dict] = []
	for emp in employees:
		daily = _build_daily_hours(emp.name, from_d, to_d, checkins.get(emp.name, {}), assignments.get(emp.name, []), shift_hours)
		present = round(sum(day.present_hours for day in daily.values()), 2)
		expected = round(sum(day.expected_hours for day in daily.values()), 2)
		short = round(max(expected - present, 0), 2)
		excess = round(max(present - expected, 0), 2)
		rows.append(
			{
				"employee": emp.name,
				"employee_name": emp.employee_name,
				"company": emp.company,
				"present_hours": present,
				"expected_hours": expected,
				"short_hours": short,
				"excess_hours": excess,
			}
		)

	return rows


@frappe.whitelist()
def get_employee_attendance_history(employee: str, from_date: str, to_date: str) -> list[dict]:
	from_d = getdate(from_date)
	to_d = getdate(to_date)
	if from_d > to_d:
		frappe.throw("From Date cannot be after To Date")
	if not employee:
		frappe.throw("Employee is required")

	checkins = _get_checkins([employee], from_d, to_d).get(employee, {})
	assignments = _get_shift_assignments([employee], from_d, to_d).get(employee, [])
	shift_hours = _get_shift_hours({employee: assignments})
	daily = _build_daily_hours(employee, from_d, to_d, checkins, assignments, shift_hours)

	history: list[dict] = []
	day = from_d
	while day <= to_d:
		data = daily.get(day, DayHours())
		present = round(data.present_hours, 2)
		expected = round(data.expected_hours, 2)
		short = round(max(expected - present, 0), 2)
		excess = round(max(present - expected, 0), 2)
		history.append(
			{
				"date": str(day),
				"shift_type": data.shift_type,
				"first_in": data.first_in,
				"last_out": data.last_out,
				"present_hours": present,
				"expected_hours": expected,
				"short_hours": short,
				"excess_hours": excess,
			}
		)
		day = add_days(day, 1)

	return history


def _get_checkins(employees: list[str], from_d: date, to_d: date) -> dict[str, dict[date, list[dict]]]:
	if not employees:
		return {}

	rows = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": ["in", employees],
			"time": ["between", [from_d, add_days(to_d, 1)]],
		},
		fields=["employee", "time", "log_type"],
		order_by="employee asc, time asc",
	)

	out: dict[str, dict[date, list[dict]]] = defaultdict(lambda: defaultdict(list))
	for row in rows:
		dt = get_datetime(row.time)
		out[row.employee][dt.date()].append({"time": dt, "log_type": (row.log_type or "").upper()})
	return out


def _get_shift_assignments(employees: list[str], from_d: date, to_d: date) -> dict[str, list[dict]]:
	if not employees:
		return {}

	rows = frappe.db.sql(
		"""
		select
			employee,
			shift_type,
			start_date,
			end_date
		from `tabShift Assignment`
		where docstatus = 1
		  and employee in %(employees)s
		  and start_date <= %(to_date)s
		  and (end_date is null or end_date = '' or end_date >= %(from_date)s)
		order by employee asc, start_date asc
		""",
		{"employees": employees, "from_date": from_d, "to_date": to_d},
		as_dict=True,
	)

	out: dict[str, list[dict]] = defaultdict(list)
	for row in rows:
		out[row.employee].append(
			{
				"shift_type": row.shift_type,
				"start_date": getdate(row.start_date),
				"end_date": getdate(row.end_date) if row.end_date else None,
			}
		)
	return out


def _get_shift_hours(assignments_by_employee: dict[str, list[dict]]) -> dict[str, float]:
	shift_types = {item["shift_type"] for rows in assignments_by_employee.values() for item in rows if item.get("shift_type")}
	if not shift_types:
		return {}

	rows = frappe.get_all("Shift Type", filters={"name": ["in", list(shift_types)]}, fields=["name", "start_time", "end_time"])
	out: dict[str, float] = {}
	for row in rows:
		out[row.name] = _hours_between(row.start_time, row.end_time)
	return out


def _build_daily_hours(
	employee: str,
	from_d: date,
	to_d: date,
	checkins_by_day: dict[date, list[dict]],
	assignments: list[dict],
	shift_hours: dict[str, float],
) -> dict[date, DayHours]:
	out: dict[date, DayHours] = {}
	day = from_d
	while day <= to_d:
		day_obj = DayHours()
		shift_type = _find_shift_for_day(assignments, day)
		day_obj.shift_type = shift_type
		if shift_type:
			day_obj.expected_hours = flt(shift_hours.get(shift_type) or 0)

		rows = checkins_by_day.get(day, [])
		if rows:
			day_obj.present_hours = _compute_present_hours(rows)
			ins = [r["time"] for r in rows if r["log_type"] == "IN"]
			outs = [r["time"] for r in rows if r["log_type"] == "OUT"]
			day_obj.first_in = min(ins) if ins else None
			day_obj.last_out = max(outs) if outs else None

		out[day] = day_obj
		day = add_days(day, 1)

	return out


def _compute_present_hours(rows: list[dict]) -> float:
	seconds = 0.0
	in_queue: list[datetime] = []
	for row in rows:
		if row["log_type"] == "IN":
			in_queue.append(row["time"])
		elif row["log_type"] == "OUT" and in_queue:
			start = in_queue.pop(0)
			if row["time"] > start:
				seconds += (row["time"] - start).total_seconds()
	return round(seconds / 3600, 2)


def _find_shift_for_day(assignments: list[dict], day: date) -> str | None:
	selected = None
	for row in assignments:
		start = row["start_date"]
		end = row["end_date"] or date.max
		if start <= day <= end:
			selected = row["shift_type"]
	return selected


def _hours_between(start_time, end_time) -> float:
	start = _to_time(start_time)
	end = _to_time(end_time)
	if not start or not end:
		return 0.0

	start_dt = datetime.combine(date.min, start)
	end_dt = datetime.combine(date.min, end)
	if end_dt <= start_dt:
		end_dt += timedelta(days=1)
	return round((end_dt - start_dt).total_seconds() / 3600, 2)


def _to_time(value) -> time | None:
	if not value:
		return None
	if isinstance(value, time):
		return value
	if isinstance(value, timedelta):
		base = datetime.min + value
		return base.time()
	if isinstance(value, str):
		parts = value.split(":")
		if len(parts) >= 2:
			h = int(parts[0])
			m = int(parts[1])
			s = int(parts[2]) if len(parts) > 2 else 0
			return time(hour=h, minute=m, second=s)
	return None
