# -*- coding: utf-8 -*-

from odoo import models, fields

class DeliveryCarrierEasyDelivery(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[
    ('easy_delivery', 'Easy delivery')
], ondelete={'easy_delivery': lambda recs: recs.write({'delivery_type': 'fixed', 'fixed_price': 0})})