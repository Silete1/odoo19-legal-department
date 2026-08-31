from odoo import _, api, fields, models


class LegalFee(models.Model):
    """Money that actually changed hands - الرسوم المدفوعة.

    A real row rather than a capture field, and that is why ``fee``, ``amount``
    and ``receipt`` are refused as capture-field names: what the department pays
    the Registrar in a year is a question somebody will ask, and a number buried
    in a per-step payload cannot be grouped, summed or reconciled.

    The row keeps the *quoted* figure from the rule alongside the *paid* figure,
    because Iraqi published fee schedules and Iraqi counters disagree often
    enough that the difference is itself information: a run of files where the
    counter charged more than the schedule is how a department discovers a
    circular it has not read.
    """

    _name = "legal.fee"
    _description = "Case Fee"
    _order = "case_id, sequence, id"

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", index=True
    )
    rule_id = fields.Many2one(
        "legal.fee.rule", string="Fee Rule", ondelete="set null", index=True
    )
    step_id = fields.Many2one(
        "legal.procedure.step", string="Due At", ondelete="set null", index=True
    )
    name = fields.Char(required=True, translate=True)
    amount = fields.Monetary(
        string="Quoted",
        currency_field="currency_id",
        help="What the schedule says. Kept even after payment, because a run of "
        "files where the counter charged more than the schedule is how a "
        "department finds a circular it has not read.",
    )
    amount_paid = fields.Monetary(string="Paid", currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False)
        or self.env.company.currency_id,
    )
    variance = fields.Monetary(
        compute="_compute_variance", store=True, currency_field="currency_id"
    )
    state = fields.Selection(
        [
            ("due", "Due"),
            ("paid", "Paid"),
            ("waived", "Waived"),
        ],
        default="due",
        required=True,
        index=True,
    )
    is_stamp_duty = fields.Boolean(string="Stamp Duty")
    is_optional = fields.Boolean()
    paid_on = fields.Date()
    receipt_number = fields.Char(
        index="trigram",
        help="The receipt number. Quoted back at every subsequent counter, so it is a "
        "column of its own and part of the file's search index.",
    )
    paid_by_id = fields.Many2one("res.users", string="Paid By")
    attachment_ids = fields.Many2many("ir.attachment", string="Receipt")
    note = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", related="case_id.company_id", store=True, index=True
    )

    @api.depends("amount", "amount_paid", "state")
    def _compute_variance(self):
        for fee in self:
            fee.variance = (fee.amount_paid - fee.amount) if fee.state == "paid" else 0.0

    @api.depends("name", "amount")
    def _compute_display_name(self):
        for fee in self:
            fee.display_name = fee.name or ""

    def action_mark_paid(self):
        for fee in self:
            fee.write(
                {
                    "state": "paid",
                    "amount_paid": fee.amount_paid or fee.amount,
                    "paid_on": fee.paid_on or fields.Date.context_today(fee),
                    "paid_by_id": fee.paid_by_id.id or self.env.uid,
                }
            )
            fee.case_id._log(
                "fee",
                _(
                    "%(name)s paid: %(amount)s%(receipt)s",
                    name=fee.name,
                    amount=fee.amount_paid,
                    receipt=_(" (receipt %s)", fee.receipt_number) if fee.receipt_number else "",
                ),
                closes_step=False,
            )
        return True
