from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.legal_core.models.legal_engine import in_engine


class LegalSlaRule(models.Model):
    """How long a step may sit, and who is told when it does not - مستوى الخدمة.

    Per procedure, per step and per company, because the same counter treats two
    companies differently and both facts are true: a target is a statement about
    what *this* department expects at *this* window, not a universal constant.

    **Everything is counted in the body's working days.** ``legal.gov.body``
    carries a real ``resource.calendar`` - Sunday to Thursday, with Eid and the
    national closures entered as leaves - and every deadline here is planned
    through it. A target counted in calendar days cries wolf every Friday and
    goes berserk over Eid al-Adha, and a chase list that is wrong four days out
    of seven is a chase list people learn to close without reading. That is the
    whole difference between an escalation people act on and one they filter to
    a folder.
    """

    _name = "legal.sla.rule"
    _description = "Service Level Rule"
    _order = "procedure_type_id, sequence, id"

    name = fields.Char(compute="_compute_name", store=True)
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Step",
        ondelete="cascade",
        index=True,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
        help="Leave empty for a fallback that covers every step the procedure has "
        "no specific rule for.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="Empty applies to every company. A subsidiary that has agreed a "
        "shorter internal target sets its own row.",
    )
    target_days = fields.Integer(
        string="Target (working days)",
        default=3,
        required=True,
        help="Counted in the body's calendar from the moment the file arrived on "
        "the step.",
    )
    warning_days = fields.Integer(
        string="Warn (working days before)",
        default=1,
        help="How long before the target the file starts showing as due soon.",
    )
    escalation_days = fields.Integer(
        string="Escalate After (working days past target)",
        default=2,
        help="Zero escalates the moment the target passes. Most Iraqi counters "
        "deserve a day or two of grace before a manager is woken up.",
    )
    escalate_to_group_id = fields.Many2one(
        "res.groups",
        string="Escalate To",
        ondelete="restrict",
        help="Whose problem it becomes. Empty escalates to the legal manager.",
    )
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    # A step rule and a procedure fallback may coexist; two rules for the same
    # step and company may not, because the engine would have to guess.
    _step_company_uniq = models.UniqueIndex(
        "(procedure_type_id, step_id, company_id) WHERE step_id IS NOT NULL AND company_id IS NOT NULL",
        "There is already a service level for that step and company.",
    )

    @api.depends("procedure_type_id", "step_id", "target_days")
    def _compute_name(self):
        for rule in self:
            where = rule.step_id.name or _("every step")
            rule.name = _(
                "%(where)s - %(days)s working day(s)", where=where, days=rule.target_days
            )

    @api.constrains("target_days", "warning_days", "escalation_days")
    def _check_days(self):
        for rule in self:
            if rule.target_days <= 0:
                raise ValidationError(
                    _("A service level with no target is not a service level.")
                )
            if rule.warning_days < 0 or rule.escalation_days < 0:
                raise ValidationError(_("A service level cannot count backwards."))

    @api.constrains("step_id", "procedure_type_id")
    def _check_step_belongs_to_procedure(self):
        for rule in self:
            if rule.step_id and rule.step_id.procedure_type_id != rule.procedure_type_id:
                raise ValidationError(
                    _("That service level covers a step belonging to another procedure.")
                )

    @api.model
    def _rule_for(self, procedure_type, step, company):
        """The rule that governs one file at one moment.

        Most specific wins: the step-and-company row, then the step row, then the
        procedure fallback. Deliberately resolved in Python over a small ordered
        search rather than in SQL, because the result is cached per file for the
        length of the request and the table is measured in dozens of rows.
        """
        if not procedure_type or not step:
            return self.browse()
        rules = self.search(
            [
                ("procedure_type_id", "=", procedure_type.id),
                ("step_id", "in", [step.id, False]),
                ("company_id", "in", [company.id, False] if company else [False]),
            ]
        )
        for candidate in (
            rules.filtered(lambda rule: rule.step_id == step and rule.company_id == company),
            rules.filtered(lambda rule: rule.step_id == step and not rule.company_id),
            rules.filtered(lambda rule: not rule.step_id and rule.company_id == company),
            rules.filtered(lambda rule: not rule.step_id and not rule.company_id),
        ):
            if candidate:
                return candidate[0]
        return self.browse()


class LegalSlaEscalation(models.Model):
    """A file somebody has been told about - التصعيد.

    A row rather than an activity, because the question a manager asks is "what
    is escalated *now*", and that has to survive the activity being marked done
    by whoever it landed on. The activity is the notification; this is the
    record.

    **Idempotent by a unique index.** The escalation cron is expected to run
    every hour and to walk the whole live caseload each time, so a second pass
    over unchanged data must write nothing at all. The index on (case, step,
    round, level) is what guarantees that: not a flag the cron sets, not a
    "last run" timestamp that drifts, but the database refusing the duplicate.
    """

    _name = "legal.sla.escalation"
    _description = "Service Level Escalation"
    _order = "raised_on desc, id desc"
    _inherit = ["mail.thread"]

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", index=True
    )
    step_id = fields.Many2one(
        "legal.procedure.step", string="Step", required=True, ondelete="cascade", index=True
    )
    step_code = fields.Char(
        readonly=True,
        help="Snapshot, so the trail survives the step being renamed or removed.",
    )
    round = fields.Integer(
        default=1,
        required=True,
        help="Which round of the file. A file returned for correction and "
        "escalated again is a new escalation, not a repeat of the old one.",
    )
    level = fields.Selection(
        [("1", "Late"), ("2", "Escalated"), ("3", "Stale")],
        default="1",
        required=True,
        tracking=True,
    )
    reason = fields.Char(required=True, translate=True)
    raised_on = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    due_on = fields.Datetime(help="The deadline that was missed.")
    escalated_to_group_id = fields.Many2one("res.groups", string="Escalated To")
    resolved_on = fields.Datetime(index=True)
    is_open = fields.Boolean(compute="_compute_is_open", store=True, index=True)
    company_id = fields.Many2one(
        "res.company", related="case_id.company_id", store=True, index=True
    )

    _case_step_round_level_uniq = models.UniqueIndex(
        "(case_id, step_id, round, level)",
        "That escalation has already been raised for this file.",
    )

    @api.depends("resolved_on")
    def _compute_is_open(self):
        for escalation in self:
            escalation.is_open = not escalation.resolved_on

    @api.depends("case_id", "level")
    def _compute_display_name(self):
        levels = dict(self._fields["level"]._description_selection(self.env))
        for escalation in self:
            escalation.display_name = "%s - %s" % (
                escalation.case_id.display_name,
                levels.get(escalation.level, ""),
            )

    def action_resolve(self):
        self.write({"resolved_on": fields.Datetime.now()})
        return True

    def write(self, vals):
        """An escalation may be resolved and re-levelled; it may not be rewritten.

        The point of the record is that somebody was told something on a date.
        Letting the reason or the date be edited afterwards turns the trail into
        a draft.
        """
        frozen = {"case_id", "step_id", "round", "reason", "raised_on", "step_code"}
        forbidden = frozen.intersection(vals)
        if forbidden and not in_engine():
            raise UserError(
                _(
                    "An escalation records that somebody was told something on a date. "
                    "%s cannot be changed afterwards - resolve it and let the next run "
                    "raise a fresh one.",
                    ", ".join(sorted(forbidden)),
                )
            )
        return super().write(vals)
