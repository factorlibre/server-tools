# -*- coding: utf-8 -*-
# © 2018 FactorLibre - Hugo Santos <hugo.santos@factorlibre.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import boto3
import base64
import os
import hashlib
import mimetypes
from openerp import api, exceptions, fields, models, _


class Image(models.Model):
    _inherit = "base_multi_image.image"

    @api.multi
    def _get_s3_url(self):
        for image in self:
            if image.storage == 's3' and image.s3_path:
                image_domain = self.env['ir.config_parameter'].get_param(
                    "base_multi_image_s3.aws_image_public_domain")
                if not image_domain:
                    image.s3_url = None
                    continue
                image.s3_url = "%s/%s" % (image_domain, image.s3_path)

    storage = fields.Selection(selection_add=[('s3', 'S3')])
    s3_path = fields.Char('S3 Path')
    s3_url = fields.Char('S3 URL', compute='_get_s3_url')
    s3_image_binary = fields.Binary('S3 Image Upload')
    s3_image_filename = fields.Char('S3 Image Filename')

    @api.multi
    def _get_image_from_s3(self):
        return self._get_image_from_url_cached(self.s3_url)

    @api.model
    def _upload_image_to_s3(self, image, s3_image_binary, s3_image_filename):
        param_env = self.env['ir.config_parameter']
        aws_access_key_id = param_env.get_param(
            "base_multi_image_s3.aws_access_key_id")
        aws_secret_access_key = param_env.get_param(
            "base_multi_image_s3.aws_secret_access_key")
        aws_s3_bucket_name = param_env.get_param(
            "base_multi_image_s3.aws_s3_bucket_name")
        if not aws_access_key_id or not aws_secret_access_key or \
                not aws_s3_bucket_name:
            raise exceptions.Warning(_(
                "AWS required params not configured. It's not possible to "
                "upload images to S3 service until params are configured. "
                "Go to Settings -> Configuration -> General settings and "
                "set the AWS params"))
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key)
        image_file = StringIO(base64.b64decode(s3_image_binary))
        hash_path = hashlib.sha1()
        hash_path.update("{}/{}".format(image.owner_model,
                                        image.owner_id))
        hash_path = hash_path.hexdigest()
        upload_path = "%s/%s" % (hash_path, s3_image_filename)
        s3_client.upload_fileobj(
            image_file, aws_s3_bucket_name, upload_path,
            ExtraArgs={
                'ContentType': mimetypes.guess_type(s3_image_filename)[0]
            })
        image.write({'name': s3_image_filename, 's3_path': upload_path})

    @api.model
    def create(self, vals):
        s3_image_binary = False
        s3_image_filename = False
        if vals.get('s3_image_binary'):
            s3_image_binary = vals['s3_image_binary']
            s3_image_filename = vals['s3_image_filename']
            del vals['s3_image_binary']
            del vals['s3_image_filename']
        image = super(Image, self).create(vals)
        if s3_image_binary and s3_image_filename:
            self._upload_image_to_s3(image, s3_image_binary, s3_image_filename)
        return image

    @api.multi
    def write(self, vals):
        s3_image_binary = False
        s3_image_filename = False
        if vals.get('s3_image_binary'):
            s3_image_binary = vals['s3_image_binary']
            s3_image_filename = vals['s3_image_filename']
            del vals['s3_image_binary']
            del vals['s3_image_filename']
        result = super(Image, self).write(vals)
        if s3_image_binary and s3_image_filename:
            for image in self:
                self._upload_image_to_s3(image, s3_image_binary,
                                         s3_image_filename)
        return result

    @api.onchange('s3_image_filename')
    def _onchange_s3_image_filename(self):
        if self.s3_image_filename:
            self.name, self.extension = os.path.splitext(
                self.s3_image_filename)
            self.name = self._make_name_pretty(self.name)
