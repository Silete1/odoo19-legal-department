import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: How far ahead the generator materialises recurring rows. Twelve months is
#: enough for a board to plan a year and short enough that a schedule edited in
#: March has not already written three years of wrong dates.
GENERATION_HORIZON_MONTHS = 12

#: Recurring frequency to a step in months. A one-off obligation is a due date,
#: not a recurrence, and is handled separately.
FREQUENCY_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}


class LegalContractObligation(models.Model):
    """A contractual obligation - a thing one side must do.

    Either a one-off - "deliver the goods by 30 June" - or recurring - "pay on
    the first of every month". The recurring shape borrows the generator idea
    from the statutory obligation engine in ``legal_procedure``: rather than
    computing whether March's payment happened from the absence of a record, it
    materialises a dated row per period so the answer is a fact with a state that
    a compliance board can group, count and escalate on.
    """

    _name = "legal.contract.obligation"
    _description = "Contract Obligation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_date asc, id desc"
    _rec_names_search = ["name", "clause_reference"]

    contract_id = fields.Many2one(
        "legal.contract",
        string="Contract",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(
        string="Obligation",
        required=True,
        translate=True,
        help="A short label: 'Monthly rent', 'Annual audit delivery'.",
    )
    clause_reference = fields.Char(
        string="Clause",
        help="Which clause of the contract this obligation comes from, e.g. '7.2'.",
    )
    description = fields.Text(translate=True)
    responsible_party = fields.Selection(
        [
            ("ours", "Us"),
            ("theirs", "The Counterparty"),
        ],
        string="Owed By",
        default="ours",
        required=True,
        index=True,
    )
    responsible_user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        index=True,
        help="Who on our side chases or performs this obligation.",
    )

    # ------------------------------------------------------------------
    # Shape: one-off or recurring
    # ------------------------------------------------------------------
    frequency = fields.Selection(
        [
            ("one_off", "One-off"),
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semiannual", "Every 6 Months"),
            ("annual", "Annual"),
        ],
        default="one_off",
        required=True,
        index=True,
    )
    due_date = fields.Date(
        string="Due Date",
        index=True,
        tracking=True,
        help="For a one-off obligation, the single date it is due.",
    )
    start_date = fields.Date(
        string="First Due",
        help="For a recurring obligation, the date of the first occurrence. The "
        "generator steps forward from here.",
    )
    end_date = fields.Date(
        string="Recurs Until",
        help="Optional. When empty, the generator plans a rolling twelve months "
        "ahead.",
    )
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="contract_id.currency_id", store=True)

    # ------------------------------------------------------------------
    # Status of the obligation itself (a one-off closes here; a recurring one
    # is really tracked on its instances)
    # ------------------------------------------------------------------
    status = fields.Selection(
        [
            ("pending", "Pending"),
            ("done", "Done"),
            ("waived", "Waived"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
        group_expand=True,
    )
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="A one-off obligation that is still pending after its due date. Read "
        "live rather than stored, because it becomes true at midnight with nobody "
        "writing to the record.",
    )
    completion_date = fields.Date(copy=False)
    evidence_document_id = fields.Many2one(
        "legal.document",
        string="Evidence",
        ondelete="set null",
        help="The register entry that evidences performance, where there is one.",
    )
    reminder_lead_days = fields.Integer(
        string="Remind (days before)",
        default=7,
        help="How many days before the due date to raise an activity to chase it.",
    )

    instance_ids = fields.One2many(
        "legal.contract.obligation.instance", "obligation_id", string="Occurrences"
    )
    instance_count = fields.Integer(compute="_compute_instance_count")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("status", "due_date", "frequency")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for obligation in self:
            obligation.is_overdue = bool(
                obligation.frequency == "one_off"
                and obligation.status == "pending"
                and obligation.due_date
                and obligation.due_date < today
            )

    def _search_is_overdue(self, operator, value):
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise ValueError(_("Overdue can only be tested for true or false."))
        today = fields.Date.context_today(self)
        wants_overdue = (operator == "=" and value) or (operator == "!=" and not value)
        if wants_overdue:
            # A one-off, still pending, whose due date has passed. Written as an
            # explicit conjunction so the meaning does not depend on the reader
            # guessing the default operator.
            return [
                "&",
                "&",
                ("frequency", "=", "one_off"),
                ("status", "=", "pending"),
                ("due_date", "<", today),
            ]
        # The negation of that conjunction, kept as an explicit disjunction. The
        # trailing clause makes a one-off with no due date read as "not overdue"
        # rather than falling through the gap a bare NULL comparison leaves.
        return [
            "|",
            "|",
            "|",
            ("frequency", "!=", "one_off"),
            ("status", "!=", "pending"),
            ("due_date", ">=", today),
            ("due_date", "=", False),
        ]

    def _compute_instance_count(self):
        counts = dict(
            self.env["legal.contract.obligation.instance"]._read_group(
                [("obligation_id", "in", self.ids)], ["obligation_id"], ["__count"]
            )
        )
        for obligation in self:
            obligation.instance_count = counts.get(obligation, 0)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_mark_done(self):
        self.write(
            {"status": "done", "completion_date": fields.Date.context_today(self)}
        )
        return True

    def action_waive(self):
        self._ensure_manager()
        self.write({"status": "waived"})
        return True

    def _ensure_manager(self):
        if not self.env.user.has_group("legal_core.group_legal_manager"):
            raise UserError(
                _("Only the legal manager may waive a contractual obligation.")
            )

    # ==================================================================
    # Recurring generation
    # ==================================================================
    @staticmethod
    def _clamp_day(year, month, day):
        last = (date(year, month, 1) + relativedelta(months=1, days=-1)).day
        return date(year, month, min(day, last))

    def _planned_due_dates(self, horizon=None):
        """The due dates of a recurring obligation inside the horizon.

        Returns plain dates; the period key the unique index is built on is the
        ISO date, so correcting a schedule updates the existing occurrence rather
        than growing a second row for the same period.
        """
        self.ensure_one()
        if self.frequency == "one_off":
            return []
        today = fields.Date.context_today(self)
        horizon = horizon or (today + relativedelta(months=GENERATION_HORIZON_MONTHS))
        anchor = self.start_date or self.due_date or today
        end = min(self.end_date or horizon, horizon)
        step = FREQUENCY_MONTHS[self.frequency]
        # Fast-forward the cursor so a schedule anchored years ago does not spin
        # through every historical period before reaching the useful window.
        floor = today - relativedelta(months=1)
        cursor = anchor
        while cursor < floor:
            cursor += relativedelta(months=step)
        dates = []
        while cursor <= end:
            dates.append(cursor)
            cursor += relativedelta(months=step)
        return dates

    def _generate(self):
        """Materialise the occurrence rows, idempotently.

        Idempotent by the unique index on (obligation, period, company), not by a
        flag anybody has to remember to set: a second run writes nothing at all,
        so a duplicate deadline - which is worse than a missing one, because
        people learn to ignore the board - cannot arise.
        """
        Instance = self.env["legal.contract.obligation.instance"].sudo()
        created = 0
        for obligation in self:
            if obligation.frequency == "one_off":
                continue
            company = obligation.company_id or self.env.company
            for due in obligation._planned_due_dates():
                period_key = fields.Date.to_string(due)
                if Instance.search_count(
                    [
                        ("obligation_id", "=", obligation.id),
                        ("period_key", "=", period_key),
                        ("company_id", "=", company.id),
                    ]
                ):
                    continue
                Instance.create(
                    {
                        "obligation_id": obligation.id,
                        "period_key": period_key,
                        "due_date": due,
                        "amount": obligation.amount,
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
                "title": _("Occurrences generated"),
                "message": _("%s occurrence(s) added.", created),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    @api.model
    def _cron_generate(self, limit=None):
        obligations = self.search([("frequency", "!=", "one_off")], limit=limit)
        created = 0
        for obligation in obligations:
            try:
                created += obligation._generate()
            except Exception:  # noqa: BLE001 - one bad schedule must not stop the run
                _logger.exception(
                    "Contract obligation generation failed on %s", obligation.name
                )
        _logger.info("Contract obligation generation: %s occurrence(s) created", created)
        return True


class LegalContractObligationInstance(models.Model):
    """One occurrence of a recurring obligation - "the March rent".

    A dated row with a state, generated ahead of time and carrying the company,
    the responsible user, the contract and the due date, so that the integrator
    can union it with every other dated obligation in the department into one
    deadline board without this model having to know that board exists.
    """

    _name = "legal.contract.obligation.instance"
    _description = "Contract Obligation Occurrence"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_date asc, id desc"
    _rec_names_search = ["period_key", "obligation_id"]

    obligation_id = fields.Many2one(
        "legal.contract.obligation",
        string="Obligation",
        required=True,
        ondelete="cascade",
        index=True,
    )
    contract_id = fields.Many2one(
        related="obligation_id.contract_id", store=True, index=True
    )
    period_key = fields.Char(
        required=True,
        readonly=True,
        index=True,
        help="Which occurrence this row is (the ISO due date). The key the unique "
        "index is built on, so re-running the generator creates nothing.",
    )
    due_date = fields.Date(required=True, index=True, tracking=True)
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="obligation_id.currency_id", store=True)
    responsible_party = fields.Selection(
        related="obligation_id.responsible_party", store=True, index=True
    )
    responsible_user_id = fields.Many2one(
        related="obligation_id.responsible_user_id", store=True, index=True
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("done", "Done"),
            ("late", "Late"),
            ("waived", "Waived"),
        ],
        default="pending",
        required=True,
        index=True,
        tracking=True,
        group_expand=True,
    )
    completion_date = fields.Date(copy=False)
    note = fields.Html(translate=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _obligation_period_company_uniq = models.UniqueIndex(
        "(obligation_id, period_key, company_id)",
        "That occurrence of that obligation already exists.",
    )

    @api.depends("obligation_id", "period_key", "due_date")
    def _compute_display_name(self):
        for instance in self:
            instance.display_name = "%s - %s" % (
                instance.obligation_id.name or "",
                instance.period_key or "",
            )

    def action_mark_done(self):
        self.write(
            {"state": "done", "completion_date": fields.Date.context_today(self)}
        )
        return True

    def action_waive(self):
        if not self.env.user.has_group("legal_core.group_legal_manager"):
            raise UserError(
                _("Only the legal manager may waive a contractual obligation.")
            )
        self.write({"state": "waived"})
        return True

    @api.model
    def _cron_mark_late(self, limit=None):
        """Move past-due occurrences into ``late`` so the board stops looking clean."""
        today = fields.Date.context_today(self)
        overdue = self.search(
            [("state", "=", "pending"), ("due_date", "<", today)], limit=limit
        )
        for instance in overdue:
            instance.state = "late"
            instance.message_post(body=_("Past due on %(date)s.", date=instance.due_date))
        return len(overdue)
