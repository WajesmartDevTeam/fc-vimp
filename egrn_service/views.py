# Import necessary modules and classes
import os, sys
import logging
import asyncio

from django.db.models import Avg
from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from django_auth_adfs.rest_framework import AdfsAccessTokenAuthentication
from overrides.authenticate import CombinedAuthentication

from byd_service.rest import RESTServices
from django.contrib.auth import get_user_model
from overrides.rest_framework import APIResponse
from django.core.exceptions import ObjectDoesNotExist
from copy import deepcopy

from .models import GoodsReceivedNote, GoodsReceivedLineItem, PurchaseOrder, PurchaseOrderLineItem
from .serializers import GoodsReceivedNoteSerializer, PurchaseOrderSerializer, GoodsReceivedLineItemSerializer
from .tasks import send_email_async

# Initialize REST services
byd_rest_services = RESTServices()
# Get the user model
User = get_user_model()


def delete_items(po):
	del po["Item"]
	return po

def filter_objects(keys_to_keep, objects):
	filtered_objects = []
	# Use dictionary comprehension to filter objects
	for obj in objects:
		filtered_obj = {key: obj[key] for key in keys_to_keep if key in obj}
		filtered_objects.append(filtered_obj)
	
	return filtered_objects

def get_formatted_vendor(id, id_type):
	data = byd_rest_services.get_vendor_by_id(id, id_type=id_type)
	vendor = {
		"InternalID": data["BusinessPartner"]["InternalID"],
		"CategoryCode": data["BusinessPartner"]["CategoryCode"],
		"CategoryCodeText": data["BusinessPartner"]["CategoryCodeText"],
		"BusinessPartnerFormattedName": data["BusinessPartner"]["BusinessPartnerFormattedName"],
	}
	
	return vendor


