from datetime import timedelta

from odoo import _, api, fields, models

#: Which remedy a judgment from each court degree first invites. A default the
#: clerk can override, not a rule - a first-instance judgment given in absentia
#: invites objection before appeal - but right often enough to save the typing.
DEGREE_TO_REMEDY = {
    "first_instance": "appeal",
    "appeal": "cassation",
    "cassation": "cassation",
    "labor": "labor",
    "misdemeanor_felony": "appeal",
    "administrative": "appeal",
    "personal_status": "appeal",
}


class LegalJudgment(models.Model):
    """الحكم - a ruling on the case, and the clock it starts.

    A judgment is worth a model of its own for one reason: التبليغ, the official
    notification, starts a **non-extendable** period to challenge it, and missing
    that period forfeits the right of appeal. So the record's real work is the
    appeal-window engine - it reads the statutory day-count from the configurable
    ``legal.appeal.rule`` table, adds it to the notification date, and turns the
    result into a deadline that is flagged non-extendable, counted down live, and
    put on the advocate's activity list before it lapses.

    The period is never hard-coded. Cassation runs thirty days against a judgment
    and seven against a decision; the labour courts run to thirty of their own;
    objection reopens an in-absentia judgment in ten. Each is a row a customer's
    counsel can read and correct, because a statute a developer buried in a
    compute is a statute nobody can audit.
    """

    _name = "legal.judgment"
    _description = "Judgment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "judgment_date desc, id desc"

    lawsuit_id = fields.Many2one(
        "legal.lawsuit",
        string="Lawsuit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    lawyer_id = fields.Many2one(
        "res.users", related="lawsuit_id.lawyer_id", store=True, index=True
    )
    company_id = fields.Many2one(
        "res.company", related="lawsuit_id.company_id", store=True, index=True
    )
    court_id = fields.Many2one(
        "legal.court",
        string="Court",
        ondelete="restrict",
        index=True,
        help="The court that gave the ruling. Its degree decides which challenge "
        "the ruling invites and how long there is to bring it.",
    )
    judgment_date = fields.Date(
        string="Judgment Date",
        index=True,
        tracking=True,
        help="The day the court pronounced the ruling.",
    )
    ruling_type = fields.Selection(
        [
            ("judgment", "Judgment (حكم)"),
            ("decision", "Decision (قرار)"),
        ],
        default="judgment",
        required=True,
        index=True,
        tracking=True,
        help="A full judgment or an interlocutory decision. Cassation, above all, "
        "runs to a different clock for each.",
    )
    summary = fields.Text(
        translate=True,
        help="What the court ruled, in our own words.",
    )
    in_our_favour = fields.Selection(
        [
            ("favour", "In Our Favour (لصالحنا)"),
            ("partial", "Partly (جزئياً)"),
            ("against", "Against Us (ضدنا)"),
            ("na", "Not Decisive (غير محدد)"),
        ],
        string="Outcome",
        default="na",
        tracking=True,
        index=True,
        help="How the ruling went for us. Read together with our capacity on the "
        "case to decide whether it is worth challenging.",
    )
    amount_awarded = fields.Monetary(
        string="Amount Awarded",
        currency_field="currency_id",
        help="What the ruling ordered paid, for us or against us.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False)
        or self.env.company.currency_id,
        required=True,
    )
    tabligh_date = fields.Date(
        string="Notification Date (التبليغ)",
        index=True,
        tracking=True,
        help="The day the ruling was officially served on us. The appeal window "
        "counts from this date, not from the day of judgment.",
    )

    remedy = fields.Selection(
        selection="_selection_remedy",
        string="Remedy",
        compute="_compute_remedy",
        store=True,
        readonly=False,
        index=True,
        help="The challenge this ruling invites. Defaulted from the court's degree "
        "and editable - an in-absentia judgment is objected to before it is "
        "appealed.",
    )
    appeal_rule_id = fields.Many2one(
        "legal.appeal.rule",
        string="Appeal Rule",
        compute="_compute_appeal_rule",
        store=True,
        readonly=False,
        ondelete="restrict",
        help="The configurable rule whose day-count sets the window. Matched from "
        "the remedy, the ruling type and the court degree, and overridable where a "
        "case needs it.",
    )
    appeal_days = fields.Integer(
        string="Days Allowed",
        related="appeal_rule_id.days",
        readonly=True,
        help="The statutory period from the matched rule.",
    )
    non_extendable = fields.Boolean(
        string="Non-extendable",
        related="appeal_rule_id.non_extendable",
        readonly=True,
        help="Carried from the rule. A statutory window does not stretch, and the "
        "flag is here so nobody treats the deadline as soft.",
    )
    appeal_deadline = fields.Date(
        string="Appeal Deadline",
        compute="_compute_appeal_deadline",
        store=True,
        index=True,
        help="Notification date plus the allowed days. The last day a challenge "
        "can be lodged - after it the right is gone.",
    )
    days_left = fields.Integer(
        string="Days Left",
        compute="_compute_days_left",
        search="_search_days_left",
        help="How long there is to challenge, recomputed on read because it "
        "changes every midnight.",
    )
    appeal_state = fields.Selection(
        [
            ("na", "No Window"),
            ("open", "Open"),
            ("closing_soon", "Closing Soon"),
            ("closed", "Lapsed"),
            ("filed", "Challenged"),
        ],
        string="Appeal Window",
        compute="_compute_appeal_state",
        store=True,
        index=True,
        default="na",
        help="Where the challenge period stands. What the docket groups and "
        "colours on.",
    )
    is_overdue = fields.Boolean(
        string="Window Lapsed",
        compute="_compute_appeal_state",
        store=True,
        help="The window closed without a challenge being lodged. On an adverse "
        "ruling this is a forfeited right - the reason the clock is worth keeping.",
    )
    closing_notice_days = fields.Integer(
        string="Closing Notice (days)",
        default=5,
        help="How many days before the deadline the window starts showing as "
        "closing soon.",
    )
    appeal_filed = fields.Boolean(
        string="Challenge Lodged",
        copy=False,
        tracking=True,
        help="Set when a طعن has been brought against this ruling. It stops the "
        "clock and clears the deadline off the advocate's list.",
    )
    appeal_lawsuit_id = fields.Many2one(
        "legal.lawsuit",
        string="Appeal Case",
        ondelete="set null",
        help="The case opened to run the challenge, where one is.",
    )
    appeal_activity_id = fields.Many2one(
        "mail.activity",
        string="Deadline Activity",
        readonly=True,
        copy=False,
        help="The to-do put on the advocate's list for the deadline. Held so it is "
        "kept in step rather than duplicated.",
    )
    active = fields.Boolean(default=True)

    # ==================================================================
    # Selections and computes
    # ==================================================================
    @api.model
    def _selection_remedy(self):
        return self.env["legal.appeal.rule"]._fields["remedy"].selection

    @api.depends("court_id.degree")
    def _compute_remedy(self):
        for judgment in self:
            if judgment.remedy:
                continue
            judgment.remedy = DEGREE_TO_REMEDY.get(judgment.court_id.degree, "appeal")

    @api.depends("remedy", "ruling_type", "court_id.degree", "company_id")
    def _compute_appeal_rule(self):
        Rule = self.env["legal.appeal.rule"]
        for judgment in self:
            jurisdiction = judgment.court_id.governorate_id
            judgment.appeal_rule_id = Rule._match(
                judgment.remedy,
                ruling_type=judgment.ruling_type,
                court_degree=judgment.court_id.degree,
                jurisdiction=jurisdiction,
                company=judgment.company_id,
            )

    @api.depends("tabligh_date", "appeal_rule_id.days")
    def _compute_appeal_deadline(self):
        for judgment in self:
            if judgment.tabligh_date and judgment.appeal_rule_id.days:
                judgment.appeal_deadline = judgment.tabligh_date + timedelta(
                    days=judgment.appeal_rule_id.days
                )
            else:
                judgment.appeal_deadline = False

    def _compute_days_left(self):
        today = fields.Date.context_today(self)
        for judgment in self:
            judgment.days_left = (
                (judgment.appeal_deadline - today).days
                if judgment.appeal_deadline
                else 0
            )

    def _search_days_left(self, operator, value):
        if not isinstance(value, int):
            raise ValueError(_("Days left can only be compared with a whole number."))
        bound = fields.Date.context_today(self) + timedelta(days=value)
        inverted = {"<": "<", "<=": "<=", ">": ">", ">=": ">=", "=": "=", "!=": "!="}.get(
            operator
        )
        if not inverted:
            raise ValueError(_("Unsupported comparison on days left."))
        return [("appeal_deadline", inverted, bound)]

    @api.depends(
        "appeal_deadline", "appeal_filed", "closing_notice_days"
    )
    def _compute_appeal_state(self):
        """Bucket the challenge period, and flag a lapsed one.

        Follows the product's expiry-state idiom: the state is stored and indexed
        so the docket can be grouped and coloured on it, while the hard reading of
        "has it lapsed" is available live through ``days_left``. A window that
        lapsed unchallenged sets ``is_overdue`` - on an adverse ruling that is a
        forfeited right of appeal, which is exactly what the clock exists to
        prevent.
        """
        today = fields.Date.context_today(self)
        for judgment in self:
            if judgment.appeal_filed:
                judgment.appeal_state = "filed"
                judgment.is_overdue = False
            elif not judgment.appeal_deadline:
                judgment.appeal_state = "na"
                judgment.is_overdue = False
            elif today > judgment.appeal_deadline:
                judgment.appeal_state = "closed"
                judgment.is_overdue = True
            else:
                remaining = (judgment.appeal_deadline - today).days
                judgment.appeal_state = (
                    "closing_soon"
                    if remaining <= (judgment.closing_notice_days or 0)
                    else "open"
                )
                judgment.is_overdue = False

    # ==================================================================
    # The deadline activity - one, kept in step
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        judgments = super().create(vals_list)
        for judgment in judgments:
            if not judgment.court_id and judgment.lawsuit_id.court_id:
                judgment.court_id = judgment.lawsuit_id.court_id
            judgment._sync_appeal_activity()
        return judgments

    def write(self, vals):
        result = super().write(vals)
        if {"tabligh_date", "appeal_rule_id", "appeal_deadline", "appeal_filed",
            "remedy", "ruling_type"} & set(vals):
            self._sync_appeal_activity()
        return result

    def _sync_appeal_activity(self):
        """Ensure exactly one live to-do for the deadline on the advocate's list.

        Idempotent by the stored ``appeal_activity_id``: an existing activity is
        re-dated rather than re-created, and once the challenge is lodged or the
        window lapses the activity is cleared, so the advocate's list never
        carries a dead deadline or two copies of a live one.
        """
        for judgment in self:
            live = (
                judgment.appeal_deadline
                and not judgment.appeal_filed
                and judgment.appeal_state in ("open", "closing_soon")
            )
            existing = judgment.appeal_activity_id
            if existing and not existing.exists():
                existing = judgment.appeal_activity_id = False
            if not live:
                if existing:
                    existing.unlink()
                    judgment.appeal_activity_id = False
                continue
            if existing:
                existing.date_deadline = judgment.appeal_deadline
                continue
            lawyer = judgment.lawsuit_id.lawyer_id
            if not lawyer:
                continue
            activity = judgment.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=judgment.appeal_deadline,
                summary=_(
                    "Non-extendable appeal deadline - %s",
                    judgment.lawsuit_id.reference,
                ),
                note=_(
                    "The window to challenge this ruling closes on %(date)s and does "
                    "not extend.",
                    date=fields.Date.to_string(judgment.appeal_deadline),
                ),
                user_id=lawyer.id,
            )
            judgment.appeal_activity_id = activity

    def action_mark_appealed(self):
        """Record that a challenge was lodged, and stop the clock."""
        for judgment in self:
            judgment.appeal_filed = True
            judgment.message_post(body=_("Challenge lodged; appeal window closed."))
        return True

    @api.depends("lawsuit_id.reference", "judgment_date", "in_our_favour")
    def _compute_display_name(self):
        for judgment in self:
            when = fields.Date.to_string(judgment.judgment_date) if judgment.judgment_date else ""
            judgment.display_name = _(
                "Judgment %(ref)s %(date)s",
                ref=judgment.lawsuit_id.reference or "",
                date=when,
            ).strip()
