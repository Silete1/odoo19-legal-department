# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

#: field name -> ``ir.config_parameter`` key and its factory default.
SETTING_PARAMETERS = {
    "sop_fee": ("dma_accreditation.sop_fee", "250.0"),
    "demo_fee": ("dma_accreditation.demo_fee", "500.0"),
    "validity_months": ("dma_accreditation.validity_months", "12"),
}


class DmaAccreditationSettings(models.TransientModel):
    """Directorate wide defaults for the accreditation process.

    This is deliberately *not* an extension of ``res.config.settings``:
    :meth:`odoo.addons.base.models.res_config.ResConfigSettings.execute` refuses
    to save for anybody outside "Administration / Settings"
    (``env.is_admin()``), so an Accreditation Manager would see the form and
    then be unable to save it. The values are still plain
    ``ir.config_parameter`` entries, so they can equally be set from a data file
    or a migration script.
    """

    _name = "dma.accreditation.settings"
    _description = "Accreditation Settings"

    # Monetary, like the ``dma.fee.payment.amount`` they seed: typed as a Float
    # the same quantity was declared two different ways in two files and the
    # view had to carry a currency option the field definition gives for free.
    sop_fee = fields.Monetary(
        string="SOP Reading Fee", currency_field="currency_id",
        help="Default amount proposed on a new SOP reading fee line.",
    )
    demo_fee = fields.Monetary(
        string="Operational Demonstration Fee", currency_field="currency_id",
        help="Default amount proposed on a new operational demonstration fee line.",
    )
    validity_months = fields.Integer(
        string="Accreditation Validity",
        default=12,
        help="Validity of an operational accreditation certificate, in months.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Fee Currency",
        compute="_compute_currency_id",
        help="Fees are expressed in the currency of the active company.",
    )

    @api.depends_context("company")
    def _compute_currency_id(self):
        for settings in self:
            settings.currency_id = settings.env.company.currency_id

    # ------------------------------------------------------------------
    # Parameter round trip
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        params = self.env["ir.config_parameter"].sudo()
        for name, (key, fallback) in SETTING_PARAMETERS.items():
            raw = params.get_param(key, fallback)
            try:
                values[name] = int(float(raw)) if name == "validity_months" else float(raw)
            except (TypeError, ValueError):
                values[name] = int(float(fallback)) if name == "validity_months" else float(fallback)
        return values

    def _check_manager(self):
        if self.env.su or self.env.user.has_group("dma_accreditation.group_dma_manager"):
            return
        raise AccessError(self.env._(
            "Only the Accreditation Manager can change the accreditation settings."
        ))

    def action_apply(self):
        """Store the values as system parameters and close the dialog."""
        self.ensure_one()
        self._check_manager()
        if self.sop_fee < 0 or self.demo_fee < 0:
            raise ValidationError(self.env._("A fee amount cannot be negative."))
        if self.validity_months < 1:
            raise ValidationError(self.env._(
                "The validity of an accreditation must be at least one month."
            ))
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("dma_accreditation.sop_fee", str(self.sop_fee))
        params.set_param("dma_accreditation.demo_fee", str(self.demo_fee))
        params.set_param("dma_accreditation.validity_months", str(self.validity_months))
        # The values live in ir.config_parameter and are surfaced nowhere else,
        # so a dialog that simply vanishes leaves the manager with no way to
        # tell whether the write landed.
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": False,
                "message": self.env._("Accreditation settings saved."),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
