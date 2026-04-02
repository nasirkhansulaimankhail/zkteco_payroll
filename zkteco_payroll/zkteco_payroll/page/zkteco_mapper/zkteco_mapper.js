frappe.pages["zkteco-mapper"].on_page_load = function (wrapper) {
	new ZKTecoMapperPage(wrapper);
};

class ZKTecoMapperPage {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("ZKTeco Mapper"),
			single_column: true,
		});
		this.rows = [];
		this.employees = [];
		this.make();
	}

	make() {
		this.page.set_primary_action(__("Save Selected Mappings"), () => this.createMappings());
		this.page.add_action_item(__("Refresh"), () => this.loadSuggestions());

		this.$body = $(
			`<div class="p-3">
				<p class="text-muted">
					${__("Map ZKTeco machine users to ERPNext Employees by writing Employee Attendance Device ID.")}
				</p>
				<div class="zkteco-mapper-table mt-3"></div>
			</div>`,
		).appendTo(this.page.main);

		this.loadData();
	}

	loadData() {
		frappe.call({
			method: "zkteco_payroll.services.mapping.get_active_employees",
			args: { limit: 5000 },
			callback: (r) => {
				this.employees = r.message || [];
				this.loadSuggestions();
			},
		});
	}

	loadSuggestions() {
		frappe.call({
			method: "zkteco_payroll.services.mapping.get_mapping_suggestions",
			args: { limit: 1000 },
			freeze: true,
			freeze_message: __("Loading device users..."),
			callback: (r) => {
				this.rows = (r.message || []).map((row) => ({
					...row,
					employee: row.mapped_employee || row.suggested_employee || "",
				}));
				this.renderTable();
			},
		});
	}

	renderTable() {
		const $tableHost = this.$body.find(".zkteco-mapper-table");
		$tableHost.empty();

		if (!this.rows.length) {
			$tableHost.html(
				`<div class="text-muted">${__("No users found on device. Check machine IP/port/password in settings.")}</div>`,
			);
			return;
		}

		const employeeOptions = [
			`<option value="">${__("Select Employee")}</option>`,
			...this.employees.map((emp) => {
				const parts = [emp.employee_name || emp.name, emp.name];
				if (emp.employee_number) {
					parts.push(emp.employee_number);
				}
				return `<option value="${frappe.utils.escape_html(emp.name)}">${frappe.utils.escape_html(parts.join(" | "))}</option>`;
			}),
		].join("");

		const rowsHtml = this.rows
			.map((row, idx) => {
				const mappedLabel = row.mapped_employee
					? `${row.mapped_employee_name || row.mapped_employee} (${row.mapped_employee})`
					: "-";
				return `
				<tr>
					<td>${frappe.utils.escape_html(row.machine_user_id || "")}</td>
					<td>${frappe.utils.escape_html(row.machine_username || "")}</td>
					<td>${frappe.utils.escape_html(mappedLabel)}</td>
					<td>
						<select class="form-control mapper-employee" data-idx="${idx}">
							${employeeOptions}
						</select>
					</td>
					<td>${frappe.utils.escape_html(row.matched_on || "")}</td>
				</tr>`;
			})
			.join("");

		$tableHost.html(
			`<table class="table table-bordered">
				<thead>
					<tr>
						<th>${__("Machine User ID")}</th>
						<th>${__("ZKTeco Username")}</th>
						<th>${__("Current Employee")}</th>
						<th>${__("Map To Employee")}</th>
						<th>${__("Matched On")}</th>
					</tr>
				</thead>
				<tbody>${rowsHtml}</tbody>
			</table>`,
		);

		$tableHost.find(".mapper-employee").each((_, el) => {
			const idx = Number($(el).attr("data-idx"));
			$(el).val(this.rows[idx].employee || "");
		});

		$tableHost.find(".mapper-employee").on("change", (e) => {
			const idx = Number($(e.currentTarget).attr("data-idx"));
			this.rows[idx].employee = $(e.currentTarget).val();
		});
	}

	createMappings() {
		const selectedRows = this.rows.filter((row) => row.employee);
		if (!selectedRows.length) {
			frappe.show_alert({ message: __("Select at least one employee mapping"), indicator: "orange" });
			return;
		}

		frappe.call({
			method: "zkteco_payroll.services.mapping.create_mappings_from_suggestions",
			args: {
				rows: selectedRows,
				overwrite: 1,
			},
			freeze: true,
			freeze_message: __("Saving mappings..."),
			callback: (r) => {
				const out = r.message || {};
				frappe.msgprint(
					__("Created: {0}, Updated: {1}, Skipped: {2}", [out.created || 0, out.updated || 0, out.skipped || 0]),
				);
				this.loadSuggestions();
			},
		});
	}
}
