from __future__ import unicode_literals
import frappe
from frappe import _
import json, math, time, pytz, requests
from .exceptions import WoocommerceError
from frappe.utils import get_request_session, get_datetime, get_time_zone
from woocommerce import API


def check_api_call_limit(response):
	"""
		This article will show you how to tell your program to take small pauses
		to keep your app a few API calls shy of the API call limit and
		to guard you against a 429 - Too Many Requests error.

		ref : https://docs.woocommerce.com/api/introduction/api-call-limit
	"""
	if response.headers.get("HTTP_X_woocommerce_SHOP_API_CALL_LIMIT") == 39:
		time.sleep(10)    # pause 10 seconds

def get_woocommerce_settings():
	d = frappe.get_doc("Woocommerce Sync Settings")
	
	if d.woocommerce_url:
		d.password = d.get_password(fieldname='password')
		return d.as_dict()
	
	else:
		frappe.throw(_("woocommerce store URL is not configured on woocommerce Settings"), WoocommerceError)

def get_request(path, settings=None):
	if not settings:
		settings = get_woocommerce_settings()

	wcapi = API(
		url=settings['woocommerce_url'],
		consumer_key=settings['api_key'],
		consumer_secret=settings['password'],
		# verify_ssl=settings['verify_ssl'],
		wp_api=True,
		version="wc/v3"
	)
	r = wcapi.get(path)
	
	r.raise_for_status()
	return r.json()

def post_request(path, data, settings=None):
	if not settings:
		settings = get_woocommerce_settings()
	wcapi = API(
		url=settings['woocommerce_url'],
		consumer_key=settings['api_key'],
		consumer_secret=settings['password'],
		verify_ssl=True,
		wp_api=True,
		version="wc/v3",
		queryStringAuth= True
	)
	print(
		(url=settings['woocommerce_url'],
		consumer_key=settings['api_key'],
		consumer_secret=settings['password'],
		verify_ssl=True,
		wp_api=True,
		version="wc/v3",
		queryStringAuth= True)
	)
	print(path)
	print(data)
	try:
		r = wcapi.post(path, data)
		r.raise_for_status()
		print(r.json())
	except requests.exceptions.HTTPError, e:
		make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
				request_data=item, exception=True)

	return r.json()

def put_request(path, data, settings=None):
	if not settings:
		settings = get_woocommerce_settings()

	wcapi = API(
		url=settings['woocommerce_url'],
		consumer_key=settings['api_key'],
		consumer_secret=settings['password'],
		wp_api=True,
		version="wc/v3"
	)
	r = wcapi.put(path, data)
	
	r.raise_for_status()
	return r.json()

def delete_request(path, settings=None):
	if not settings:
		settings = get_woocommerce_settings()

	wcapi = API(
		url=settings['woocommerce_url'],
		consumer_key=settings['api_key'],
		consumer_secret=settings['password'],
		wp_api=True,
		version="wc/v3"
	)
	r = wcapi.delete(path)
	
	r.raise_for_status()
	return r.json()

def get_woocommerce_url(path, settings):
	return '{}/{}'.format(settings['woocommerce_url'], path)

def get_header(settings):
	header = {'Content-Type': 'application/json'}

	# if settings['app_type'] == "Private":
	# 	return header
	# else:
	# 	header["X-woocommerce-Access-Token"] = settings['access_token']
	return header

def get_filtering_condition():
	woocommerce_settings = get_woocommerce_settings()
	if woocommerce_settings.last_sync_datetime:

		last_sync_datetime = get_datetime(woocommerce_settings.last_sync_datetime)
		timezone = pytz.timezone(get_time_zone())
		timezone_abbr = timezone.localize(last_sync_datetime, is_dst=False)

		return 'updated_at_min="{0} {1}"'.format(last_sync_datetime.strftime("%Y-%m-%d %H:%M:%S"), timezone_abbr.tzname())
	return ''

def get_total_pages(resource, ignore_filter_conditions=False):
	filter_condition = ""

	if not ignore_filter_conditions:
		filter_condition = get_filtering_condition()
	
	count = get_request('/admin/{0}&{1}'.format(resource, filter_condition))
	return int(math.ceil(count.get('count', 0) / 250))

def get_country():
	return get_request('/admin/countries.json')['countries']

def get_woocommerce_items(ignore_filter_conditions=False):
	woocommerce_products = []

	filter_condition = ''
	if not ignore_filter_conditions:
		filter_condition = get_filtering_condition()

	for page_idx in xrange(0, get_total_pages("products/count.json?", ignore_filter_conditions) or 1):
		woocommerce_products.extend(get_request('/admin/products.json?limit=250&page={0}&{1}'.format(page_idx+1,
			filter_condition))['products'])

	return woocommerce_products

def get_woocommerce_item_image(woocommerce_product_id):
	return get_request("/admin/products/{0}/images.json".format(woocommerce_product_id))["images"]

def get_woocommerce_orders(ignore_filter_conditions=False):
	woocommerce_orders = []

	filter_condition = ''

	if not ignore_filter_conditions:
		filter_condition = get_filtering_condition()

	for page_idx in xrange(0, get_total_pages("orders/count.json?status=any", ignore_filter_conditions) or 1):
		woocommerce_orders.extend(get_request('/admin/orders.json?status=any&limit=250&page={0}&{1}'.format(page_idx+1,
			filter_condition))['orders'])
	return woocommerce_orders

def get_woocommerce_customers(ignore_filter_conditions=False):
	woocommerce_customers = []

	filter_condition = ''

	if not ignore_filter_conditions:
		filter_condition = get_filtering_condition()

	for page_idx in xrange(0, get_total_pages("customers/count.json?", ignore_filter_conditions) or 1):
		woocommerce_customers.extend(get_request('/admin/customers.json?limit=250&page={0}&{1}'.format(page_idx+1,
			filter_condition))['customers'])
	return woocommerce_customers