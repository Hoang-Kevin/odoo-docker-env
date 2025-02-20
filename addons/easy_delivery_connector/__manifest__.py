# -*- coding: utf-8 -*-
{
    'name': "easy_delivery_connector",
    'summary': """Intégration API Easy-Delivery""",
    'description': """
      Intégration API Easy-Delivery
    """,
    'author': "Jessy Rakotondrainibe",
    'category': 'Tools',
    'version': '0.1',
    'depends': ['stock','website_sale','delivery'],
    'data': [
        'data/data.xml',
        'data/ir_config_parameter.xml',
        'views/stock_picking_views.xml.xml',
    ],
}
