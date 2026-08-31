from odoo import _, fields, models
from odoo.exceptions import UserError


class LegalLawsuitReason(models.TransientModel):
    """The reason an adverse move demands before it is made.

    Closing a case or lodging a challenge changes what the department is exposed
    to, and both are learned from afterwards only if the reason was captured at
    the time. So neither move happens on a bare button: the button opens this,
    and this refuses to confirm without a reason.
    """

    _name = "legal.lawsuit.reason"
    _description = "Lawsuit Reason"

    lawsuit_id = fields.Many2one(
        "legal.lawsuit", string="Lawsuit", required=True, ondelete="cascade"
    )
    action_kind = fields.Selection(
        [
            ("close", "Close Case"),
            ("appeal", "Lodge Challenge"),
        ],
        required=True,
    )
    reason = fields.Text(
        string="Reason",
        required=True,
        help="Why the case is being closed, or on what ground it is challenged. "
        "Read afterwards by whoever asks how the matter ended.",
    )

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(_("A reason is required."))
        if self.action_kind == "close":
            self.lawsuit_id._apply_close(self.reason)
        elif self.action_kind == "appeal":
            self.lawsuit_id._apply_appeal(self.reason)
        return {"type": "ir.actions.act_window_close"}
