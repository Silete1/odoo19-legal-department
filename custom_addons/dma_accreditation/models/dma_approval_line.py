# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_datetime

from .dma_constants import ROLE_SELECTION, STATE_SELECTION


class DmaApprovalLine(models.Model):
    """Immutable audit trail of every workflow transition of a request.

    Lines are only ever appended by the workflow methods of
    ``dma.accreditation.request`` (through
    :meth:`~odoo.addons.dma_accreditation.models.dma_accreditation_request.
    DmaAccreditationRequest._log_approval`). They can never be modified nor
    deleted afterwards: ``ir.model.access`` grants no write/unlink right to any
    group, and the overrides below also block privileged (``sudo``) code so the
    log stays trustworthy for an external audit.
    """

    _name = "dma.approval.line"
    _description = "Accreditation Approval Log Line"
    _order = "date asc, id asc"

    request_id = fields.Many2one(
        "dma.accreditation.request",
        string="Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    step = fields.Selection(
        STATE_SELECTION, string="Step", required=True,
        help="Workflow step the decision was taken on.",
    )
    role = fields.Selection(ROLE_SELECTION, string="Role", required=True)
    user_id = fields.Many2one(
        "res.users", string="Decided By", required=True,
        default=lambda self: self.env.user,
    )
    decision = fields.Selection(
        [
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("returned", "Returned"),
            ("confirmed", "Confirmed"),
        ],
        required=True,
    )
    date = fields.Datetime(
        string="Date", required=True, default=fields.Datetime.now,
    )
    notes = fields.Text()
    # The whole statement as one translatable sentence: assembled in the form
    # around four <field> nodes it would export as four fragments, and Arabic
    # cannot reorder those.
    summary = fields.Char(string="Decision", compute="_compute_summary")
    company_id = fields.Many2one(related="request_id.company_id")

    @api.depends("user_id", "role", "date", "request_id")
    def _compute_summary(self):
        roles = dict(self._fields["role"]._description_selection(self.env))
        for line in self:
            line.summary = self.env._(
                "%(user)s, acting as %(role)s, decided this on %(date)s "
                "for %(request)s.",
                user=line.user_id.display_name,
                role=roles.get(line.role, line.role),
                date=format_datetime(self.env, line.date, dt_format="short"),
                request=line.request_id.name,
            )

    @api.depends("step", "user_id")
    def _compute_display_name(self):
        for line in self:
            step = dict(self._fields["step"]._description_selection(self.env)).get(line.step, "")
            line.display_name = f"{step} / {line.user_id.name or ''}".strip(" /")

    def write(self, vals):
        raise UserError(self.env._(
            "The accreditation approval log is immutable: existing entries can "
            "never be modified."
        ))

    def unlink(self):
        raise UserError(self.env._(
            "The accreditation approval log is immutable: existing entries can "
            "never be deleted."
        ))
