# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

FEE_TYPE_SELECTION = [
    ("sop_reading", "SOP Reading Fee"),
    ("operational_demo", "Operational Demonstration Fee"),
]

#: fee type -> ``ir.config_parameter`` key holding its default amount.
FEE_TYPE_PARAMETER = {
    "sop_reading": "dma_accreditation.sop_fee",
    "operational_demo": "dma_accreditation.demo_fee",
}


class DmaFeePayment(models.Model):
    """A fee collected during the operational accreditation phase."""

    _name = "dma.fee.payment"
    _description = "Accreditation Fee Payment"
    _order = "receipt_date desc, id desc"

    request_id = fields.Many2one(
        "dma.accreditation.request",
        string="Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    fee_type = fields.Selection(
        FEE_TYPE_SELECTION, string="Fee Type", required=True,
        default="sop_reading",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    amount = fields.Monetary(string="Amount", currency_field="currency_id")
    receipt_number = fields.Char(string="Receipt Number", copy=False)
    receipt_date = fields.Date(string="Receipt Date", copy=False)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "dma_fee_payment_attachment_rel",
        "fee_id",
        "attachment_id",
        string="Receipt Scan",
    )
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed")],
        default="draft", required=True, copy=False,
    )
    confirmed_by = fields.Many2one("res.users", string="Confirmed By", readonly=True, copy=False)
    confirmed_on = fields.Datetime(string="Confirmed On", readonly=True, copy=False)
    notes = fields.Text()
    company_id = fields.Many2one(related="request_id.company_id")

    _amount_positive = models.Constraint(
        "CHECK(amount >= 0)",
        "A fee amount can never be negative.",
    )

    @api.depends("fee_type", "receipt_number")
    def _compute_display_name(self):
        labels = dict(self._fields["fee_type"]._description_selection(self.env))
        for fee in self:
            label = labels.get(fee.fee_type, "")
            fee.display_name = f"{label} - {fee.receipt_number}" if fee.receipt_number else label

    @api.model
    def _default_amount(self, fee_type):
        """Read the configured default amount of ``fee_type``."""
        param = FEE_TYPE_PARAMETER.get(fee_type)
        if not param:
            return 0.0
        value = self.env["ir.config_parameter"].sudo().get_param(param, "0")
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @api.onchange("fee_type")
    def _onchange_fee_type(self):
        for fee in self:
            if fee.fee_type and not fee.amount:
                fee.amount = fee._default_amount(fee.fee_type)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Only fill in the configured default when no amount was given at
            # all. An explicit zero is a real value - and one that
            # :meth:`action_confirm` refuses - not a request for the default.
            if vals.get("amount") is None:
                vals["amount"] = self._default_amount(vals.get("fee_type", "sop_reading"))
        return super().create(vals_list)

    def _check_finance_role(self):
        user = self.env.user
        if not (
            user.has_group("dma_accreditation.group_dma_finance")
            or user.has_group("dma_accreditation.group_dma_manager")
        ):
            raise UserError(self.env._(
                "Only the Finance Department can confirm or reset an accreditation fee."
            ))

    def action_confirm(self):
        """Finance confirms that the fee was actually cashed in."""
        self._check_finance_role()
        for fee in self:
            if fee.state == "confirmed":
                raise UserError(self.env._("Fee “%s” is already confirmed.", fee.display_name))
            if not fee.receipt_number:
                raise ValidationError(self.env._(
                    "A receipt number is required before confirming a fee."
                ))
            if not fee.receipt_date:
                raise ValidationError(self.env._(
                    "A receipt date is required before confirming a fee."
                ))
            if fee.currency_id.is_zero(fee.amount):
                raise ValidationError(self.env._(
                    "The fee amount must be greater than zero."
                ))
        self.write({
            "state": "confirmed",
            "confirmed_by": self.env.user.id,
            "confirmed_on": fields.Datetime.now(),
        })
        for fee in self:
            fee.request_id.message_post(
                body=self.env._(
                    "Fee confirmed: %(fee)s - %(amount)s (receipt %(receipt)s).",
                    fee=dict(self._fields["fee_type"]._description_selection(self.env))[fee.fee_type],
                    amount=fee.amount,
                    receipt=fee.receipt_number,
                )
            )

    def action_reset_draft(self):
        """Undo a confirmation (Finance / Accreditation Manager only)."""
        self._check_finance_role()
        self.write({"state": "draft", "confirmed_by": False, "confirmed_on": False})
