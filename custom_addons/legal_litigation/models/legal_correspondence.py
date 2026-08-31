from odoo import _, api, fields, models


class LegalCorrespondence(models.Model):
    """The edge from the letter register to a case.

    Added from this side for the same reason ``legal_procedure`` adds
    ``case_id``: ``legal_correspondence`` does not know litigation exists, and a
    ``Many2one('legal.lawsuit')`` declared there would make the register
    unloadable without this module. The field is nullable because a summons, an
    expert's notice or a court letter routinely arrives before a case has been
    opened for it.
    """

    _inherit = "legal.correspondence"

    lawsuit_id = fields.Many2one(
        "legal.lawsuit",
        string="Lawsuit",
        ondelete="set null",
        index=True,
        help="The الدعوى this letter belongs to. Empty for court post that arrived "
        "before a case was opened for it.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        entries = super().create(vals_list)
        for entry in entries:
            if entry.lawsuit_id:
                entry.lawsuit_id.message_post(
                    body=_("Letter registered: %s", entry.display_name)
                )
        return entries

    def action_open_lawsuit(self):
        self.ensure_one()
        if not self.lawsuit_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.lawsuit",
            "res_id": self.lawsuit_id.id,
            "view_mode": "form",
        }
