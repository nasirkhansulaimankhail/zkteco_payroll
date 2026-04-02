from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime, timedelta

import frappe
from frappe.utils import add_days, get_datetime, getdate


def get_penalty_absent_days_for_period(employee: str, from_date: str, to_date: str) -> float:
	from_d = getdate(from_date)
	to_d = getdate(to_date)
	if not employee or from_d > to_d:
		return 0.0

	rows = frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ["between", [from_d, add_days(to_d, 1)]],
		},
		fields=["time", "log_type"],
		order_by="time asc",
	)

	per_day: dict[date, list[dict]] = defaultdict(list)
	for row in rows:
		dt = get_datetime(row.time)
		per_day[dt.date()].append({"time": dt, "log_type": (row.log_type or "").upper()})

	stats_by_shift: dict[str, dict] = defaultdict(lambda: {"late_count": 0, "missing_count": 0, "settings": None})

	day = from_d
	while day <= to_d:
		day_rows = per_day.get(day, [])
		if not day_rows:
			day = add_days(day, 1)
			continue

		shift_type = _get_shift_type_for_day(employee, day)
		if not shift_type:
			day = add_days(day, 1)
			continue

		policy = _get_shift_policy(shift_type)
		if not policy:
			day = add_days(day, 1)
			continue

		stats = stats_by_shift[shift_type]
		stats["settings"] = policy

		in_rows = [r for r in day_rows if r["log_type"] == "IN"]
		out_rows = [r for r in day_rows if r["log_type"] == "OUT"]
		if not in_rows or not out_rows:
			stats["missing_count"] += 1

		if in_rows and _is_late(day, min(in_rows, key=lambda row: row["time"])["time"], policy):
			stats["late_count"] += 1

		day = add_days(day, 1)

	total_penalty = 0.0
	for shift_stats in stats_by_shift.values():
		policy = shift_stats["settings"] or {}
		shift_penalty = _compute_penalty_absent(
			late_count=int(shift_stats["late_count"] or 0),
			missing_count=int(shift_stats["missing_count"] or 0),
			lates_per_absent=int(policy.get("lates_per_absent") or 3),
			missing_per_absent=int(policy.get("missing_logs_per_absent") or 3),
		)
		if policy.get("convert_penalty_to_paid_leave"):
			continue
		total_penalty += shift_penalty

	return float(total_penalty)


def _compute_penalty_absent(
	late_count: int,
	missing_count: int,
	lates_per_absent: int,
	missing_per_absent: int,
) -> float:
	late_absents = math.floor(late_count / max(int(lates_per_absent or 1), 1))
	missing_absents = math.floor(missing_count / max(int(missing_per_absent or 1), 1))
	return float(late_absents + missing_absents)


def _is_late(day: date, first_in: datetime, policy: dict) -> bool:
	start_time = policy.get("start_time")
	if not start_time:
		return False

	grace_minutes = int(policy.get("grace_time_minutes") or 0)
	grace_dt = datetime.combine(day, start_time) + timedelta(minutes=grace_minutes)
	return get_datetime(first_in) > grace_dt


def _get_shift_type_for_day(employee: str, day: date) -> str | None:
	assignment = frappe.db.get_value(
		"Shift Assignment",
		{
			"employee": employee,
			"start_date": ["<=", day],
			"docstatus": 1,
		},
		["shift_type"],
		order_by="start_date desc",
		as_dict=True,
	)
	if assignment and assignment.shift_type:
		return assignment.shift_type

	return frappe.db.get_value("Employee", employee, "default_shift")


def _get_shift_policy(shift_type: str) -> dict | None:
	if not shift_type:
		return None

	row = frappe.db.get_value(
		"Shift Type",
		shift_type,
		[
			"start_time",
			"late_entry_grace_period",
			"zkteco_lates_per_absent",
			"zkteco_missing_logs_per_absent",
			"zkteco_convert_penalty_to_paid_leave",
			"zkteco_paid_leave_type",
		],
		as_dict=True,
	)
	if not row:
		return None

	return {
		"start_time": row.start_time,
		"grace_time_minutes": int(row.late_entry_grace_period or 0),
		"lates_per_absent": int(row.zkteco_lates_per_absent or 3),
		"missing_logs_per_absent": int(row.zkteco_missing_logs_per_absent or 3),
		"convert_penalty_to_paid_leave": int(row.zkteco_convert_penalty_to_paid_leave or 0),
		"paid_leave_type": row.zkteco_paid_leave_type,
	}
