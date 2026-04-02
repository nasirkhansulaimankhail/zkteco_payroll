import frappe


@frappe.whitelist()
def get_context(context):
	return context
