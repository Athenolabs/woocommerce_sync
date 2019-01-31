from __future__ import unicode_literals
import frappe
from frappe import _
import requests.exceptions
from .exceptions import WoocommerceError
from .utils import make_woocommerce_log, disable_woocommerce_sync_for_item
from erpnext.stock.utils import get_bin
from frappe.utils import cstr, flt, cint, get_files_path
from .woocommerce_requests import post_request, get_woocommerce_items, put_request, get_woocommerce_item_image
import base64, requests, datetime, os
from frappe.utils.background_jobs import enqueue
woocommerce_variants_attr_list = ["option1", "option2", "option3"]

def sync_products(price_list, warehouse):
	woocommerce_item_list = []
	# sync_woocommerce_items(warehouse, woocommerce_item_list)
	frappe.local.form_dict.count_dict["products"] = len(woocommerce_item_list)
	sync_erpnext_items(price_list, warehouse, woocommerce_item_list)

def sync_woocommerce_items(warehouse, woocommerce_item_list):
	for woocommerce_item in get_woocommerce_items():
		try:
			make_item(warehouse, woocommerce_item, woocommerce_item_list)

		except WoocommerceError as e:
			make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
				request_data=woocommerce_item, exception=True)

		except Exception as e:
			if e.args[0] and e.args[0].startswith("402"):
				raise e
			else:
				make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
					request_data=woocommerce_item, exception=True)

def make_item(warehouse, woocommerce_item, woocommerce_item_list):
	add_item_weight(woocommerce_item)
	if has_variants(woocommerce_item):
		attributes = create_attribute(woocommerce_item)
		create_item(woocommerce_item, warehouse, 1, attributes, woocommerce_item_list=woocommerce_item_list)
		create_item_variants(woocommerce_item, warehouse, attributes, woocommerce_variants_attr_list, woocommerce_item_list=woocommerce_item_list)

	else:
		woocommerce_item["variant_id"] = woocommerce_item['variants'][0]["id"]
		create_item(woocommerce_item, warehouse, woocommerce_item_list=woocommerce_item_list)

def add_item_weight(woocommerce_item):
	woocommerce_item["weight"] = woocommerce_item['variants'][0]["weight"]
	woocommerce_item["weight_unit"] = woocommerce_item['variants'][0]["weight_unit"]

def has_variants(woocommerce_item):
	if len(woocommerce_item.get("options")) >= 1 and "Default Title" not in woocommerce_item.get("options")[0]["values"]:
		return True
	return False

def create_attribute(woocommerce_item):
	attribute = []
	# woocommerce item dict
	for attr in woocommerce_item.get('options'):
		if not frappe.db.get_value("Item Attribute", attr.get("name"), "name"):
			frappe.get_doc({
				"doctype": "Item Attribute",
				"attribute_name": attr.get("name"),
				"item_attribute_values": [
					{
						"attribute_value": attr_value,
						"abbr":attr_value
					}
					for attr_value in attr.get("values")
				]
			}).insert()
			attribute.append({"attribute": attr.get("name")})

		else:
			# check for attribute values
			item_attr = frappe.get_doc("Item Attribute", attr.get("name"))
			if not item_attr.numeric_values:
				set_new_attribute_values(item_attr, attr.get("values"))
				item_attr.save()
				attribute.append({"attribute": attr.get("name")})

			else:
				attribute.append({
					"attribute": attr.get("name"),
					"from_range": item_attr.get("from_range"),
					"to_range": item_attr.get("to_range"),
					"increment": item_attr.get("increment"),
					"numeric_values": item_attr.get("numeric_values")
				})

	return attribute

def set_new_attribute_values(item_attr, values):
	for attr_value in values:
		if not any((d.abbr.lower() == attr_value.lower() or d.attribute_value.lower() == attr_value.lower())\
		for d in item_attr.item_attribute_values):
			item_attr.append("item_attribute_values", {
				"attribute_value": attr_value,
				"abbr": attr_value
			})

