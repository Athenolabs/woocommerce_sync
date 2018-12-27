from __future__ import unicode_literals
import frappe

class WoocommerceError(frappe.ValidationError): pass
class WoocommerceSetupError(frappe.ValidationError): pass