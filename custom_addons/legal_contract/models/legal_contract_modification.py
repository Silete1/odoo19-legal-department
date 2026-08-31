from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalContractModification(models.Model):
    """An amendment to a contract - a mulhaq / addendum.

    The rule that makes this a log rather than an edit: an amendment **never
    rewrites the original contract in place**. It is its own dated record with
    its own description and its own value change, and the contract's current
    value is computed as the original plus the applied amendments. Overwriting
    the signed value is how a department loses the ability to answer "what did we
    actually agree", which is the only question a dispute turns on.
    """

    _name = "legal.contract.modification"
    _description = "Contract Amendment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, sequence, id desc"
    _rec_names_search = ["number", "description"]

    contract_id = fields.Many2one(
        "legal.contract",
        string="Contract",
        required=True,
        ondelete="cascade",
        index=True,
    )
    number = fields.Char(
        string="Amendment No.",
        required=True,
        help="The amendment's own number, e.g. 'Addendum 1'.",
    )
    date = fields.Date(
        string="Amendment Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    description = fields.Text(
        string="What Changed",
        required=True,
        translate=True,
        help="What this amendment changes, in words.",
    )
    value_change = fields.Monetary(
        string="Value Change",
        currency_field="currency_id",
        help="The signed change to the contract value. Positive for an increase, "
        "negative for a reduction. Added to the original value only once applied.",
    )
    new_expiry_date = fields.Date(
        string="New Expiry",
        help="Where the amendment extends the term, the new expiry date. Applied "
        "onto the contract when the amendment is applied.",
    )
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("applied", "Applied"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(related="contract_id.company_id", store=True, index=True)
    active = fields.Boolean(default=True)

    _number_contract_uniq = models.Constraint(
        "UNIQUE(number, contract_id)",
        "That amendment number already exists on this contract.",
    )

    def action_apply(self):
        """Take the amendment into effect.

        Reserved for the approver rung: an amendment changes the value or the
        term the company is bound to, and the drafting clerk should not apply it
        on their own. Applying it never edits the original value; it flips the
        amendment to ``applied`` so the computed current value picks it up, and
        extends the term only where a new expiry was named.
        """
        if not self.env.user.has_group("legal_core.group_legal_approver"):
            raise UserError(
                _("Only an approver or the legal manager may apply an amendment.")
            )
        for amendment in self:
            if amendment.state == "applied":
                continue
            amendment.state = "applied"
            if amendment.new_expiry_date:
                amendment.contract_id.expiry_date = amendment.new_expiry_date
            amendment.contract_id.message_post(
                body=_(
                    "Amendment %(number)s applied: %(description)s",
                    number=amendment.number,
                    description=amendment.description or "",
                )
            )
        return True
