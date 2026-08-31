from odoo import _, fields, models


class LegalCorrespondence(models.Model):
    """The edge from the register back to the opinion that produced the letter.

    ``legal_correspondence`` deliberately does not know that opinions exist - the
    register is useful with no advisory workflow at all - so the link is declared
    from this side, the side that can explain why it is nullable: almost every
    register entry has nothing to do with an opinion, and an issued opinion books
    exactly one.
    """

    _inherit = "legal.correspondence"

    opinion_id = fields.Many2one(
        "legal.opinion",
        string="Legal Opinion",
        ondelete="set null",
        index=True,
        help="The issued opinion this outgoing entry books into the register. "
        "Empty for every ordinary letter.",
    )

    def action_open_opinion(self):
        self.ensure_one()
        if not self.opinion_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Legal Opinion"),
            "res_model": "legal.opinion",
            "res_id": self.opinion_id.id,
            "view_mode": "form",
        }
