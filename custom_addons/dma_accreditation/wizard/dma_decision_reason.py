# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DmaDecisionReason(models.TransientModel):
    """Collects the mandatory reason before returning or rejecting a request."""

    _name = "dma.decision.reason"
    _description = "Accreditation Return / Reject Reason"

    request_id = fields.Many2one(
        "dma.accreditation.request", string="Request", required=True,
        ondelete="cascade",
    )
    mode = fields.Selection(
        [("return", "Return to Applicant"), ("reject", "Reject")],
        string="Decision", required=True, default="return",
    )
    reason = fields.Text(string="Reason", required=True)
    target_state = fields.Selection(
        related="request_id.state", string="Current Step", readonly=True,
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        if not values.get("request_id") and self.env.context.get("active_model") == \
                "dma.accreditation.request":
            active_id = self.env.context.get("active_id")
            if active_id:
                values["request_id"] = active_id
        return values

    def action_confirm(self):
        """Apply the decision on the request; the request enforces the rights."""
        self.ensure_one()
        reason = (self.reason or "").strip()
        if not reason:
            raise ValidationError(self.env._(
                "A reason is required before returning or rejecting a request."
            ))
        if self.mode == "return":
            self.request_id.action_return_to_applicant(reason)
        else:
            self.request_id.action_reject(reason)
        return {"type": "ir.actions.act_window_close"}