def create_item(woocommerce_item, warehouse, has_variant=0, attributes=None,variant_of=None, woocommerce_item_list=[]):
	item_dict = {
		"doctype": "Item",
		"woocommerce_sync_product_id": woocommerce_item.get("id"),
		"woocommerce_sync_variant_id": woocommerce_item.get("variant_id"),
		# "inventory_item_id" : new_item['product']["variants"][0].get("inventory_item_id")
		"variant_of": variant_of,
		"sync_with_woocommerce_sync": 1,
		"is_stock_item": 1,
		"item_code": cstr(woocommerce_item.get("item_code")) or cstr(woocommerce_item.get("id")),
		"item_name": woocommerce_item.get("title", '').strip(),
		"description": woocommerce_item.get("body_html") or woocommerce_item.get("title"),
		"woocommerce_sync_description": woocommerce_item.get("body_html") or woocommerce_item.get("title"),
		"item_group": get_item_group(woocommerce_item.get("product_type")),
		"has_variants": has_variant,
		"attributes":attributes or [],
		"stock_uom": woocommerce_item.get("uom") or _("Nos"),
		"stock_keeping_unit": woocommerce_item.get("sku") or get_sku(woocommerce_item),
		"default_warehouse": warehouse,
		"image": get_item_image(woocommerce_item),
		"weight_uom": woocommerce_item.get("weight_unit"),
		"weight_per_unit": woocommerce_item.get("weight"),
		"default_supplier_woocommerce_sync": get_supplier(woocommerce_item)
	}

	if not is_item_exists(item_dict, attributes, variant_of=variant_of, woocommerce_item_list=woocommerce_item_list):
		item_details = get_item_details(woocommerce_item)

		if not item_details:
			new_item = frappe.get_doc(item_dict)
			new_item.insert()
			name = new_item.name

		else:
			update_item(item_details, item_dict)
			name = item_details.name

		if not has_variant:
			add_to_price_list(woocommerce_item, name)

		frappe.db.commit()

def create_item_variants(woocommerce_item, warehouse, attributes, woocommerce_variants_attr_list, woocommerce_item_list):
	template_item = frappe.db.get_value("Item", filters={"woocommerce_sync_product_id": woocommerce_item.get("id")},
		fieldname=["name", "stock_uom"], as_dict=True)

	if template_item:
		for variant in woocommerce_item.get("variants"):
			woocommerce_item_variant = {
				"id" : variant.get("id"),
				"item_code": variant.get("id"),
				"title": variant.get("title"),
				"product_type": woocommerce_item.get("product_type"),
				"sku": variant.get("sku"),
				"uom": template_item.stock_uom or _("Nos"),
				"item_price": variant.get("price"),
				"variant_id": variant.get("id"),
				"weight_unit": variant.get("weight_unit"),
				"weight": variant.get("weight")
			}

			for i, variant_attr in enumerate(woocommerce_variants_attr_list):
				if variant.get(variant_attr):
					attributes[i].update({"attribute_value": get_attribute_value(variant.get(variant_attr), attributes[i])})
			create_item(woocommerce_item_variant, warehouse, 0, attributes, template_item.name, woocommerce_item_list=woocommerce_item_list)

def get_attribute_value(variant_attr_val, attribute):
	attribute_value = frappe.db.sql("""select attribute_value from `tabItem Attribute Value`
		where parent = %s and (abbr = %s or attribute_value = %s)""", (attribute["attribute"], variant_attr_val,
		variant_attr_val), as_list=1)
	return attribute_value[0][0] if len(attribute_value)>0 else cint(variant_attr_val)

def get_item_group(product_type=None):
	import frappe.utils.nestedset
	parent_item_group = frappe.utils.nestedset.get_root_of("Item Group")

	if product_type:
		if not frappe.db.get_value("Item Group", product_type, "name"):
			item_group = frappe.get_doc({
				"doctype": "Item Group",
				"item_group_name": product_type,
				"parent_item_group": parent_item_group,
				"is_group": "No"
			}).insert()
			return item_group.name
		else:
			return product_type
	else:
		return parent_item_group


