from odoo import fields, models


class GovHrDeputationActivityType(models.Model):
    _name = "gov.hr.deputation.activity.type"
    _description = "Deputation Activity Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    _unique_code_company = models.Constraint(
        "UNIQUE (company_id, code)", "Activity type codes must be unique per company."
    )
