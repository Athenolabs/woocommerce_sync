# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "woocommerce_sync"
app_title = "Woocommerce Sync"
app_publisher = "Jigar Tarpara"
app_description = "Sync Product and Order between ERPNext- Woocommerce"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "tarparatechnologies@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/woocommerce_sync/css/woocommerce_sync.css"
# app_include_js = "/assets/woocommerce_sync/js/woocommerce_sync.js"

# include js, css files in header of web template
# web_include_css = "/assets/woocommerce_sync/css/woocommerce_sync.css"
# web_include_js = "/assets/woocommerce_sync/js/woocommerce_sync.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "woocommerce_sync.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "woocommerce_sync.install.before_install"
# after_install = "woocommerce_sync.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "woocommerce_sync.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"woocommerce_sync.tasks.all"
# 	],
# 	"daily": [
# 		"woocommerce_sync.tasks.daily"
# 	],
# 	"hourly": [
# 		"woocommerce_sync.tasks.hourly"
# 	],
# 	"weekly": [
# 		"woocommerce_sync.tasks.weekly"
# 	]
# 	"monthly": [
# 		"woocommerce_sync.tasks.monthly"
# 	]
# }
scheduler_events = {
	"hourly": [
		"woocommerce_sync.api.sync_woocommerce"
	],
	# "daily": [
	# 	"woocommerce_sync.billing.send_payment_notification_to_user"
	# ]
}
# Testing
# -------

# before_tests = "woocommerce_sync.install.before_tests"

# Overriding Whitelisted Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "woocommerce_sync.event.get_events"
# }

