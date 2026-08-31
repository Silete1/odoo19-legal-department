import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

#: How far ahead the generator materialises rows. Twelve months is enough for a
#: board to plan a year and short enough that a schedule somebody edits in March
#: has not already written three years of wrong dates.
GENERATION_HORIZON_MONTHS = 12


class LegalObligationSchedule(models.Model):
    """A recurring statutory deadline - الالتزام الدوري.

    Four shapes, and they are four because Iraqi practice has four, not because
    four felt like a tidy number:

    * **a fixed annual date** - the corporate income tax return, 31 May
      federally and 30 June in the Kurdistan Region;
    * **an offset from the financial year end** - the annual accounts, due a
      fixed number of days after a year end that differs per company;
    * **monthly** - the social security contribution, due on a day of every
      month, which is the obligation a department is most often late on and
      least often reminded about;
    * **an offset before an expiry** - the renewal that has to start before a
      licence lapses, where the deadline is a property of a *document* rather
      than of the calendar.

    A shape that cannot express one of those forces a customer to fake it with a
    date they maintain by hand, and a hand-maintained deadline is a deadline that
    is wrong by the second year.
    """

    _name = "legal.obligation.schedule"
    _description = "Obligation Schedule"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(required=True, help="Stable key used by content packs.")
    body_id = fields.Many2one(
        "legal.gov.body", string="Body", required=True, ondelete="restrict", index=True
    )
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction", string="Jurisdiction", ondelete="restrict", index=True
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Discharged By",
        ondelete="restrict",
        index=True,
        help="The procedure that satisfies the obligation. Without it the period "
        "row is a reminder; with it, it is a button that opens the file.",
    )
    entity_id = fields.Many2one(
        "legal.entity",
        string="For",
        ondelete="cascade",
        index=True,
        help="Leave empty to generate one row per legal entity of the company.",
    )

    frequency = fields.Selection(
        [
            ("fixed_annual_date", "Fixed Date Each Year"),
            ("offset_from_fye", "After The Financial Year End"),
            ("monthly", "Monthly"),
            ("offset_before_expiry", "Before A Document Expires"),
        ],
        default="fixed_annual_date",
        required=True,
    )
    due_month = fields.Integer(
        string="Month",
        default=5,
        help="For a fixed annual date: 5 for May. The federal corporate return is "
        "31 May; the Region's is 30 June.",
    )
    due_day = fields.Integer(
        string="Day",
        default=31,
        help="Day of the month. Clamped to the month's length, so 31 is safe.",
    )
    offset_days = fields.Integer(
        string="Days After / Before",
        default=0,
        help="Days after the financial year end, or days before the expiry, "
        "depending on the shape.",
    )
    document_type_id = fields.Many2one(
        "legal.document.type",
        string="Document",
        ondelete="restrict",
        help="Which register entry the deadline hangs off, for the shape that "
        "counts backwards from an expiry.",
    )

    lead_days = fields.Integer(
        string="Start By (days before)",
        default=30,
        help="How long the filing itself takes, so the board can say 'you had to "
        "start last Tuesday' rather than 'due in sixty days'. Planned backwards "
        "through the body's own calendar.",
    )
    penalty_note = fields.Char(
        translate=True,
        help="The actual formula, in the words of the law: “10% of the tax capped "
        "at IQD 500,000”. A note that says “penalties apply” tells a manager "
        "nothing they can weigh a decision against.",
    )
    instruction = fields.Html(translate=True)
    legal_basis = fields.Char(translate=True)
    legal_basis_url = fields.Char()
    last_verified_on = fields.Date()

    instance_ids = fields.One2many(
        "legal.obligation.instance", "schedule_id", string="Periods"
    )
    instance_count = fields.Integer(compute="_compute_instance_count")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", index=True)
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "An obligation code must be unique per company."
    )

    def _compute_instance_count(self):
        counts = dict(
            self.env["legal.obligation.instance"]._read_group(
                [("schedule_id", "in", self.ids)], ["schedule_id"], ["__count"]
            )
        )
        for schedule in self:
            schedule.instance_count = counts.get(schedule, 0)

    @api.constrains("frequency", "due_month", "due_day", "document_type_id")
    def _check_shape(self):
        for schedule in self:
            if schedule.frequency == "fixed_annual_date" and not (
                1 <= schedule.due_month <= 12 and 1 <= schedule.due_day <= 31
            ):
                raise ValidationError(
                    _("“%s” needs a real month and day.", schedule.name)
                )
            if schedule.frequency == "monthly" and not 1 <= schedule.due_day <= 31:
                raise ValidationError(_("“%s” needs a day of the month.", schedule.name))
            if schedule.frequency == "offset_before_expiry" and not schedule.document_type_id:
                raise ValidationError(
                    _(
                        "“%s” counts backwards from an expiry, so it has to say which "
                        "document expires.",
                        schedule.name,
                    )
                )

    # ==================================================================
    # Generation
    # ==================================================================
    @staticmethod
    def _clamp_day(year, month, day):
        """31 February is not a date, and a schedule that says 31 means "the end"."""
        last = (date(year, month, 1) + relativedelta(months=1, days=-1)).day
        return date(year, month, min(day, last))

    def _entities(self):
        """Which legal persons this schedule applies to.

        A group holds several registered persons and each one files its own
        return; a schedule with no entity therefore fans out rather than
        producing one row somebody has to remember covers three companies.
        """
        self.ensure_one()
        if self.entity_id:
            return self.entity_id
        domain = [("active", "=", True)]
        if self.company_id:
            domain.append(("company_id", "=", self.company_id.id))
        return self.env["legal.entity"].search(domain)

    def _planned_periods(self, horizon=None):
        """The (entity, period key, due date) triples due inside the horizon.

        Deliberately returns *keys* rather than only dates. The key is what the
        unique index is built on, so a schedule whose due date is corrected by a
        circular updates the existing row rather than growing a second one for
        the same period - which is the difference between "the 2026 return" and
        "two rows that are both the 2026 return".

        The entity is part of the triple rather than being appended afterwards,
        because a group holds several registered persons and each one files its
        own return. Deriving the suffix later means guessing from the shape of
        the key, and a monthly key already contains the separator.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        horizon = horizon or (today + relativedelta(months=GENERATION_HORIZON_MONTHS))
        entities = self._entities()
        periods = []

        if self.frequency == "fixed_annual_date":
            for entity in entities:
                for year in range(today.year, horizon.year + 1):
                    due = self._clamp_day(year, self.due_month or 1, self.due_day or 1)
                    periods.append((entity, str(year), due))

        elif self.frequency == "monthly":
            for entity in entities:
                cursor = date(today.year, today.month, 1)
                while cursor <= horizon:
                    due = self._clamp_day(cursor.year, cursor.month, self.due_day or 1)
                    periods.append((entity, "%04d-%02d" % (cursor.year, cursor.month), due))
                    cursor += relativedelta(months=1)

        elif self.frequency == "offset_from_fye":
            for entity in entities:
                year_end = entity.financial_year_end
                if not year_end:
                    # An obligation counted from a year end nobody has recorded
                    # would otherwise be silently skipped for ever, so it is
                    # logged rather than swallowed.
                    _logger.info(
                        "Obligation %s skips %s: no financial year end recorded",
                        self.code, entity.display_name,
                    )
                    continue
                for year in range(today.year - 1, horizon.year + 1):
                    anchor = self._clamp_day(year, year_end.month, year_end.day)
                    due = anchor + relativedelta(days=self.offset_days or 0)
                    if today - relativedelta(months=3) <= due <= horizon:
                        periods.append((entity, "FYE-%s" % year, due))

        elif self.frequency == "offset_before_expiry":
            domain = [
                ("document_type_id", "=", self.document_type_id.id),
                ("state", "=", "active"),
                ("expiry_date", "!=", False),
            ]
            if self.entity_id:
                domain.append(("entity_id", "=", self.entity_id.id))
            for document in self.env["legal.document"].search(domain):
                due = document.expiry_date - relativedelta(days=self.offset_days or 0)
                if due <= horizon:
                    periods.append((document.entity_id, "DOC-%s" % document.id, due))

        return periods

    def _generate(self):
        """Materialise the period rows.

        "Have we filed social security for March" cannot be answered by the
        absence of a record: absence is indistinguishable from nobody having
        looked, and a compliance board built on computed absence reports a
        department as clean the day it stops entering data. So every period is a
        **row with a state**, and this method is what puts it there.
        """
        Instance = self.env["legal.obligation.instance"].sudo()
        created = 0
        for schedule in self:
            company = schedule.company_id or self.env.company
            for entity, period_key, due in schedule._planned_periods():
                key = "%s/%s" % (period_key, entity.id) if entity else period_key
                if Instance.search_count(
                    [
                        ("schedule_id", "=", schedule.id),
                        ("period_key", "=", key),
                        ("company_id", "=", company.id),
                    ]
                ):
                    continue
                Instance.create(
                    {
                        "schedule_id": schedule.id,
                        "period_key": key,
                        "due_on": due,
                        "entity_id": entity.id if entity else False,
                        "company_id": company.id,
                    }
                )
                created += 1
        return created

    def action_generate(self):
        created = self._generate()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Periods generated"),
                "message": _("%s period(s) added.", created),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    @api.model
    def _cron_generate(self, limit=None):
        """Idempotent by construction, not by luck.

        The unique index on (schedule, period, company) is what makes a second
        run of this job write nothing at all - not a "last generated" timestamp
        that drifts, not a flag somebody forgets to set. A generation cron that
        is only *usually* idempotent produces duplicate deadlines, and a
        duplicate deadline is worse than a missing one: people learn to ignore
        the board.
        """
        Cron = self.env["ir.cron"]
        schedules = self.search([], limit=limit)
        under_cron = bool(self.env.context.get("cron_id"))
        if under_cron:
            Cron._commit_progress(remaining=len(schedules))
        created = 0
        for index in range(len(schedules)):
            schedule = schedules[index]
            try:
                created += schedule._generate()
            except Exception:  # noqa: BLE001 - one bad schedule must not stop the run
                _logger.exception("Obligation generation failed on %s", schedule.name)
            if under_cron and not Cron._commit_progress(processed=1):
                break
        _logger.info("Obligation generation: %s period(s) created", created)
        return True


class LegalObligationInstance(models.Model):
    """One period of one obligation - "the 2026 return".

    A dated row, with a state, generated ahead of time. That is the whole design
    decision and it is worth being blunt about the alternative: computing the
    answer from the absence of a filed case makes a department look compliant
    precisely when it has stopped entering data, and gives nobody anywhere to
    record "waived", "filed late" or "we rang them and they said next month".

    ``start_by_date`` - not ``due_on`` - is what the board buckets on, planned
    backwards through the body's own working calendar. "Due in sixty days" is
    decoration; "you had to start this last Tuesday" is a task.
    """

    _name = "legal.obligation.instance"
    _description = "Obligation Period"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_on asc, id desc"
    _rec_names_search = ["period_key", "schedule_id"]

    schedule_id = fields.Many2one(
        "legal.obligation.schedule",
        string="Obligation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    period_key = fields.Char(
        required=True,
        index=True,
        readonly=True,
        help="Which period this row is: 2026, 2026-03. The key the unique index "
        "is built on, so re-running the generator creates nothing.",
    )
    entity_id = fields.Many2one("legal.entity", string="For", ondelete="cascade", index=True)
    body_id = fields.Many2one(
        "legal.gov.body", related="schedule_id.body_id", store=True, index=True
    )
    due_on = fields.Date(required=True, index=True, tracking=True)
    start_by_date = fields.Date(
        compute="_compute_start_by_date",
        store=True,
        index=True,
        help="Due minus the lead time, planned backwards through the body's own "
        "calendar so it does not land on a Friday the office is shut.",
    )
    state = fields.Selection(
        [
            ("not_started", "Not Started"),
            ("in_progress", "In Progress"),
            ("filed", "Filed"),
            ("late", "Late"),
            ("waived", "Waived"),
        ],
        default="not_started",
        required=True,
        index=True,
        tracking=True,
        group_expand=True,
    )
    case_id = fields.Many2one(
        "legal.case", string="File", ondelete="set null", index=True, copy=False
    )
    filed_on = fields.Date(tracking=True)
    penalty_note = fields.Char(
        related="schedule_id.penalty_note",
        readonly=True,
        help="Shown on the row so the figure - “10% of the tax capped at IQD "
        "500,000” - is in front of whoever is deciding whether to file late. Read "
        "through rather than copied: a translated string stored on both sides "
        "would be correct in one language and stale in the other.",
    )
    note = fields.Html(translate=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _schedule_period_company_uniq = models.UniqueIndex(
        "(schedule_id, period_key, company_id)",
        "That period of that obligation already exists.",
    )

    @api.depends("due_on", "schedule_id.lead_days", "schedule_id.body_id")
    def _compute_start_by_date(self):
        """Plan backwards through the body's own calendar.

        A lead time subtracted in calendar days lands on a Friday the office is
        shut roughly one time in seven, and lands inside Eid whenever the
        deadline is near one. ``legal.gov.body._plan_days`` accepts a negative
        count and walks the calendar the other way, which is the only arithmetic
        that produces a date somebody can actually start on.
        """
        for instance in self:
            lead = instance.schedule_id.lead_days or 0
            if not instance.due_on:
                instance.start_by_date = False
                continue
            if not lead:
                instance.start_by_date = instance.due_on
                continue
            body = instance.schedule_id.body_id
            planned = False
            if body:
                anchor = fields.Datetime.to_datetime(instance.due_on)
                planned = body._plan_days(-lead, anchor)
            instance.start_by_date = (
                fields.Date.to_date(planned)
                if planned
                else instance.due_on - relativedelta(days=lead)
            )

    @api.depends("schedule_id", "period_key")
    def _compute_display_name(self):
        for instance in self:
            instance.display_name = "%s - %s" % (
                instance.schedule_id.name or "",
                instance.period_key or "",
            )

    def action_open_case(self):
        """Open the file that discharges the period, or jump to the one that does.

        The obligation carries ``period_key`` onto the case rather than letting
        the two be matched up later by date arithmetic, because date arithmetic
        across a fiscal year end and a Hijri holiday is exactly the kind of
        matching that is right until it is quietly wrong.
        """
        self.ensure_one()
        if self.case_id:
            return {
                "type": "ir.actions.act_window",
                "res_model": "legal.case",
                "res_id": self.case_id.id,
                "view_mode": "form",
            }
        procedure = self.schedule_id.procedure_type_id
        if not procedure:
            raise UserError(
                _(
                    "“%s” has no procedure configured, so there is nothing to open. Say "
                    "which procedure discharges it and this becomes a button.",
                    self.schedule_id.name,
                )
            )
        case = self.env["legal.case"].create(
            {
                "procedure_type_id": procedure.id,
                "entity_id": (self.entity_id or self.env.company.legal_entity_id).id,
                "company_id": self.company_id.id,
                "date_deadline": self.due_on,
                "schedule_id": self.schedule_id.id,
                "obligation_instance_id": self.id,
                "period_key": self.period_key,
                "subject": self.display_name,
            }
        )
        self.write({"case_id": case.id, "state": "in_progress"})
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.case",
            "res_id": case.id,
            "view_mode": "form",
        }

    def action_mark_filed(self):
        self.write({"state": "filed", "filed_on": fields.Date.context_today(self)})
        return True

    def action_waive(self):
        self.write({"state": "waived"})
        return True

    @api.model
    def _cron_mark_late(self, limit=None):
        """Move past-due periods into ``late`` so the board stops looking clean.

        A separate state rather than a computed colour, because "late" is a fact
        the department reports on and argues about, and a colour cannot be
        grouped, counted or explained to an auditor.
        """
        today = fields.Date.context_today(self)
        overdue = self.search(
            [("state", "in", ("not_started", "in_progress")), ("due_on", "<", today)],
            limit=limit,
        )
        for instance in overdue:
            instance.state = "late"
            instance.message_post(
                body=_(
                    "Past due on %(date)s. %(penalty)s",
                    date=instance.due_on,
                    penalty=instance.penalty_note or "",
                )
            )
        return len(overdue)
