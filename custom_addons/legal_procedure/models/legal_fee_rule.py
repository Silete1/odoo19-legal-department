from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalFeeRule(models.Model):
    """What a procedure costs, and who says so - الرسوم.

    Iraqi fee schedules conflict. The published figure, the figure in the
    circular that amended it, the figure the counter quotes and the figure on the
    receipt are four numbers that agree perhaps half the time, and a stamp duty
    of 0.2% of capital is not the same shape as a flat IQD 25,000 filing fee.

    So a fee rule is guidance rather than gospel, and the form shows
    ``last_verified_on`` and ``legal_basis`` *beside the amount* rather than on
    some provenance tab nobody opens. A number with no date next to it invites a
    clerk to trust it; a number with "last checked in 2023" next to it invites
    them to ring the counter, which is the correct behaviour.
    """

    _name = "legal.fee.rule"
    _description = "Fee Rule"
    _order = "procedure_type_id, sequence, id"

    name = fields.Char(
        required=True,
        translate=True,
        help="What the counter calls it: registration fee, stamp duty, publication charges.",
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Paid At",
        ondelete="cascade",
        index=True,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
        help="Where in the walk the money changes hands. Leave empty for a fee "
        "due at any point.",
    )
    computation = fields.Selection(
        [
            ("fixed", "Fixed Amount"),
            ("percent_capital", "Percentage Of Capital"),
            ("percent_contract", "Percentage Of Contract Value"),
        ],
        default="fixed",
        required=True,
        help="A stamp duty of 0.2% of capital is not the same shape as a flat "
        "filing fee, and forcing both into one column loses the arithmetic that "
        "makes the second one checkable.",
    )
    amount = fields.Monetary(
        currency_field="currency_id",
        help="The flat amount, or the percentage where the computation is a rate.",
    )
    minimum_amount = fields.Monetary(currency_field="currency_id")
    maximum_amount = fields.Monetary(
        currency_field="currency_id",
        help="Iraqi percentage fees are routinely capped. Zero means no cap.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False)
        or self.env.company.currency_id,
        required=True,
    )
    is_stamp_duty = fields.Boolean(
        string="Stamp Duty",
        help="Stamps are bought rather than paid, are receipted differently and "
        "are reported separately, so they are flagged rather than merged into the fee.",
    )
    is_optional = fields.Boolean(
        help="A fee some files attract and others do not - expedited handling, an "
        "extra certified copy.",
    )
    note = fields.Text(translate=True)
    legal_basis = fields.Char(
        translate=True,
        help="The instruction or schedule that sets the figure.",
    )
    legal_basis_url = fields.Char()
    last_verified_on = fields.Date(
        help="Shown next to the amount, deliberately. A figure with no date beside "
        "it invites a clerk to trust it.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    @api.depends("name", "amount", "currency_id")
    def _compute_display_name(self):
        for rule in self:
            rule.display_name = rule.name or ""

    @api.constrains("step_id", "procedure_type_id")
    def _check_step_belongs_to_procedure(self):
        for rule in self:
            if rule.step_id and rule.step_id.procedure_type_id != rule.procedure_type_id:
                raise ValidationError(
                    _("The fee “%s” is due at a step belonging to another procedure.", rule.name)
                )

    @api.constrains("amount", "minimum_amount", "maximum_amount")
    def _check_amounts(self):
        for rule in self:
            if rule.amount < 0:
                raise ValidationError(_("A fee cannot be negative."))
            if rule.maximum_amount and rule.maximum_amount < rule.minimum_amount:
                raise ValidationError(
                    _("The cap on “%s” is below its floor.", rule.name)
                )

    def _amount_for(self, case):
        """What this rule costs on that file.

        A percentage is computed against the figure the file carries, then
        clamped. Where the file carries no base at all the flat amount is
        returned rather than zero: a fee of zero reads as "free" on a screen and
        somebody turns up at the counter with no money.
        """
        self.ensure_one()
        if self.computation == "fixed":
            return self.amount
        base = 0.0
        if self.computation == "percent_capital":
            base = case.entity_id.capital or 0.0
        elif self.computation == "percent_contract":
            base = case.contract_value or 0.0
        if not base:
            return self.amount
        computed = base * (self.amount or 0.0) / 100.0
        if self.minimum_amount:
            computed = max(computed, self.minimum_amount)
        if self.maximum_amount:
            computed = min(computed, self.maximum_amount)
        return computed