def get_sku(item):
	if item.get("variants"):
		return item.get("variants")[0].get("sku")
	return ""

def add_to_price_list(item, name):
	woocommerce_settings = frappe.db.get_value("Woocommerce Sync Settings", None, ["price_list", "push_prices_to_woocommerce"], as_dict=1)
	if woocommerce_settings.push_prices_to_woocommerce:
		return

	item_price_name = frappe.db.get_value("Item Price",
		{"item_code": name, "price_list": woocommerce_settings.price_list}, "name")

	if not item_price_name:
		frappe.get_doc({
			"doctype": "Item Price",
			"price_list": woocommerce_settings.price_list,
			"item_code": name,
			"price_list_rate": item.get("item_price") or item.get("variants")[0].get("price")
		}).insert()
	else:
		item_rate = frappe.get_doc("Item Price", item_price_name)
		item_rate.price_list_rate = item.get("item_price") or item.get("variants")[0].get("price")
		item_rate.save()

def get_item_image(woocommerce_item):
	if woocommerce_item.get("image"):
		return woocommerce_item.get("image").get("src")
	return None

def get_supplier(woocommerce_item):
	if woocommerce_item.get("vendor"):
		supplier = frappe.db.sql("""select name from tabSupplier
			where name = %s or woocommerce_supplier_id = %s """, (woocommerce_item.get("vendor"),
			woocommerce_item.get("vendor").lower()), as_list=1)

		if not supplier:
			supplier = frappe.get_doc({
				"doctype": "Supplier",
				"supplier_name": woocommerce_item.get("vendor"),
				"woocommerce_supplier_id": woocommerce_item.get("vendor").lower(),
				"supplier_type": get_supplier_type()
			}).insert()
			return supplier.name
		else:
			return woocommerce_item.get("vendor")
	else:
		return ""

def get_supplier_type():
	supplier_type = frappe.db.get_value("Supplier Type", _("woocommerce Supplier"))
	if not supplier_type:
		supplier_type = frappe.get_doc({
			"doctype": "Supplier Type",
			"supplier_type": _("woocommerce Supplier")
		}).insert()
		return supplier_type.name
	return supplier_type

def get_item_details(woocommerce_item):
	item_details = {}

	item_details = frappe.db.get_value("Item", {"woocommerce_sync_product_id": woocommerce_item.get("id")},
		["name", "stock_uom", "item_name"], as_dict=1)

	if item_details:
		return item_details

	else:
		item_details = frappe.db.get_value("Item", {"woocommerce_sync_variant_id": woocommerce_item.get("id")},
			["name", "stock_uom", "item_name"], as_dict=1)
		return item_details

