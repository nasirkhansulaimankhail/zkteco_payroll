from __future__ import annotations

from datetime import datetime

import frappe
from frappe.utils import get_datetime, getdate, now_datetime

from zkteco_payroll.services.zkteco_client import ZKTecoConnectorError, fetch_punches


@frappe.whitelist()
def sync_attendance_logs() -> dict[str, int | str]:
	settings = _get_settings()
	if not settings.enable_zkteco_sync:
		return {"status": "disabled", "processed": 0}

	if not settings.machine_ip:
		frappe.throw("Machine IP is required in ZKTeco Payroll Settings")

	employee_by_device_id = {
		str(row.attendance_device_id): row.name
		for row in frappe.get_all(
			"Employee",
			filters={"status": "Active", "attendance_device_id": ["is", "set"]},
			fields=["name", "attendance_device_id"],
		)
	}
	employees_with_shift_assignments = set(
		frappe.get_all("Shift Assignment", filters={"docstatus": 1}, pluck="employee")
	)
	sync_from_date = getdate(settings.sync_from_date) if settings.sync_from_date else None

	processed = 0
	ignored = 0
	unmapped = 0
	unknown_state = 0
	ignored_before_sync_date = 0
	ignored_without_shift_assignment = 0

	try:
		punches = fetch_punches(
			ip=settings.machine_ip,
			port=int(settings.machine_port or 4370),
			password=settings.get_password("machine_password") or 0,
		)
	except ZKTecoConnectorError:
		frappe.log_error(frappe.get_traceback(), "ZKTeco Sync Failed")
		raise

	# Device logs may come without reliable IN/OUT states. Normalize to:
	# first punch of each employee/day => IN, then alternate OUT/IN/OUT...
	punches = _normalize_punch_states(punches)

	for punch in punches:
		if sync_from_date and getdate(punch.log_time) < sync_from_date:
			ignored_before_sync_date += 1
			continue

		employee = employee_by_device_id.get(str(punch.machine_user_id or "").strip())
		if not employee:
			unmapped += 1
			continue

		if employee not in employees_with_shift_assignments:
			ignored_without_shift_assignment += 1
			continue

		checkin_name = _create_employee_checkin_if_missing(
			employee=employee,
			log_time=punch.log_time,
			punch_state=punch.punch_state,
			device_id=settings.checkin_device_id or "ZKTeco",
		)
		if checkin_name == "unknown_state":
			unknown_state += 1
			continue
		if checkin_name:
			processed += 1
		else:
			ignored += 1

	frappe.db.set_single_value("ZKTeco Payroll Settings", "last_sync_at", now_datetime())
	frappe.db.commit()
	return {
		"status": "ok",
		"processed": processed,
		"ignored": ignored,
		"unmapped": unmapped,
		"unknown_state": unknown_state,
		"ignored_before_sync_date": ignored_before_sync_date,
		"ignored_without_shift_assignment": ignored_without_shift_assignment,
	}


def _create_employee_checkin_if_missing(
	employee: str,
	log_time: datetime,
	punch_state: str,
	device_id: str,
) -> str | None:
	log_type = "IN" if punch_state == "IN" else "OUT" if punch_state == "OUT" else None
	if not log_type:
		return "unknown_state"

	checkin_time = get_datetime(log_time)
	if frappe.db.exists(
		"Employee Checkin",
		{
			"employee": employee,
			"time": checkin_time,
			"log_type": log_type,
		},
	):
		return None

	checkin = frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": employee,
			"time": checkin_time,
			"log_type": log_type,
			"device_id": device_id,
		}
	)
	checkin.insert(ignore_permissions=True)
	return checkin.name


def _get_settings():
	return frappe.get_cached_doc("ZKTeco Payroll Settings")


def _normalize_punch_states(punches):
	grouped: dict[tuple[str, str], list] = {}
	for punch in punches or []:
		user_id = str(getattr(punch, "machine_user_id", "") or "").strip()
		log_dt = get_datetime(getattr(punch, "log_time", None))
		if not user_id or not log_dt:
			continue
		key = (user_id, str(log_dt.date()))
		grouped.setdefault(key, []).append(punch)

	for day_punches in grouped.values():
		day_punches.sort(key=lambda p: get_datetime(p.log_time))
		for idx, punch in enumerate(day_punches):
			punch.punch_state = "IN" if idx % 2 == 0 else "OUT"

	normalized = [p for rows in grouped.values() for p in rows]
	normalized.sort(key=lambda p: (str(p.machine_user_id or ""), get_datetime(p.log_time)))
	return normalized
