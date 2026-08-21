from odoo import fields, models, _
from odoo.exceptions import ValidationError


class GovHrReturnWizard(models.TransientModel):
    _name = "gov.hr.return.wizard"
    _description = "Return Government HR Case for Correction"

    res_model = fields.Char(required=True, readonly=True)
    res_id = fields.Integer(required=True, readonly=True)
    step_name = fields.Char(readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        if self.res_model not in self.env:
            raise ValidationError(_("The target case model is not available."))
        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record or not hasattr(record, "action_return"):
            raise ValidationError(_("The target record is not a government workflow case."))
        return record.action_return(self.reason)
