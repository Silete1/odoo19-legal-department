# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..models.dma_accreditation_request import RETURN_TARGET_STATE
from ..models.dma_constants import state_label


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
    # Named for what it holds. It used to be called `target_state` while being
    # `related="request_id.state"`, so the name promised the destination and
    # the value was the origin.
    current_state = fields.Selection(
        related="request_id.state", string="Current Step", readonly=True,
    )
    # A Char holding the *label*, not a Selection holding the key: a new
    # Selection field gets its own ir.model.fields.selection rows, and the
    # Arabic entries in ar.po are bound to the fields that already existed - so
    # a duplicate of the workflow states would have rendered in English inside
    # an otherwise Arabic dialog. `state_label` reads the request's own field,
    # which is translated once, for everyone.
    resume_state = fields.Char(
        string="Resumes At", compute="_compute_resume_state",
        help="Step the file re-enters once the reception desk resumes it.",
    )

    @api.depends("request_id.state")
    def _compute_resume_state(self):
        for wizard in self:
            state = wizard.request_id.state
            wizard.resume_state = state_label(
                self.env, RETURN_TARGET_STATE.get(state, "draft")
            ) if state else False

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
