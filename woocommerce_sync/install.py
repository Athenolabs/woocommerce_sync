from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe import _
import frappe
@frappe.whitelist()
def after_install():
	create_custom_field('Item', {
		'label': _('Sync Quantity With Woocommerce Sync'),
		'fieldname': 'sync_qty_with_woocommerce_sync',
		'fieldtype': 'Check',
		'insert_after': 'item_code'
	})
	create_custom_field('Item', {
		'label': _('Sync Variant Id'),
		'fieldname': 'woocommerce_sync_variant_id',
		'fieldtype': 'Data',
		'insert_after': 'sync_qty_with_woocommerce_sync'
	})
	create_custom_field('Item', {
		'label': _('Woocommerce Sync Product Id'),
		'fieldname': 'woocommerce_sync_product_id',
		'fieldtype': 'Data',
		'insert_after': 'woocommerce_sync_variant_id'
	})
	create_custom_field('Item', {
		'label': _('Sync With Woocommerce Sync'),
		'fieldname': 'sync_with_woocommerce_sync',
		'fieldtype': 'Check',
		'insert_after': 'is_stock_item'
	})
	create_custom_field('Item', {
		'label': _('Woocommerce Sync Description'),
		'fieldname': 'woocommerce_sync_description',
		'fieldtype': 'Text Editor',
		'insert_after': 'brand'
	})
	create_custom_field('Item', {
		'label': _('Default Supplier'),
		'fieldname': 'default_supplier_woocommerce_sync',
		'fieldtype': 'Link',
		'options': 'Supplier',
		'insert_after': 'manufacturer_part_no'
	})
	create_custom_field('Customer', {
		'label': _('Woocommerce Customer ID'),
		'fieldname': 'woocommerce_customer_id',
		'fieldtype': 'Data',
		'insert_after': 'customer_type'
	})
	