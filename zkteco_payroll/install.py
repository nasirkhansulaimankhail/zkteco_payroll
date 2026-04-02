from zkteco_payroll.services.custom_fields import ensure_custom_fields


def after_install():
	ensure_custom_fields()
