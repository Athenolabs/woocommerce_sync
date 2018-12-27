// Copyright (c) 2018, Jigar Tarpara and contributors
// For license information, please see license.txt
frappe.provide("woocommerce_sync.woocommerce_sync_settings");

// frappe.ui.form.on('Woocommerce Sync Settings', {
// 	refresh: function(frm) {

// 	}
// });


frappe.ui.form.on("Woocommerce Sync Settings", "onload", function(frm, dt, dn){
	frappe.call({
		method:"woocommerce_sync.woocommerce_sync.doctype.woocommerce_sync_settings.woocommerce_sync_settings.get_series",
		callback:function(r){
			$.each(r.message, function(key, value){
				set_field_options(key, value)
			})
		}
	})
	woocommerce_sync.woocommerce_sync_settings.setup_queries(frm);
})

frappe.ui.form.on("Woocommerce Sync Settings", "app_type", function(frm, dt, dn) {
	frm.toggle_reqd("api_key", (frm.doc.app_type == "Private"));
	frm.toggle_reqd("password", (frm.doc.app_type == "Private"));
})

frappe.ui.form.on("Woocommerce Sync Settings", "refresh", function(frm){
	if(!frm.doc.__islocal && frm.doc.enable_woocommerce === 1){
		frm.toggle_reqd("price_list", true);
		frm.toggle_reqd("warehouse", true);
		frm.toggle_reqd("taxes", true);
		frm.toggle_reqd("company", true);
		frm.toggle_reqd("cost_center", true);
		frm.toggle_reqd("cash_bank_account", true);
		frm.toggle_reqd("sales_order_series", true);
		frm.toggle_reqd("customer_group", true);
		
		frm.toggle_reqd("sales_invoice_series", frm.doc.sync_sales_invoice);
		frm.toggle_reqd("delivery_note_series", frm.doc.sync_delivery_note);

		frm.add_custom_button(__('Sync woocommerce'), function() {
			frappe.call({
				method:"woocommerce_sync.api.sync_woocommerce",
			})
		}).addClass("btn-primary");
	}

	if(!frm.doc.access_token && !frm.doc.api_key) {
		frm.add_custom_button(__("Connect to woocommerce"),
			function(){
				window.open("https://apps.woocommerce.com/erpnext");
			}).addClass("btn-primary")
	}

	frm.add_custom_button(__("Woocommerce Log"), function(){
		frappe.set_route("List", "Woocommerce Log");
	})
	
	frm.add_custom_button(__("Reset Last Sync Date"), function(){
		var dialog = new frappe.ui.Dialog({
			title: __("Reset Last Sync Date"),
			fields: [
				{"fieldtype": "Datetime", "label": __("Date"), "fieldname": "last_sync_date", "reqd": 1 },
				{"fieldtype": "Button", "label": __("Set last sync date"), "fieldname": "set_last_sync_date", "cssClass": "btn-primary"},
			]
		});
		var args;
		dialog.fields_dict.set_last_sync_date.$input.click(function() {
			args = dialog.get_values();
			if(!args) return;

			frm.set_value("last_sync_datetime", args['last_sync_date']);
			frm.save();

			dialog.hide();
		});
		dialog.show();
	})


	frappe.call({
		method: "woocommerce_sync.api.get_log_status",
		callback: function(r) {
			if(r.message){
				frm.dashboard.set_headline_alert(r.message.text, r.message.alert_class)
			}
		}
	})

})


$.extend(woocommerce_sync.woocommerce_sync_settings, {
	setup_queries: function(frm) {
		frm.fields_dict["warehouse"].get_query = function(doc) {
			return {
				filters:{
					"company": doc.company,
					"is_group": "No"
				}
			}
		}

		frm.fields_dict["taxes"].grid.get_field("tax_account").get_query = function(doc, dt, dn){
			return {
				"query": "erpnext.controllers.queries.tax_account_query",
				"filters": {
					"account_type": ["Tax", "Chargeable", "Expense Account"],
					"company": doc.company
				}
			}
		}

		frm.fields_dict["cash_bank_account"].get_query = function(doc) {
			return {
				filters: [
					["Account", "account_type", "in", ["Cash", "Bank"]],
					["Account", "root_type", "=", "Asset"],
					["Account", "is_group", "=",0],
					["Account", "company", "=", doc.company]
				]
			}
		}

		frm.fields_dict["cost_center"].get_query = function(doc) {
			return {
				filters:{
					"company": doc.company,
					"is_group": "No"
				}
			}
		}

		frm.fields_dict["price_list"].get_query = function(doc) {
			return {
				filters:{
					"selling": 1
				}
			}
		}
	}
})
