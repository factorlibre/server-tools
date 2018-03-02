# -*- coding: utf-8 -*-
# © 2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
{
    "name": "Multiple images: Store in Amazon S3",
    "summary": "Allow multiple images for database objects",
    "version": "8.0.1.0.0",
    "author": "FactorLibre, "
              "Odoo Community Association (OCA)",
    "license": "AGPL-3",
    "website": "http://www.factorlibre.com",
    "category": "Tools",
    "depends": [
        'base_setup',
        'base_multi_image'
    ],
    'installable': True,
    "data": [
        "views/res_config_view.xml",
        "views/image_view.xml",
    ],
    "external_dependencies": {
        "python": [
            "boto3"
        ]
    }
}
