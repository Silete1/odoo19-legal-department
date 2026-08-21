from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gov_hr_administrative_department_id = fields.Many2one(
        related="company_id.gov_hr_administrative_department_id", readonly=False
    )
    gov_hr_director_general_user_id = fields.Many2one(
        related="company_id.gov_hr_director_general_user_id", readonly=False
    )
    gov_hr_default_administrative_officer_id = fields.Many2one(
        related="company_id.gov_hr_default_administrative_officer_id", readonly=False
    )
    gov_hr_official_stamp = fields.Binary(
        related="company_id.gov_hr_official_stamp", readonly=False
    )
    gov_hr_official_stamp_filename = fields.Char(
        related="company_id.gov_hr_official_stamp_filename", readonly=False
    )
    gov_hr_director_general_signature = fields.Binary(
        related="company_id.gov_hr_director_general_signature", readonly=False
    )
    gov_hr_director_general_signature_filename = fields.Char(
        related="company_id.gov_hr_director_general_signature_filename", readonly=False
    )