def is_item_exists(woocommerce_item, attributes=None, variant_of=None, woocommerce_item_list=[]):
	if variant_of:
		name = variant_of
	else:
		name = frappe.db.get_value("Item", {"item_name": woocommerce_item.get("item_name")})

	woocommerce_item_list.append(cstr(woocommerce_item.get("woocommerce_sync_product_id")))

	if name:
		item = frappe.get_doc("Item", name)
		item.flags.ignore_mandatory=True

		if not variant_of and not item.woocommerce_sync_product_id:
			item.woocommerce_sync_product_id = woocommerce_item.get("woocommerce_sync_product_id")
			item.woocommerce_sync_variant_id = woocommerce_item.get("woocommerce_sync_variant_id")
			item.inventory_item_id = woocommerce_item.get("inventory_item_id")
			item.save()
			return True

		if item.woocommerce_sync_product_id and attributes and attributes[0].get("attribute_value"):
			if not variant_of:
				variant_of = frappe.db.get_value("Item",
					{"woocommerce_sync_product_id": item.woocommerce_sync_product_id}, "variant_of")

			# create conditions for all item attributes,
			# as we are putting condition basis on OR it will fetch all items matching either of conditions
			# thus comparing matching conditions with len(attributes)
			# which will give exact matching variant item.

			conditions = ["(iv.attribute='{0}' and iv.attribute_value = '{1}')"\
				.format(attr.get("attribute"), attr.get("attribute_value")) for attr in attributes]

			conditions = "( {0} ) and iv.parent = it.name ) = {1}".format(" or ".join(conditions), len(attributes))

			parent = frappe.db.sql(""" select * from tabItem it where
				( select count(*) from `tabItem Variant Attribute` iv
					where {conditions} and it.variant_of = %s """.format(conditions=conditions) ,
				variant_of, as_list=1)

			if parent:
				variant = frappe.get_doc("Item", parent[0][0])
				variant.flags.ignore_mandatory = True

				variant.woocommerce_sync_product_id = woocommerce_item.get("woocommerce_sync_product_id")
				variant.woocommerce_sync_variant_id = woocommerce_item.get("woocommerce_sync_variant_id")
				variant.save()
			return False

		if item.woocommerce_sync_product_id and item.woocommerce_sync_product_id != woocommerce_item.get("woocommerce_sync_product_id"):
			return False

		return True

	else:
		return False

def update_item(item_details, item_dict):
	item = frappe.get_doc("Item", item_details.name)
	item_dict["stock_uom"] = item_details.stock_uom

	if item_dict.get("default_warehouse"):
		del item_dict["default_warehouse"]

	del item_dict["description"]
	del item_dict["item_code"]
	del item_dict["variant_of"]
	del item_dict["item_name"]
	del item_dict["image"]

	item.update(item_dict)
	item.flags.ignore_mandatory = True
	item.save()

def sync_erpnext_items(price_list, warehouse, woocommerce_item_list):
	for item in get_erpnext_items(price_list):
		if item.woocommerce_sync_product_id not in woocommerce_item_list:
			try:
				sync_item_with_woocommerce(item, price_list, warehouse)
				frappe.local.form_dict.count_dict["products"] += 1

			except WoocommerceError as e:
				make_woocommerce_log(title=e.message, status="Error", method="sync_erpnext_items", message=frappe.get_traceback(),
					request_data=item, exception=True)
			except Exception as e:
				make_woocommerce_log(title=e.message, status="Error", method="sync_erpnext_items", message=frappe.get_traceback(),
					request_data=item, exception=True)

def get_erpnext_items(price_list):
	erpnext_items = []
	woocommerce_settings = frappe.get_doc("Woocommerce Sync Settings", "Woocommerce Sync Settings")

	last_sync_condition, item_price_condition = "", ""
	if woocommerce_settings.last_sync_datetime:
		last_sync_condition = "and modified >= '{0}' ".format(woocommerce_settings.last_sync_datetime)
		item_price_condition = "and ip.modified >= '{0}' ".format(woocommerce_settings.last_sync_datetime)

	item_from_master = """select name, item_code, item_name, item_group,
		description, woocommerce_sync_description, has_variants, variant_of, stock_uom, image, woocommerce_sync_product_id, 
		woocommerce_sync_variant_id, sync_qty_with_woocommerce_sync, weight_per_unit, weight_uom, default_supplier_woocommerce_sync from tabItem
		where sync_with_woocommerce_sync=1 and (variant_of is null or variant_of = '')
		and (disabled is null or disabled = 0)  %s """ % last_sync_condition

	erpnext_items.extend(frappe.db.sql(item_from_master, as_dict=1))

	template_items = [item.name for item in erpnext_items if item.has_variants]

	if len(template_items) > 0:
		item_price_condition += ' and i.variant_of not in (%s)'%(' ,'.join(["'%s'"]*len(template_items)))%tuple(template_items)

	item_from_item_price = """select i.name, i.item_code, i.item_name, i.item_group, i.description,
		i.woocommerce_sync_description, i.has_variants, i.variant_of, i.stock_uom, i.image, i.woocommerce_sync_product_id,
		i.woocommerce_sync_variant_id, i.sync_qty_with_woocommerce_sync, i.weight_per_unit, i.weight_uom,
		i.default_supplier_woocommerce_sync from `tabItem` i, `tabItem Price` ip
		where price_list = '%s' and i.name = ip.item_code
			and sync_with_woocommerce_sync=1 and (disabled is null or disabled = 0) %s""" %(price_list, item_price_condition)

	updated_price_item_list = frappe.db.sql(item_from_item_price, as_dict=1)

	# to avoid item duplication
	return [frappe._dict(tupleized) for tupleized in set(tuple(item.items())
		for item in erpnext_items + updated_price_item_list)]

