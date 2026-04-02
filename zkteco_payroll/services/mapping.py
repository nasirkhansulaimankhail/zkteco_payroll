from __future__ import annotations

import json

import frappe

from zkteco_payroll.services.zkteco_client import (
	ZKTecoConnectorError,
	fetch_device_users,
)


@frappe.whitelist()
def get_active_employees(limit: int = 2000) -> list[dict]:
	limit = max(1, min(int(limit or 2000), 5000))
	return frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "employee_number", "attendance_device_id"],
		order_by="employee_name asc",
		limit=limit,
	)


@frappe.whitelist()
def get_mapping_suggestions(limit: int = 500) -> list[dict]:
	limit = max(1, min(int(limit or 500), 5000))
	settings = frappe.get_cached_doc("ZKTeco Payroll Settings")
	if not settings.enable_zkteco_sync:
		return []
	if not settings.machine_ip:
		frappe.throw("Machine IP is required in ZKTeco Payroll Settings")

	try:
		device_users = fetch_device_users(
			ip=settings.machine_ip,
			port=int(settings.machine_port or 4370),
			password=settings.get_password("machine_password") or 0,
		)
	except ZKTecoConnectorError:
		frappe.log_error(frappe.get_traceback(), "ZKTeco Mapper Fetch Users Failed")
		raise

	mapped = {
		row.attendance_device_id: {
			"employee": row.name,
			"employee_name": row.employee_name,
			"employee_number": row.employee_number,
		}
		for row in frappe.get_all(
			"Employee",
			filters={"status": "Active", "attendance_device_id": ["is", "set"]},
			fields=["name", "employee_name", "employee_number", "attendance_device_id"],
		)
	}

	rows: list[dict] = []
	for user in device_users[:limit]:
		machine_user_id = str(user.machine_user_id or "").strip()
		if not machine_user_id:
			continue

		existing = mapped.get(machine_user_id)
		suggested_employee, matched_on = _guess_employee(machine_user_id, user.username)
		rows.append(
			{
				"machine_user_id": machine_user_id,
				"machine_username": user.username or "",
				"mapped_employee": existing.get("employee") if existing else None,
				"mapped_employee_name": existing.get("employee_name") if existing else None,
				"suggested_employee": suggested_employee,
				"matched_on": matched_on,
			}
		)

	rows.sort(key=lambda row: (0 if not row.get("mapped_employee") else 1, row.get("machine_user_id") or ""))
	return rows


@frappe.whitelist()
def create_mappings_from_suggestions(rows: str | list[dict], overwrite: int = 0) -> dict[str, int]:
	if isinstance(rows, str):
		rows = json.loads(rows)

	overwrite = int(overwrite or 0)
	created = 0
	updated = 0
	skipped = 0

	for row in rows or []:
		machine_user_id = str((row or {}).get("machine_user_id") or "").strip()
		employee = str((row or {}).get("employee") or (row or {}).get("suggested_employee") or "").strip()
		if not machine_user_id or not employee:
			skipped += 1
			continue

		if not frappe.db.exists("Employee", {"name": employee, "status": "Active"}):
			skipped += 1
			continue

		current_device_id = frappe.db.get_value("Employee", employee, "attendance_device_id")
		if current_device_id and str(current_device_id) != machine_user_id and not overwrite:
			skipped += 1
			continue

		owner_employee = frappe.db.get_value(
			"Employee",
			{"attendance_device_id": machine_user_id, "status": "Active"},
			"name",
		)
		if owner_employee and owner_employee != employee:
			if not overwrite:
				skipped += 1
				continue
			frappe.db.set_value("Employee", owner_employee, "attendance_device_id", None, update_modified=False)

		action = "created" if not current_device_id else "updated"
		frappe.db.set_value("Employee", employee, "attendance_device_id", machine_user_id)
		if action == "created":
			created += 1
		else:
			updated += 1

	frappe.db.commit()
	return {"created": created, "updated": updated, "skipped": skipped}


def _guess_employee(machine_user_id: str, machine_username: str | None) -> tuple[str | None, str | None]:
	employee = frappe.db.get_value("Employee", {"attendance_device_id": machine_user_id, "status": "Active"}, "name")
	if employee:
		return employee, "attendance_device_id"

	employee = frappe.db.get_value("Employee", {"employee_number": machine_user_id, "status": "Active"}, "name")
	if employee:
		return employee, "employee_number"

	employee = frappe.db.get_value("Employee", {"name": machine_user_id, "status": "Active"}, "name")
	if employee:
		return employee, "employee"

	if machine_username:
		employee = frappe.db.get_value("Employee", {"employee_name": machine_username, "status": "Active"}, "name")
		if employee:
			return employee, "employee_name"

	return None, None
