from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def after_install():
	create_custom_field('Item', {
		'label': _('Sync Quantity With Shopify'),
		'fieldname': 'sync_qty_with_woocommerce',
		'fieldtype': 'Check',
		'insert_after': 'item_code'
	})
	create_custom_field('Item', {
		'label': _('Fetch Customer from Sales Inquiry'),
		'fieldname': 'fetch_customer_frm_si',
		'fieldtype': 'Button',
		'depends_on':'eval:doc.contact_no_car_sales',
		'insert_after': 'contact_no_car_sales'
	})
	create_custom_field('Item', {
		'label': _('Sales Inquiry'),
		'fieldname': 'sales_inquiry',
		'fieldtype': 'Link',
		'options': 'Sales Inquiry',
		'insert_after': 'customer'
	})
	create_custom_field('Item', {
		'label': _('Fetch Customer from Sales Inquiry'),
		'fieldname': 'fetch_customer_frm_si',
		'fieldtype': 'Button',
		'depends_on':'eval:doc.sales_inquiry',
		'insert_after': 'sales_inquiry'
	})