def sync_item_with_woocommerce(item, price_list, warehouse):
	variant_item_name_list = []
	variant_list = []
	item_data = {
		"name": item.get("item_name"),
		"description": item.get("woocommerce_sync_description") or item.get("web_long_description") or item.get("description"),
		"short_description": item.get("web_long_description") or item.get("description"),
		"manage_stock":item.get("sync_qty_with_woocommerce_sync"),
		"images":[],
	}
	item_data.update( get_price_and_stock_details(item, warehouse, price_list) )
	if item.get("variant_of"):
		parent_item_sync = frappe.get_doc("Item", item.get("variant_of"))
		if not parent_item_sync.get("woocommerce_sync_product_id"):
			return
		create_or_update_varient_to_woocommerce()
	elif item.get("has_variants"):
		item_data["type"] = "variable"
		if item.get("variant_of"):
			item = frappe.get_doc("Item", item.get("variant_of"))

		variant_list, options, variant_item_name = get_variant_attributes(item, price_list, warehouse)
		item_data["attributes"] = options

		variant_item_name_list.extend(variant_item_name)

	else:
		# price_and_stock = []
		# price_and_stock = get_price_and_stock_details(item, warehouse, price_list)
		# item_data["stock_quantity"] = price_and_stock['inventory_quantity']
		# item_data["regular_price"] = str(price_and_stock['regular_price'])
		item_data["type"] = "simple" 
		
	erp_item = frappe.get_doc("Item", item.get("name"))
	erp_item.flags.ignore_mandatory = True
	if not item.get("woocommerce_sync_product_id"):
		create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list)
		sync_item_image(erp_item)

	else:
		item_data["id"] = item.get("woocommerce_sync_product_id")
		try:
			updated_item = put_request("products/{0}".format(item.get("woocommerce_sync_product_id")), item_data)
			# sync_item_image(erp_item)
		except requests.exceptions.HTTPError as e:
			if e.args[0] and (e.args[0].startswith("404") or e.args[0].startswith("400") ):
				if frappe.db.get_value("Woocommerce Sync Settings", "Woocommerce Sync Settings", "if_not_exists_create_item_to_woocommerce"):
					item_data["id"] = ''
					create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list)
					# sync_item_image(erp_item)
				else:
					disable_woocommerce_sync_for_item(erp_item)
			else:
				raise e

	frappe.db.commit()

def create_or_update_varient_to_woocommerce():
	if not item.get("woocommerce_sync_product_id"):
		create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list)
		sync_item_image(erp_item)

	else:
		item_data["id"] = item.get("woocommerce_sync_product_id")
		try:
			updated_item = put_request("products/{0}".format(item.get("woocommerce_sync_product_id")), item_data)
			# sync_item_image(erp_item)
		except requests.exceptions.HTTPError as e:
			if e.args[0] and (e.args[0].startswith("404") or e.args[0].startswith("400") ):
				if frappe.db.get_value("Woocommerce Sync Settings", "Woocommerce Sync Settings", "if_not_exists_create_item_to_woocommerce"):
					item_data["id"] = ''
					create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list)
					# sync_item_image(erp_item)
				else:
					disable_woocommerce_sync_for_item(erp_item)
			else:
				raise e

	frappe.db.commit()

