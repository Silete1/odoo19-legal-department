from odoo import _, api, fields, models


class LegalCaseStepCheck(models.Model):
    """The counter walk as it actually happened - جولة الأختام.

    A براءة ذمة is twenty-two windows inside one step. Modelling them as
    twenty-two steps would bury the shape of the procedure under its
    bureaucracy; modelling them as a free-text note would make "which counter
    are we stuck at" unanswerable, which is the only question the runner's
    manager asks all morning.

    So the configured check list is instantiated into rows here when the file
    arrives at the step, and the row carries **its own copy** of the name, the
    window and the stamp. The copy is deliberate: the configuration will be
    edited, windows move floors and stamps get renamed, and a walk completed in
    March must keep saying what was actually stamped in March.
    """

    _name = "legal.case.step.check"
    _description = "Case Counter Check"
    _order = "case_id, sequence, id"

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", index=True
    )
    check_id = fields.Many2one(
        "legal.procedure.step.check",
        string="Configured Check",
        ondelete="set null",
        index=True,
    )
    step_id = fields.Many2one(
        "legal.procedure.step", string="Step", required=True, ondelete="restrict", index=True
    )

    # Snapshots, so a completed walk keeps saying what was really stamped.
    name = fields.Char(required=True, translate=True)
    counter = fields.Char(string="Window", translate=True)
    produces_stamp = fields.Char(string="Stamp", translate=True)
    check_kind = fields.Selection(
        [
            ("stamp", "Stamp / Endorsement"),
            ("pay_fee", "Payment"),
            ("inspection", "Inspection"),
            ("collect", "Collection"),
            ("verify", "Verification"),
        ],
        default="stamp",
        required=True,
    )

    done = fields.Boolean()
    done_on = fields.Datetime(readonly=True)
    done_by_id = fields.Many2one("res.users", string="Done By", readonly=True)
    refused = fields.Boolean(
        help="The window refused it. A refusal at counter 14 of 22 is the single "
        "most useful fact of the morning, and it is not the same as 'not done yet'.",
    )
    refusal_reason = fields.Char(translate=True)
    reference = fields.Char(
        string="Reference",
        help="The stamp number, the receipt, the initials the officer wrote.",
    )
    is_required = fields.Boolean(default=True)
    superseded = fields.Boolean(
        readonly=True,
        help="Marked when the file is returned and the walk starts again. The old "
        "row stays: it is the evidence of which counters were already satisfied.",
    )
    round = fields.Integer(default=1, required=True, index=True)
    sequence = fields.Integer(default=10)
    note = fields.Char(translate=True)
    company_id = fields.Many2one(
        "res.company", related="case_id.company_id", store=True, index=True
    )

    @api.depends("name", "counter")
    def _compute_display_name(self):
        for check in self:
            check.display_name = (
                "%s (%s)" % (check.name, check.counter) if check.counter else (check.name or "")
            )

    def action_mark_done(self):
        self.write(
            {
                "done": True,
                "refused": False,
                "done_on": fields.Datetime.now(),
                "done_by_id": self.env.uid,
            }
        )
        for check in self:
            check.case_id._log(
                "check",
                _("%(stamp)s obtained at %(counter)s.",
                  stamp=check.produces_stamp or check.name,
                  counter=check.counter or check.step_id.gov_body_id.display_name),
                closes_step=False,
            )
        return True

    def action_mark_refused(self):
        self.write({"done": False, "refused": True})
        for check in self:
            check.case_id._log(
                "check",
                _("%(counter)s refused: %(reason)s",
                  counter=check.counter or check.name,
                  reason=check.refusal_reason or _("no reason given")),
                closes_step=False,
            )
        return True
