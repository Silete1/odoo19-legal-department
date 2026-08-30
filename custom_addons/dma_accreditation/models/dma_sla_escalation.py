# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Record of a file that overran its service level.

Deliberately small: this is an operational log, not an incident management
system. One row per (file, step, department, level, visit), so a file that
comes back to a step it already overran a first time gets a *second* row rather
than silently reusing the first - which is exactly what makes the rework
figures of the performance screen honest.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from .dma_constants import ROLE_SELECTION, STATE_SELECTION, role_label, state_label

#: Level 1 warns the department that owns the step; level 2 puts the file on
#: the Accreditation Manager's desk. There is no level 3: the module knows no
#: authority above the manager, and inventing one would be inventing policy.
ESCALATION_LEVEL_SELECTION = [
    ("1", "Department Warning"),
    ("2", "Escalated to the Accreditation Manager"),
]


class DmaSlaEscalation(models.Model):
    """One overrun of a service level."""

    _name = "dma.sla.escalation"
    _description = "Accreditation Service Level Escalation"
    _order = "triggered_on desc, id desc"

    request_id = fields.Many2one(
        "dma.accreditation.request", string="Request", required=True,
        ondelete="cascade", index=True,
    )
    state = fields.Selection(
        STATE_SELECTION, string="Step", required=True, index=True,
        help="Step the file was sitting on when it overran.",
    )
    role = fields.Selection(
        ROLE_SELECTION, string="Responsible Role", required=True, index=True,
    )
    level = fields.Selection(
        ESCALATION_LEVEL_SELECTION, string="Level", required=True, default="1", index=True,
    )
    #: The moment the file reached the step. Part of the identity of the row:
    #: it is what tells a second visit to a step from the first one.
    stage_entered_on = fields.Datetime(string="Step Entered On", required=True)
    due_on = fields.Datetime(string="Was Due On", required=True)
    triggered_on = fields.Datetime(
        string="Raised On", required=True, default=fields.Datetime.now, index=True,
    )
    overdue_hours = fields.Float(
        string="Overdue By (hours)",
        help="How late the file already was when the escalation was raised.",
    )
    reason = fields.Char(string="Reason", required=True)
    acknowledged_by = fields.Many2one("res.users", string="Acknowledged By", readonly=True)
    acknowledged_on = fields.Datetime(string="Acknowledged On", readonly=True)
    resolved_on = fields.Datetime(
        string="Resolved On", readonly=True, index=True,
        help="Set when the file left the step the escalation was raised on.",
    )
    is_open = fields.Boolean(
        string="Open", compute="_compute_is_open", store=True, index=True,
    )
    # Related and stored so the escalation list can be searched and grouped by
    # applicant without joining back through the request on every row.
    partner_id = fields.Many2one(
        related="request_id.partner_id", string="Applicant", store=True, index=True,
    )
    request_state = fields.Selection(
        related="request_id.state", string="Current Status",
    )
    company_id = fields.Many2one(related="request_id.company_id", store=True, index=True)

    #: One row per overrun of one visit to one step by one department. The
    #: whole idempotency of the scheduled job rests on this index: the job may
    #: run every ten minutes and will still never raise the same escalation
    #: twice.
    _unique_escalation = models.UniqueIndex(
        "(request_id, state, role, level, stage_entered_on)",
        "This escalation has already been raised for that step.",
    )

    @api.depends("resolved_on")
    def _compute_is_open(self):
        for escalation in self:
            escalation.is_open = not escalation.resolved_on

    @api.depends("request_id", "state", "level")
    def _compute_display_name(self):
        levels = dict(self._fields["level"]._description_selection(self.env))
        for escalation in self:
            escalation.display_name = "%s - %s (%s)" % (
                escalation.request_id.name or "",
                state_label(self.env, escalation.state) if escalation.state else "",
                levels.get(escalation.level, ""),
            )

    # ------------------------------------------------------------------
    # Integrity - the escalation log is evidence, like the approval log
    # ------------------------------------------------------------------
    #: The only things a human may ever change on an escalation. Everything
    #: else is written by the engine and is part of the record of what
    #: happened, so it is as immutable as ``dma.approval.line``.
    _MUTABLE_FIELDS = frozenset({
        "acknowledged_by", "acknowledged_on", "resolved_on", "is_open",
    })

    def write(self, vals):
        forbidden = set(vals) - self._MUTABLE_FIELDS
        if forbidden and not self.env.context.get("dma_sla_engine"):
            raise UserError(self.env._(
                "An escalation records what actually happened and cannot be "
                "rewritten; only acknowledging and resolving it are allowed."
            ))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("dma_sla_engine"):
            raise UserError(self.env._(
                "Escalations are part of the audit trail of the process and can "
                "never be deleted."
            ))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_acknowledge(self):
        """The responsible department (or the manager) takes the file on."""
        for escalation in self:
            if escalation.acknowledged_on:
                continue
            escalation.write({
                "acknowledged_by": self.env.uid,
                "acknowledged_on": fields.Datetime.now(),
            })
            escalation.request_id.message_post(body=self.env._(
                "Escalation acknowledged by %(user)s: %(step)s is overdue with "
                "%(role)s.",
                user=self.env.user.name,
                step=state_label(self.env, escalation.state),
                role=role_label(self.env, escalation.role),
            ))
        return True

    def action_open_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "dma.accreditation.request",
            "res_id": self.request_id.id,
            "view_mode": "form",
            "target": "current",
        }
