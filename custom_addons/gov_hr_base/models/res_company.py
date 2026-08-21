from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    gov_hr_administrative_department_id = fields.Many2one(
        "hr.department",
        string="Administrative Department",
        check_company=True,
        ondelete="restrict",
    )
    gov_hr_director_general_user_id = fields.Many2one(
        "res.users",
        string="Director General",
        check_company=True,
        ondelete="restrict",
    )
    gov_hr_default_administrative_officer_id = fields.Many2one(
        "hr.employee",
        string="Default Administrative Officer",
        check_company=True,
        ondelete="restrict",
    )
    gov_hr_official_stamp = fields.Binary(
        string="Official Electronic Stamp",
        attachment=True,
        groups="gov_hr_base.group_gov_hr_manager",
    )
    gov_hr_official_stamp_filename = fields.Char(
        groups="gov_hr_base.group_gov_hr_manager"
    )
    gov_hr_director_general_signature = fields.Binary(
        string="Director General Signature",
        attachment=True,
        groups="gov_hr_base.group_gov_hr_manager",
    )
    gov_hr_director_general_signature_filename = fields.Char(
        groups="gov_hr_base.group_gov_hr_manager"
    )
