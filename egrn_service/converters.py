'''
	A collection of functions that contain the logic of how products should be converted.
	
	TODO: Document the rules.
	
	1. Always return "quantity_received"
'''


def chicken_conversion(*args, **kwargs):
	"""
		Converts KG chicken to pieces.
		Inputs:
			- packets_per_bag
			- number_of_bags
			
		[
		  {
		    "name": "packets_per_bag",
		    "type": "number",
		    "properties": {
		      "placeholder": "The number of packets in a bag.",
		      "min": 1,
		      "required": true
		    }
		  },
		  {
		    "name": "number_of_bags",
		    "type": "number",
		    "properties": {
		      "placeholder": "The number bags supplied.",
		      "min": 1,
		      "required": true
		    }
		  },
		]
	"""
	inputs = kwargs.get('input_fields')
	
	number_of_bag = float(inputs.get('number_of_bags'))
	packets_per_bag = float(inputs.get('packets_per_bag'))
	
	# Convert KG to pounds for consistency with other conversions
	# kg_to_pcs = 0
	# Chicken pieces conversion factor
	# if weight_of_bird >= 1.0 and weight_of_bird < 1.3:
	# 	kg_to_pcs = 6
	# elif weight_of_bird >= 1.3 and weight_of_bird < 1.5:
	# 	kg_to_pcs = 9
	# elif weight_of_bird >= 1.5 and weight_of_bird < 1.9:
	# 	kg_to_pcs = 12
	
	return {
		"quantity_received": number_of_bag * packets_per_bag
	}


def cut9_conversion(*args, **kwargs):
	"""
		Number of bags x No of Packets per bag x Pieces per packet
		Inputs:
			- number_of_bags
			- packets_per_bag
			- pieces_per_packet
			
		[
		  {
		    "name": "number_of_bags",
		    "type": "number",
		    "properties": {
		      "placeholder": "The number bags supplied.",
		      "min": 1,
		      "required": true
		    }
		  },
		  {
		    "name": "packets_per_bag",
		    "type": "number",
		    "properties": {
		      "placeholder": "The number of packets in a bag.",
		      "min": 1,
		      "required": true
		    }
		  },
		  {
            "name": "pieces_per_packet",
            "type": "number",
            "properties": {
              "placeholder": "The number of pieces in a packet.",,
		      "min": 1,
		      "required": true
            }
          }
		]
	"""
	inputs = kwargs.get('input_fields')
	
	number_of_bag = float(inputs.get('number_of_bags'))
	packets_per_bag = float(inputs.get('packets_per_bag'))
	pieces_per_packet = float(inputs.get('pieces_per_packet'))
	
	return {
		"quantity_received": number_of_bag * packets_per_bag * pieces_per_packet
	}


def nbc_products_volume_conversion(*args, **kwargs):
	'''
		Volume of NBC product received e.g 35cl, 50CL, 1Litre.
		Number of NBC products in a pack
		Number of packs received
		Upon inputting these required details, The system should do the following :
			Calculate the extended volume received. This is realized with the formular:
				Volume of Product received × Number in a pack × Number of packs received
		
		[
			{
				"name":"number_of_packs_received",
				"type":"number",
				"properties":{
					"placeholder":"The total number of packs received.",
					"min":1,
					"required":true
				}
			},
			{
				"name":"number_per_pack",
				"type":"number",
				"properties":{
				"placeholder":"The number products in a complete pack.",
				"min":1,
				"required":true
			}},
			{
				"name":"product_volume",
				"type":"select",
				"properties":{
					"placeholder":"The volume of this product, as stated on the product's container.",
					"required":true,
					"options":[
						{"name":"35cl","value":"35"},
						{"name":"50cl","value":"50"},
						{"name":"1L","value":"100"},
					]
			}}
		]
	'''
	inputs = kwargs.get('input_fields')
	
	number_of_packs_received = float(inputs.get('number_of_packs_received') or 0.00)
	number_per_pack = float(inputs.get('number_per_pack') or 0.00)
	product_volume = (float(inputs.get('product_volume') or 0.00) / 100.00) # Given that 1L = 100cl, we want to get the value in Litres
	
	extended_volume_received = product_volume * number_per_pack * number_of_packs_received
	
	return {
		"quantity_received": number_of_packs_received * number_per_pack,
		"extended_volume_received": extended_volume_received
	}
	