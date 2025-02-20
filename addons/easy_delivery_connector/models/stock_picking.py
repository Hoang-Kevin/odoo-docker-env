import logging
import requests
from odoo import models , fields, api
from werkzeug.urls import url_join

from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    show_easy_delivery_button = fields.Boolean(
        compute="_compute_show_easy_delivery_button"
    )

    @api.depends("carrier_id")
    def _compute_show_easy_delivery_button(self):
        for record in self:
            record.show_easy_delivery_button = record.carrier_id and record.carrier_id.delivery_type == "easy_delivery"

    def build_delivery_details(self):
        """
        Build and return delivery details for the current stock picking.
        
        Returns:
            dict: A dictionary containing shipper, recipient, and parcel details.
        """
        company_partner = self.env.company.partner_id
        recipient_partner = self.partner_id

        shipper_details = {
            'name': company_partner.name,
            'street': company_partner.contact_address,
            'country': company_partner.country_id.code,
            'postal_code': company_partner.zip or '-',
            'city': company_partner.city,
            'tel': company_partner.phone,
            'email': company_partner.email,
        }

        recipient_details = {
            'name': recipient_partner.name,
            'street': recipient_partner.contact_address,
            'country': recipient_partner.country_id.code,
            'postal_code': recipient_partner.zip,
            'city': recipient_partner.city,
            'tel': recipient_partner.phone,
            'email': recipient_partner.email,
        }

        parcel_details = [
            {
                'weight': line.product_id.weight,
                'shipper_reference': self.carrier_id.name,
                'comment': line.description_picking,
                'value': line.product_id.lst_price * line.quantity,
            }
            for line in self.move_ids_without_package
        ]

        return {
            'shipper': shipper_details,
            'recipient': recipient_details,
            'parcels': parcel_details,
            'printtype': 'zpl',
        }

    def generate_shipping_label_easy_delivery(self):

        api_url, auth_token = self._get_and_validate_api_credentials()
        json_response = self._send_api_request(api_url, auth_token)
        self._process_api_response_and_create_attachments(json_response)
        _logger.info("Easy Delivery label retrieval completed successfully for picking ID: %s", self.id)

    def _get_and_validate_api_credentials(self):

        config_param = self.env["ir.config_parameter"].sudo()
        api_url = config_param.get_param("easy_delivery.api_url")
        auth_token = config_param.get_param("easy_delivery.auth_token")

        if not api_url or not auth_token:
            _logger.error("Easy Delivery API credentials are missing!")
            raise ValidationError("Easy Delivery API credentials are not configured. Please set them in system parameters.")

        return api_url, auth_token

    def _send_api_request(self, api_url, auth_token):
        request_url = url_join(api_url, "/api/order")
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }
        request_data = self.build_delivery_details()

        _logger.info("Requesting Easy Delivery API with URL: %s, Headers: %s, Data: %s", request_url, headers, request_data)

        try:
            response = requests.post(request_url, json=request_data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("API Request Failed: %s", str(e))
            raise ValidationError(f"API Request Failed: {e}")

    def _process_api_response_and_create_attachments(self, json_response):
        """
        Process the API response and create attachments for PDF or ZPL labels.
        
        Args:
            json_response (dict): The JSON response from the API.
        
        Raises:
            ValidationError: If the response does not contain PDF or ZPL data.
        """
        if json_response.get('status') != 'success':
            error_type = json_response.get('error', {}).get('type', 'Unknown Error')
            error_message = json_response.get('error', {}).get('message', 'No message provided')
            raise ValidationError(f"{error_type}: {error_message}")

        data = json_response.get('data', {})
        if 'pdf' in data:
            self.env['ir.attachment'].create({
                'name': f"{data['parcel_ref']}.pdf",
                'datas': data['pdf'],
                'type': 'binary',
                'mimetype': 'application/pdf',
                'res_model': 'stock.picking',
                'res_id': self.id,
            })
            _logger.info("Successfully created PDF attachment for picking ID: %s", self.id)
        elif 'labels' in data:
            for label in data['labels']:
                self.env['ir.attachment'].create({
                    'name': f"{label['shipper_ref'] or label['number']}.zpl",
                    'raw': label['zpl'].encode('utf-8'),
                    'type': 'binary',
                    'mimetype': 'text/plain',
                    'res_model': 'stock.picking',
                    'res_id': self.id,
                })
            _logger.info("Successfully created %d ZPL attachments for picking ID: %s", len(data['labels']), self.id)
        else:
            raise ValidationError("No PDF or ZPL labels found in the API response.")