def create_new_item_to_woocommerce(item, item_data, erp_item, variant_item_name_list):
	new_item = post_request("products", item_data)
	erp_item.woocommerce_sync_product_id = new_item.get("id")
	if not item.get("has_variants"):
		erp_item.woocommerce_sync_variant_id = new_item.get("id")

	erp_item.save()
	# update_variant_item(erp_item.woocommerce_sync_product_id, variant_item_name_list)

def restImgUL(imgPath):
    url='http://xxxxxxxxxxxx.com/wp-json/wp/v2/media'
    data = open(imgPath, 'rb').read()
    fileName = os.path.basename(imgPath)
    res = requests.post(url='http://xxxxxxxxxxxxx.com/wp-json/wp/v2/media',
                        data=data,
                        headers={ 'Content-Type': 'image/jpg','Content-Disposition' : 'attachment; filename=%s'% fileName},
                        auth=('authname', 'authpass'))
    # pp = pprint.PrettyPrinter(indent=4) ## print it pretty. 
    # pp.pprint(res.json()) #this is nice when you need it
    newDict=res.json()
    newID= newDict.get('id')
    link = newDict.get('guid').get("rendered")
    print newID, link
    return (newID, link)

def sync_item_image(item):
	image_info = {
        "image": {}
	}

	if item.image:
		img_details = frappe.db.get_value("File", {"file_url": item.image}, ["file_name", "content_hash"])

		if img_details and img_details[0] and img_details[1]:
			is_private = item.image.startswith("/private/files/")

			with open(get_files_path(img_details[0].strip("/"), is_private=is_private), "rb") as image_file:
				image_info["image"]["attachment"] = base64.b64encode(image_file.read())
			image_info["image"]["filename"] = img_details[0]

			#to avoid 422 : Unprocessable Entity
			if not image_info["image"]["attachment"] or not image_info["image"]["filename"]:
				return False

		elif item.image.startswith("http") or item.image.startswith("ftp"):
			if validate_image_url(item.image):
				#to avoid 422 : Unprocessable Entity
				image_info["image"]["src"] = item.image

		if image_info["image"]:
			if not item_image_exists(item.woocommerce_sync_product_id, image_info):
				# to avoid image duplication
				post_request("/admin/products/{0}/images.json".format(item.woocommerce_sync_product_id), image_info)


def validate_image_url(url):
	""" check on given url image exists or not"""
	res = requests.get(url)
	if res.headers.get("content-type") in ('image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/tiff'):
		return True
	return False

def item_image_exists(woocommerce_sync_product_id, image_info):
	"""check same image exist or not"""
	for image in get_woocommerce_item_image(woocommerce_sync_product_id):
		if image_info.get("image").get("filename"):
			if os.path.splitext(image.get("src"))[0].split("/")[-1] == os.path.splitext(image_info.get("image").get("filename"))[0]:
				return True
		elif image_info.get("image").get("src"):
			if os.path.splitext(image.get("src"))[0].split("/")[-1] == os.path.splitext(image_info.get("image").get("src"))[0].split("/")[-1]:
				return True
		else:
			return False

def update_variant_item(new_item, item_code_list):
	for i, name in enumerate(item_code_list):
		erp_item = frappe.get_doc("Item", name)
		erp_item.flags.ignore_mandatory = True
		erp_item.woocommerce_sync_product_id = new_item['product']["variants"][i].get("id")
		erp_item.woocommerce_sync_variant_id = new_item['product']["variants"][i].get("id")
		erp_item.inventory_item_id = new_item['product']["variants"][i].get("inventory_item_id")
		erp_item.save()

