from odoo import _, api, fields, models


class LegalCorrespondence(models.Model):
    """The edge from the request desk to the register.

    ``legal_correspondence`` deliberately does not know that requests exist - the
    mail room predates the intake desk and stands on its own - so the link is
    added from this side, which is also the side that can say why it is nullable:
    most letters have no request behind them, and a letter that answers one is
    still a first-class register entry, not a child of the request.
    """

    _inherit = "legal.correspondence"

    request_id = fields.Many2one(
        "legal.request",
        string="From Request",
        ondelete="set null",
        index=True,
        help="The legal-department request this letter was raised to answer. "
        "Empty for the ordinary post that arrived without one.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        entries = super().create(vals_list)
        for entry in entries:
            if entry.request_id:
                entry.request_id.message_post(
                    body=_("Letter raised from this request: %s", entry.display_name)
                )
        return entries

    def action_open_request(self):
        self.ensure_one()
        if not self.request_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.request",
            "res_id": self.request_id.id,
            "view_mode": "form",
        }
