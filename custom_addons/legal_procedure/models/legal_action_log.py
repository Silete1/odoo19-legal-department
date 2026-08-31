from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalActionLog(models.Model):
    """The trail - سجل الإجراءات. Append only, and it means it.

    Every move a file makes appends exactly one row here, and this table is the
    single source of truth for *when* a file arrived where it is:
    ``legal.case.stage_entered_on`` is computed from it and stored, rather than
    being a timestamp the workflow methods write by hand. A second set of
    timestamps maintained alongside a log always drifts, and the drift is
    discovered during an audit, which is the worst possible moment.

    **Immutability is enforced three times over, deliberately.**

    * ``write`` and ``unlink`` raise - *even under ``sudo``*, because the usual
      escape hatch for "the engine needs to fix it up" is precisely the hole an
      auditor is looking for;
    * no group is granted write or unlink in the access rules, so a client never
      gets the chance to try;
    * the row carries **denormalised snapshots** - ``step_code``,
      ``step_name``, ``group_code`` - so that renaming or deleting a step
      afterwards cannot rewrite what happened. A log that only holds foreign
      keys is a log that quietly changes its own history the first time somebody
      reorganises the configuration.
    """

    _name = "legal.action.log"
    _description = "Action Log"
    _order = "id desc"

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", index=True
    )
    action = fields.Selection(
        [
            ("open", "Opened"),
            ("advance", "Advanced"),
            ("transition", "Transition"),
            ("return", "Returned For Correction"),
            ("check", "Counter Check"),
            ("document", "Document"),
            ("fee", "Fee"),
            ("letter", "Letter"),
            ("contact", "Contact Note"),
            ("escalate", "Escalated"),
            ("close", "Closed"),
            ("reopen", "Reopened"),
        ],
        required=True,
        index=True,
    )
    description = fields.Char(required=True, translate=True)
    reason = fields.Text(
        translate=True,
        help="Mandatory on a return or a rejection: it is what the next round is "
        "corrected against.",
    )

    # ------------------------------------------------------------------
    # Where the file was and where it went
    # ------------------------------------------------------------------
    from_step_id = fields.Many2one(
        "legal.procedure.step", string="From", ondelete="set null", index=True
    )
    to_step_id = fields.Many2one(
        "legal.procedure.step", string="To", ondelete="set null", index=True
    )
    transition_id = fields.Many2one(
        "legal.procedure.transition", string="Move", ondelete="set null"
    )
    closes_step = fields.Boolean(
        default=True,
        index=True,
        help="Whether this entry actually moved the file. Entries that record "
        "something happening while the file stays put - a fee paid, a note taken - "
        "must not reset the clock on the step.",
    )

    # ------------------------------------------------------------------
    # Snapshots, so the trail survives reconfiguration
    # ------------------------------------------------------------------
    step_code = fields.Char(readonly=True)
    step_name = fields.Char(readonly=True)
    body_name = fields.Char(readonly=True)
    group_code = fields.Char(readonly=True)
    round = fields.Integer(default=1, required=True, index=True)

    user_id = fields.Many2one(
        "res.users", string="By", default=lambda self: self.env.user, required=True, index=True
    )
    logged_on = fields.Datetime(
        default=fields.Datetime.now, required=True, index=True, readonly=True
    )
    company_id = fields.Many2one(
        "res.company", related="case_id.company_id", store=True, index=True
    )

    @api.depends("description", "logged_on")
    def _compute_display_name(self):
        for entry in self:
            entry.display_name = entry.description or ""

    @api.model_create_multi
    def create(self, vals_list):
        """Take the snapshots at write time, never at read time.

        The whole value of the denormalised columns is that they record what the
        configuration said *then*. Filling them from the foreign key on read
        would reproduce exactly the drift they exist to prevent.
        """
        for vals in vals_list:
            step = self.env["legal.procedure.step"].browse(vals.get("to_step_id") or vals.get("from_step_id"))
            if step:
                vals.setdefault("step_code", step.code or "")
                vals.setdefault("step_name", step.name or "")
                vals.setdefault("body_name", step.gov_body_id.display_name or "")
                vals.setdefault("group_code", step.responsible_group_id.name or "")
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(
            _(
                "The action log is the file's evidence and cannot be edited, not even "
                "by an administrator. If an entry is wrong, add the entry that corrects "
                "it - that is what an audit trail is."
            )
        )

    def unlink(self):
        raise UserError(
            _(
                "An entry in the action log cannot be deleted. The trail is the only "
                "answer the department has to “what did we do, and when”."
            )
        )
