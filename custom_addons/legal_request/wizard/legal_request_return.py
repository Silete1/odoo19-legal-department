from odoo import _, fields, models
from odoo.exceptions import UserError


class LegalRequestReturn(models.TransientModel):
    """Sending an answer back for rework is a reasoned act, never a bare bounce.

    The officer who reworks the request corrects it against what the approver
    objected to, and "returned" tells them nothing. The reason is what the next
    round is measured against, so it is mandatory - and captured here rather than
    typed into a chatter note, so it lands on the request's own return field
    where the officer will look for it.
    """

    _name = "legal.request.return"
    _description = "Return A Request For Rework"

    request_id = fields.Many2one(
        "legal.request",
        string="Request",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    reason = fields.Text(
        string="Reason",
        help="What the approver wants changed, in their words. This is what the "
        "rework is corrected against, so “redo it” is not an answer.",
    )

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(
                _(
                    "A return needs a reason. Without it the officer reworking the "
                    "request is guessing at what the approver wanted."
                )
            )
        self.request_id._apply_return(self.reason)
        return {"type": "ir.actions.act_window_close"}
