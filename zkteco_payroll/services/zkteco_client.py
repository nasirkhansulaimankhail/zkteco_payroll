from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import frappe


@dataclass
class PunchLog:
	machine_user_id: str
	log_time: datetime
	punch_state: str
	source_device: str


@dataclass
class DeviceUser:
	machine_user_id: str
	username: str


class ZKTecoConnectorError(frappe.ValidationError):
	pass


def fetch_punches(ip: str, port: int, password: str | int | None, timeout: int = 10) -> list[PunchLog]:
	"""Fetch attendance punches from a ZKTeco machine using pyzk."""
	conn = _connect(ip=ip, port=port, password=password, timeout=timeout)
	try:
		attendance = conn.get_attendance() or []
		device_name = getattr(conn, "get_device_name", lambda: "ZKTeco")()
		logs: list[PunchLog] = []
		for row in attendance:
			machine_user_id = str(getattr(row, "user_id", "") or "").strip()
			log_time = getattr(row, "timestamp", None)
			status = getattr(row, "status", None)
			if not machine_user_id or not isinstance(log_time, datetime):
				continue
			logs.append(
				PunchLog(
					machine_user_id=machine_user_id,
					log_time=log_time,
					punch_state=_map_status_to_state(status),
					source_device=str(device_name or "ZKTeco"),
				)
			)
		return logs
	finally:
		_disconnect(conn)


def fetch_device_users(ip: str, port: int, password: str | int | None, timeout: int = 10) -> list[DeviceUser]:
	"""Fetch registered users from ZKTeco device (for mapping UI)."""
	conn = _connect(ip=ip, port=port, password=password, timeout=timeout)
	try:
		users = conn.get_users() or []
		rows: list[DeviceUser] = []
		for row in users:
			machine_user_id = str(getattr(row, "user_id", "") or "").strip()
			username = str(getattr(row, "name", "") or "").strip()
			if not machine_user_id:
				continue
			rows.append(DeviceUser(machine_user_id=machine_user_id, username=username))
		return rows
	finally:
		_disconnect(conn)


def _connect(ip: str, port: int, password: str | int | None, timeout: int):
	try:
		from zk import ZK
	except ImportError as exc:
		raise ZKTecoConnectorError(
			"Missing dependency `pyzk`. Install it in bench env: pip install pyzk"
		) from exc

	zk_client = ZK(ip, port=port, timeout=timeout, password=int(password or 0), force_udp=False, ommit_ping=True)
	conn = None
	try:
		conn = zk_client.connect()
		conn.disable_device()
		return conn
	except Exception as exc:
		raise ZKTecoConnectorError(f"Unable to connect to ZKTeco ({ip}:{port}): {exc}") from exc


def _disconnect(conn):
	if not conn:
		return
	try:
		conn.enable_device()
	except Exception:
		pass
	try:
		conn.disconnect()
	except Exception:
		pass


def _map_status_to_state(status: int | None) -> str:
	if status == 0:
		return "IN"
	if status == 1:
		return "OUT"
	return "UNKNOWN"
