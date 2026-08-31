from odoo import _, fields, models
from odoo.exceptions import UserError


class LegalRequestCancel(models.TransientModel):
    """The dialog that will not let a request be cancelled without a reason.

    A cancelled request is not deleted - the number stays in the record - and the
    only question anybody asks about it later is why. A cancellation logged as a
    bare state change answers nobody: not the requester whose question just went
    away, not the manager reviewing the desk, not the auditor. So the reason is
    mandatory here, checked in the action rather than as a NOT NULL column, so the
    message explains what the reason is *for*.
    """

    _name = "legal.request.cancel"
    _description = "Cancel A Legal Request"

    request_id = fields.Many2one(
        "legal.request",
        string="Request",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    reason = fields.Text(
        string="Reason",
        help="Why the request is being dropped. The requester will ask, and so "
        "will the auditor.",
    )

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(
                _(
                    "A cancellation needs a reason. Without it, a dropped request is "
                    "indistinguishable from a mistake."
                )
            )
        self.request_id._apply_cancel(self.reason)
        return {"type": "ir.actions.act_window_close"}
