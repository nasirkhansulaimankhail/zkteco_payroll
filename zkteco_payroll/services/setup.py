from __future__ import annotations

import frappe


@frappe.whitelist()
def bootstrap_defaults(ip: str, port: int = 4370, password: str = "0"):
	settings = frappe.get_doc("ZKTeco Payroll Settings")
	settings.machine_ip = ip
	settings.machine_port = int(port or 4370)
	settings.machine_password = str(password or "0")
	settings.enable_zkteco_sync = 1
	settings.auto_create_employee_checkin = 1
	settings.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "ok"}
