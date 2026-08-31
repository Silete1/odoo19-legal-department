from odoo import _, api, fields, models


class LegalCorrespondence(models.Model):
    """The edge from the correspondence register to a contract.

    ``legal_correspondence`` deliberately does not know that contracts exist - a
    department may run the register with no contract module at all - so the link
    is added from this side, exactly as ``legal_procedure`` adds ``case_id``. It
    is nullable because a letter about a contract routinely arrives before the
    contract file is opened: a landlord's renewal notice lands in the mail room
    addressed to a company that has not yet drafted the renewal.
    """

    _inherit = "legal.correspondence"

    contract_id = fields.Many2one(
        "legal.contract",
        string="Contract",
        ondelete="set null",
        index=True,
        help="The contract this letter belongs to, if any. Empty for a letter "
        "that arrived before anybody opened a contract file for it.",
    )

    def action_open_contract(self):
        self.ensure_one()
        if not self.contract_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.contract",
            "res_id": self.contract_id.id,
            "view_mode": "form",
        }


class LegalContract(models.Model):
    """The other half of the edge: the letters filed under a contract."""

    _inherit = "legal.contract"

    correspondence_ids = fields.One2many(
        "legal.correspondence", "contract_id", string="Letters", copy=False
    )
    correspondence_count = fields.Integer(compute="_compute_correspondence_count")

    def _compute_correspondence_count(self):
        counts = dict(
            self.env["legal.correspondence"]._read_group(
                [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
            )
        )
        for contract in self:
            contract.correspondence_count = counts.get(contract, 0)

    def action_open_correspondence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Letters"),
            "res_model": "legal.correspondence",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "default_entity_id": self.entity_id.id,
                "default_subject": self.title or "",
            },
        }
