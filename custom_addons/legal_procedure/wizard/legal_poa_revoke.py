from odoo import _, fields, models
from odoo.exceptions import UserError


class LegalPoaRevoke(models.TransientModel):
    """Revoking a وكالة is a dated, reasoned act - never an archive tick.

    The reason is mandatory because three different people will ask for it: the
    agent whose authority has just gone, the counter that still has the old deed
    on file, and the auditor six months later. A boolean flag answers none of
    them, and a revocation nobody can explain is indistinguishable from a
    mistake.
    """

    _name = "legal.poa.revoke"
    _description = "Revoke A Power Of Attorney"

    poa_id = fields.Many2one(
        "legal.poa", string="Power Of Attorney", required=True, ondelete="cascade", readonly=True
    )
    revoked_on = fields.Date(
        required=True,
        default=fields.Date.context_today,
        help="The date the revocation was registered, which is the date the "
        "counter will honour - not the date somebody noticed.",
    )
    # Required in the view and checked below, not on the column: the message a
    # NOT NULL constraint produces explains nothing, and this is a field three
    # different people will later ask about.
    reason = fields.Char(translate=True)
    notify_bodies = fields.Boolean(
        string="Note The Bodies",
        default=True,
        help="Records on the trail that each counter the deed was valid at still "
        "holds the old copy. Iraqi bodies do not learn of a revocation until they "
        "are told, and the file presented tomorrow is presented on the old deed.",
    )

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(_("A revocation needs a reason."))
        self.poa_id.write(
            {
                "state": "revoked",
                "revoked_on": self.revoked_on,
                "revocation_reason": self.reason,
            }
        )
        body = _(
            "Revoked on %(date)s: %(reason)s", date=self.revoked_on, reason=self.reason
        )
        if self.notify_bodies and self.poa_id.body_ids:
            body += _(
                "\nStill on file at: %s. Each of them must be told separately.",
                ", ".join(self.poa_id.body_ids.mapped("display_name")),
            )
        self.poa_id.message_post(body=body)
        for case in self.poa_id.case_ids.filtered(lambda record: not record.is_closed):
            case._log("contact", body, closes_step=False)
        return {"type": "ir.actions.act_window_close"}
