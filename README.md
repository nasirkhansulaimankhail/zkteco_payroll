### ZKTeco Payroll (Frappe/ERPNext/HRMS v15)

ZKTeco attendance integration app built to work with:

- `frappe` branch: `version-15`
- `erpnext` branch: `version-15`
- `hrms` branch: `version-15`

### Features

- Fetches biometric logs from ZKTeco device (`pyzk`)
- Maps device users to ERPNext Employees via `Employee.attendance_device_id`
- Creates attendance in native `Employee Checkin`
- Supports 5-minute scheduled sync
- Supports sync cutoff date (`Sync Logs From Date`)
- Creates checkins only for employees with submitted `Shift Assignment`
- Uses Shift policy fields for lateness/missing-log penalties
- Supports hourly payroll from Employee-level fields
- Includes:
  - `Employee Hours Variance` Script Report
  - `ZKTeco Attendance History` Desk Page

### Installation on v15 bench

```bash
# Bench with frappe/erpnext/hrms on version-15
bench --site <your-site> install-app zkteco_payroll
bench --site <your-site> migrate
```

### Required Apps

- `erpnext`
- `hrms`

### Python Compatibility

- `>=3.10,<3.13`

### Notes

- Device credentials are stored in `ZKTeco Payroll Settings`.
- IN/OUT states are normalized per employee/day as alternating sequence starting with `IN`.

### License

mit