def get_variant_attributes(item, price_list, warehouse):
	options, variant_list, variant_item_name, attr_sequence = [], [], [], []
	attr_dict = {}

	for i, variant in enumerate(frappe.get_all("Item", filters={"variant_of": item.get("name")},
		fields=['name'])):

		item_variant = frappe.get_doc("Item", variant.get("name"))
		data = (get_price_and_stock_details(item_variant, warehouse, price_list))
		data["item_name"] = item_variant.name
		data["attributes"] = []
		for attr in item_variant.get('attributes'):
			attribute_option = {}
			attribute_option["name"] = attr.attribute
			attribute_option["option"] = attr.attribute_value
			data["attributes"].append(attribute_option)
			
			if attr.attribute not in attr_sequence:
				attr_sequence.append(attr.attribute)
			if not attr_dict.get(attr.attribute):
				attr_dict.setdefault(attr.attribute, [])

			attr_dict[attr.attribute].append(attr.attribute_value)
		
		variant_list.append(data)	
		

	for i, attr in enumerate(attr_sequence):
		options.append({
			"name": attr,
			"visible": "True",
			"variation": "True",
			"position": i+1,
			"options": list(set(attr_dict[attr]))
		})
	return variant_list, options, variant_item_name

def get_price_and_stock_details(item, warehouse, price_list):
	qty = 0

	for warehouse_in_list in warehouse:
		# bin = get_bin(item.get("item_code"), warehouse_in_list)
		temp_qty = frappe.db.get_value("Bin", {"item_code":item.get("item_code"), "warehouse": warehouse_in_list.warehouse}, "actual_qty")
		if temp_qty:
			qty += temp_qty
	price = frappe.db.get_value("Item Price", \
			{"price_list": price_list, "item_code":item.get("item_code")}, "price_list_rate")

	item_price_and_quantity = {
		"regular_price": str(price)
	}
	if item.weight_per_unit:
		if item.weight_uom and item.weight_uom.lower() in ["kg", "g", "oz", "lb"]:
			item_price_and_quantity.update({
				"weight_unit": item.weight_uom.lower(),
				"weight": item.weight_per_unit,
				"grams": get_weight_in_grams(item.weight_per_unit, item.weight_uom)
			})


	if item.get("sync_qty_with_woocommerce_sync"):
		item_price_and_quantity.update({
			"stock_quantity": cint(qty) if qty else 0,
			"manage_stock": "True"
		})

	if item.woocommerce_sync_variant_id:
		item_price_and_quantity["id"] = item.woocommerce_sync_variant_id
	return item_price_and_quantity

def get_weight_in_grams(weight, weight_uom):
	convert_to_gram = {
		"kg": 1000,
		"lb": 453.592,
		"oz": 28.3495,
		"g": 1
	}

	return weight * convert_to_gram[weight_uom.lower()]

def trigger_update_item_stock(doc, method):
	if doc.flags.via_stock_ledger_entry:
		woocommerce_settings = frappe.get_doc("Woocommerce Sync Settings", "Woocommerce Sync Settings")
		if woocommerce_settings.woocommerce_url and woocommerce_settings.enable_woocommerce:
			update_item_stock(doc.item_code, woocommerce_settings, doc)

def trigger_update_item_stock_with_so_qty(sales_order, method):
	try:
		# update_item_stock_qty()
		enqueue("erpnext_woocommerce.sync_products.update_item_stock_qty", queue='long', timeout=1500)
	except Exception as e:
		pass
	

def update_item_stock_qty():
	woocommerce_settings = frappe.get_doc("Woocommerce Sync Settings", "Woocommerce Sync Settings")
	for item in frappe.get_all("Item", fields=['name', "item_code"],
		filters={"sync_with_woocommerce_sync": 1, "disabled": ("!=", 1), 'woocommerce_sync_variant_id': ('!=', '')}):
		try:
			update_item_stock(item.item_code, woocommerce_settings)
		except woocommerceError as e:
			make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
				request_data=item, exception=True)

		except Exception as e:
			try:
				if e.args[0] and e.args[0].startswith("402"):
					raise e
				else:
					make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
						request_data=item, exception=True)
			except Exception as e:
				print("exception")

