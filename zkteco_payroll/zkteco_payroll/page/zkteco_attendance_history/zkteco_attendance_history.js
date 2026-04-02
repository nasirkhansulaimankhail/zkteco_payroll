frappe.pages["zkteco-attendance-history"].on_page_load = function (wrapper) {
	new ZKTecoAttendanceHistoryPage(wrapper);
};

class ZKTecoAttendanceHistoryPage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("ZKTeco Attendance History"),
			single_column: true,
		});
		this.rows = [];
		this.make();
	}

	make() {
		this.employeeField = this.page.add_field({
			label: __("Employee"),
			fieldname: "employee",
			fieldtype: "Link",
			options: "Employee",
			reqd: 1,
		});
		this.fromDateField = this.page.add_field({
			label: __("From Date"),
			fieldname: "from_date",
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		});
		this.toDateField = this.page.add_field({
			label: __("To Date"),
			fieldname: "to_date",
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		});

		this.page.set_primary_action(__("Load History"), () => this.loadHistory());

		this.$body = $(
			`<div class="p-3">
				<p class="text-muted">${__("Select employee and date range to view daily attendance history and hours variance.")}</p>
				<div class="zkteco-attendance-history-table mt-3"></div>
			</div>`,
		).appendTo(this.page.main);
	}

	loadHistory() {
		const employee = this.employeeField.get_value();
		const from_date = this.fromDateField.get_value();
		const to_date = this.toDateField.get_value();

		if (!employee || !from_date || !to_date) {
			frappe.show_alert({ message: __("Employee and date range are required"), indicator: "orange" });
			return;
		}

		frappe.call({
			method: "zkteco_payroll.services.attendance_analytics.get_employee_attendance_history",
			args: { employee, from_date, to_date },
			freeze: true,
			freeze_message: __("Loading attendance history..."),
			callback: (r) => {
				this.rows = r.message || [];
				this.renderTable();
			},
		});
	}

	renderTable() {
		const $host = this.$body.find(".zkteco-attendance-history-table");
		$host.empty();

		if (!this.rows.length) {
			$host.html(`<div class="text-muted">${__("No data found for selected filters.")}</div>`);
			return;
		}

		const rowsHtml = this.rows
			.map(
				(row) => `
				<tr>
					<td>${frappe.utils.escape_html(row.date || "")}</td>
					<td>${frappe.utils.escape_html(row.shift_type || "-")}</td>
					<td>${frappe.datetime.str_to_user(row.first_in || "") || "-"}</td>
					<td>${frappe.datetime.str_to_user(row.last_out || "") || "-"}</td>
					<td>${frappe.utils.escape_html((row.present_hours || 0).toString())}</td>
					<td>${frappe.utils.escape_html((row.expected_hours || 0).toString())}</td>
					<td>${frappe.utils.escape_html((row.short_hours || 0).toString())}</td>
					<td>${frappe.utils.escape_html((row.excess_hours || 0).toString())}</td>
				</tr>`,
			)
			.join("");

		$host.html(
			`<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("Date")}</th>
						<th>${__("Shift")}</th>
						<th>${__("First IN")}</th>
						<th>${__("Last OUT")}</th>
						<th>${__("Present Hours")}</th>
						<th>${__("Expected Hours")}</th>
						<th>${__("Short Hours")}</th>
						<th>${__("Excess Hours")}</th>
					</tr>
				</thead>
				<tbody>${rowsHtml}</tbody>
			</table>`,
		);
	}
}