@api_view(['GET'])
@authentication_classes([AdfsAccessTokenAuthentication,])
def search_vendor(request, ):
	params = dict(request.GET)
	try:
		query_param = ('email', params['email'][0]) if params['email'] else ('phone', params['phone'][0])
		# Fetch purchase orders for the authenticated user
		vendor = get_formatted_vendor(query_param[1], query_param[1])
		# Data object to hold the return data
		data = {}
		
		if vendor:
			keys_to_keep = ["ObjectID", "UUID", "ID", "CreationDateTime", "LastChangeDateTime", "CurrencyCode",
							"CurrencyCodeText", "TotalGrossAmount", "TotalNetAmount", "TotalTaxAmount",
							"ConsistencyStatusCode",
							"LifeCycleStatusCode", "AcknowledgmentStatusCode", "AcknowledgmentStatusCodeText",
							"DeliveryStatusCode", "DeliveryStatusCodeText", "InvoicingStatusCode",
							"InvoicingStatusCodeText"]
			
			purchase_orders = byd_rest_services.get_vendor_purchase_orders(vendor["InternalID"])
			purchase_orders = filter_objects(keys_to_keep, list(map(delete_items, purchase_orders)))
			
			data["BusinessPartner"] = vendor
			data["PurchaseOrders"] = purchase_orders
			
			return APIResponse("Vendor found.", status.HTTP_200_OK, data=data)
		
		return APIResponse(f"No vendor results found for {query_param[1]} {query_param[1]}.", status.HTTP_404_NOT_FOUND)
	except Exception as e:
		logging.error(e)
		return APIResponse("Internal Error.", status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@authentication_classes([CombinedAuthentication])
def get_purchase_order(request, po_id):
	try:
		try:
			# Fetch purchase orders from the database
			orders = PurchaseOrder.objects.get(po_id=po_id)
		except ObjectDoesNotExist:
			# If the order does not exist in the database, fetch the order from ByD
			byd_orders = byd_rest_services.get_purchase_order_by_id(po_id)
			if byd_orders:
				# If the order exists in ByD, create a new PurchaseOrder object
				po = PurchaseOrder()
				orders = po.create_purchase_order(byd_orders)
			else:
				# If the order does not exist in ByD, return an error
				return APIResponse(f"Order with ID {po_id} not found.", status.HTTP_404_NOT_FOUND)
		# Serialize the PurchaseOrder object
		serializer = PurchaseOrderSerializer(orders)
		return APIResponse("Purchase Orders Retrieved", status.HTTP_200_OK, data=serializer.data)
	except Exception as e:
		# Handle any other errors
		logging.error(f"An error occurred creating a Purchase Order: {e}")
		return APIResponse(f"Internal Error: {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@authentication_classes([AdfsAccessTokenAuthentication,])
def create_grn(request, ):
	identifier = "PONumber"  # should be PO_ID
	# keys we NEED to create a GRN
	required_keys = [identifier, "recievedGoods"]
	# the post request
	request_data = request.data
	# Check that all the required keys are present in the request
	required_keys_present = [
		any(
			map(lambda x: r in x, list(request_data.keys()))
		) for r in required_keys
	]
	# If required keys are not present, return an error
	if not all(required_keys_present):
		return APIResponse(f"Missing required key(s) [{', '.join(required_keys)}]", status.HTTP_400_BAD_REQUEST)
	# Make the PO_ID key consistent as the identifier
	request_data["po_id"] = request_data[identifier]
	try:
		# Try to create the GRN
		new_grn = GoodsReceivedNote()
		grn_saved = new_grn.save(grn_data=request_data)
		if grn_saved:
			# If the GRN was created successfully, return the created GRN
			created_grn = GoodsReceivedNote.objects.get(id=grn_saved.id)
			# Serialize the GoodsReceivedNote instance along with its related GoodsReceivedLineItem instances
			goods_received_note = GoodsReceivedNoteSerializer(created_grn).data
			template_data = deepcopy(goods_received_note)
			# Modify some fields for more straightforward rendering
			template_data['purchase_order']['BuyerParty']['BuyerPartyName'] = template_data['purchase_order']['BuyerParty']['BuyerPartyName'][0]
			template_data['purchase_order']['Supplier']['SupplierName'] = template_data['purchase_order']['Supplier']['SupplierName'][0]
			template_data['purchase_order']['Supplier']['SupplierPostalAddress'] = template_data['purchase_order']['Supplier']['SupplierPostalAddress'][0]
			# Render the HTML content of the template and send the email asynchronously
			html_content = render_to_string('grn_receipt_template.html', {'data': template_data})
			send_email_async(html_content)
			return APIResponse("GRN Created.", status.HTTP_201_CREATED, data=goods_received_note)
	# Return an error if there is an exception
	except Exception as e:
		return APIResponse(str(e), status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@authentication_classes([CombinedAuthentication])
def get_all_grns(request, ):
	try:
		grns = GoodsReceivedNote.objects.all()
		# Serialize the GoodsReceivedNote instance along with its related GoodsReceivedLineItem instances
		grn_serializer = GoodsReceivedNoteSerializer(grns, many=True)
		goods_received_note = grn_serializer.data
		
		return APIResponse("GRNs Retrieved", status.HTTP_200_OK, data=goods_received_note)
	except Exception as e:
		return APIResponse(f"Internal Error: {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)
	

@api_view(['GET'])
@authentication_classes([CombinedAuthentication])
def get_vendors_grns(request, ):
	'''
		Get all GRNs for the authenticated user
	'''
	try:
		po_id = request.query_params.get('po_id')
		grns = GoodsReceivedNote.objects.filter(purchase_order__vendor=request.user.vendor_profile)
		# If the request params contain po_id, filter by po_id
		grns = grns.filter(purchase_order__po_id=po_id) if po_id else grns
		if grns:
			# Serialize the GoodsReceivedNote instance along with its related GoodsReceivedLineItem instances
			serialized_grns = GoodsReceivedNoteSerializer(grns, many=True).data
			return APIResponse("GRNs Retrieved", status.HTTP_200_OK, data=serialized_grns)
		return APIResponse(f"No GRN found.", status=status.HTTP_404_NOT_FOUND)
	except Exception as e:
		return APIResponse(f"Internal Error: {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([CombinedAuthentication])
def get_grn(request, grn_number):
	try:
		grn = GoodsReceivedNote.objects.get(grn_number=grn_number)
		if grn:
			# Serialize the GoodsReceivedNote instance along with its related GoodsReceivedLineItem instances
			grn_serializer = GoodsReceivedNoteSerializer(grn)
			goods_received_note = grn_serializer.data
			return APIResponse("GRN Retrieved", status.HTTP_200_OK, data=goods_received_note)
		else:
			return APIResponse("GRN Not Found", status=status.HTTP_404_NOT_FOUND)
	except Exception as e:
		return APIResponse(f"Internal Error: {e}", status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([CombinedAuthentication,])
def weighted_average(request):
	product_id = request.query_params.get('product_id')
	start_date = request.query_params.get('start_date')
	end_date = request.query_params.get('end_date')
	
	if not product_id or not start_date or not end_date:
		return APIResponse("Product ID, start_date, and end_date are required parameters.", status=status.HTTP_400_BAD_REQUEST)
	
	try:
		# Get the received line items for the given product ID and date range
		line_items = GoodsReceivedLineItem.objects.filter(
			purchase_order_line_item__product_code=product_id,
			date_received__range=[start_date, end_date]
		)
		
		if not line_items.exists():
			return APIResponse("No line items found for the given product ID and date range.", status=status.HTTP_404_NOT_FOUND)
	
		# Calculate the average price
		avg_price = line_items.aggregate(average_price=Avg('purchase_order_line_item__unit_price'))['average_price']
		
		# Serialize the GoodsReceivedLineItem instances
		Goods = GoodsReceivedLineItemSerializer(line_items, many=True).data
		
		return APIResponse("Success", data={
			"product_id": product_id,
			"average_price": avg_price,
			"start_date": start_date,
			"end_date": end_date,
			"items": Goods
		}, status=status.HTTP_200_OK)
	
	except Exception as e:
		return APIResponse(str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)