def update_item_stock(item_code, woocommerce_settings, bin=None):
	item = frappe.get_doc("Item", item_code)
	items = frappe.db.sql("""
		select sum(soi.qty ) as qty
			from `tabSales Order` as so
					inner join `tabSales Order Item` as soi
						on soi.parent = so.name
			where 
				so.status in ("To Deliver and Bill","To Deliver") 
				and soi.item_code = %s
			group by soi.item_code 
	""",(item_code), as_list=1)
	if items and items[0] and items[0][0]:
		dec_qty = items[0][0]
	else: 
		dec_qty = 0
	if item.sync_qty_with_woocommerce_sync:
		if not bin:
			bin = get_bin(item_code, woocommerce_settings.warehouse)
		
		warehouses =  frappe.db.get_values("woocommerce Warehouse",{"parent": "Woocommerce Sync Settings"}, "warehouse")
		qty = bin.actual_qty
		bin_warehouse_is_sync = False
		for warehouse_in_list in warehouses:
			# bin = get_bin(item.get("item_code"), warehouse_in_list)
			temp_qty = 0
			if bin.warehouse == warehouse_in_list[0]:
				bin_warehouse_is_sync = True
				continue
			temp_qty = frappe.db.get_value("Bin", {"item_code":item_code, "warehouse": warehouse_in_list[0]}, "actual_qty")
			if temp_qty:
				qty += temp_qty	
		if 	not (bin_warehouse_is_sync or bin.warehouse ==  woocommerce_settings.warehouse):
			return
		qty -= dec_qty
		if not item.woocommerce_sync_product_id and not item.variant_of:
			sync_item_with_woocommerce(item, woocommerce_settings.price_list, woocommerce_settings.warehouse)

		if item.sync_with_woocommerce_sync and item.woocommerce_sync_product_id :
			if item.variant_of:
				item_data, resource = get_product_update_dict_and_resource(frappe.get_value("Item",
					item.variant_of, "woocommerce_sync_product_id"), item.woocommerce_sync_variant_id, is_variant=True,
					actual_qty=qty)
			else:
				item_data, resource = get_product_update_dict_and_resource(item.woocommerce_sync_product_id,
					item.woocommerce_sync_variant_id, actual_qty=qty)

			try:
				put_request(resource, item_data)
			except requests.exceptions.HTTPError as e:
				if e.args[0] and e.args[0].startswith("404"):
					make_woocommerce_log(title=e.message, status="Error", method="sync_woocommerce_items", message=frappe.get_traceback(),
						request_data=item_data, exception=True)
					disable_woocommerce_sync_for_item(item)
				else:
					raise e

def get_product_update_dict_and_resource(woocommerce_sync_product_id, woocommerce_sync_variant_id, is_variant=False, actual_qty=0):
	"""
	JSON required to update product

	item_data =	{
		"product": {
			"id": 3649706435 (woocommerce_sync_product_id),
			"variants": [
				{
					"id": 10577917379 (woocommerce_sync_variant_id),
					"inventory_management": "woocommerce",
					"inventory_quantity": 10
				}
			]
		}
	}
	"""

	item_data = {
		"product": {
			"variants": []
		}
	}

	varient_data = {
		"id": woocommerce_sync_variant_id,
		"inventory_quantity": cint(actual_qty),
		"inventory_management": "woocommerce"
	}

	if is_variant:
		item_data = {
			"variant": varient_data
		}
		resource = "admin/variants/{}.json".format(woocommerce_sync_variant_id)
	else:
		item_data["product"]["id"] = woocommerce_sync_product_id
		item_data["product"]["variants"].append(varient_data)
		resource = "admin/products/{}.json".format(woocommerce_sync_product_id)

	return item_data, resource
