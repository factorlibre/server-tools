# -*- coding: utf-8 -*-
# © 2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from openerp import api, fields, models


class BaseConfigSettings(models.TransientModel):
    _inherit = 'base.config.settings'

    @api.model
    def get_default_aws_access_key_id(self, fields):
        return {
            'aws_access_key_id':
            self.env["ir.config_parameter"].get_param(
                "base_multi_image_s3.aws_access_key_id")
        }

    @api.multi
    def set_aws_access_key_id(self):
        for config in self:
            self.env['ir.config_parameter'].set_param(
                "base_multi_image_s3.aws_access_key_id",
                config.aws_access_key_id or '')

    @api.model
    def get_default_aws_secret_access_key(self, fields):
        return {
            'aws_secret_access_key':
            self.env['ir.config_parameter'].get_param(
                "base_multi_image_s3.aws_secret_access_key")
        }

    @api.multi
    def set_aws_secret_access_key(self):
        for config in self:
            self.env['ir.config_parameter'].set_param(
                "base_multi_image_s3.aws_secret_access_key",
                config.aws_secret_access_key or '')

    @api.model
    def get_default_aws_s3_bucket_name(self, fields):
        return {
            'aws_s3_bucket_name':
            self.env['ir.config_parameter'].get_param(
                "base_multi_image_s3.aws_s3_bucket_name")
        }

    @api.multi
    def set_aws_s3_bucket_name(self):
        for config in self:
            self.env['ir.config_parameter'].set_param(
                "base_multi_image_s3.aws_s3_bucket_name",
                config.aws_s3_bucket_name or '')

    @api.model
    def get_default_aws_image_public_domain(self, fields):
        return {
            'aws_image_public_domain':
            self.env['ir.config_parameter'].get_param(
                "base_multi_image_s3.aws_image_public_domain")
        }

    @api.multi
    def set_aws_image_public_domain(self):
        for config in self:
            self.env['ir.config_parameter'].set_param(
                "base_multi_image_s3.aws_image_public_domain",
                config.aws_image_public_domain or '')

    aws_access_key_id = fields.Char('AWS Access Key ID')
    aws_secret_access_key = fields.Char('AWS Secret access Key')
    aws_s3_bucket_name = fields.Char('S3 Bucket Name')
    aws_image_public_domain = fields.Char(
        'AWS Public Image domain', help="Public domain to access images "
        "in bucket. It can be the bucket domain if has public permissions or "
        "a CloudFront domain linked to that bucket")
