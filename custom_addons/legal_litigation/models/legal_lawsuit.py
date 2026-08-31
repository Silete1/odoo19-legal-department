from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

#: The lifecycle of a case, in the order it walks. A Selection rather than the
#: procedure engine's configurable steps because a lawsuit's stages are fixed by
#: the court's own procedure, not by a consultant's configuration: every case
#: everywhere passes assessment, filing, hearing and judgment, and the value of
#: the field is that a manager can group the whole docket on it and read the
#: shape of the department's exposure at a glance.
LAWSUIT_STATE_SELECTION = [
    ("assessment", "Assessment (تقييم)"),
    ("preparation", "Preparation (إعداد)"),
    ("filed", "Filed (مقيدة)"),
    ("in_progress", "In Progress (قيد النظر)"),
    ("judgment", "Judgment (صدور الحكم)"),
    ("appeal", "Under Appeal (طعن)"),
    ("enforcement", "Enforcement (تنفيذ)"),
    ("closed", "Closed (مغلقة)"),
]

#: The states a case is no longer live in. Used by the record rule and by the
#: readiness of the workflow buttons.
CLOSED_STATES = ("closed",)


class LegalLawsuit(models.Model):
    """الدعوى - a case the department is running, for us or against us.

    The court analogue of ``legal.case``: one transactional record that carries
    the whole matter, tracks its lifecycle on a statusbar, and gates the moves
    that must not be made carelessly. Two of those gates are the reason the model
    exists rather than a folder of documents.

    **Filing is blocked without a وكالة بالمرافعة that will stand.** An Iraqi
    court refuses an advocate whose name is not on a litigation power of
    attorney, so ``action_file`` reuses ``legal.poa`` and stops the move outright
    - the same three-dimensional check the counter makes, moved to the desk where
    it costs a click instead of a hearing.

    **Closing is a separated duty.** The clerk who runs the file cannot be the
    one who declares it lost or settled; the close is gated to an approver and
    demands a reason, because a case closed without one cannot be learned from.
    """

    _name = "legal.lawsuit"
    _description = "Lawsuit"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, next_deadline asc, id desc"
    _rec_names_search = ["reference", "title", "court_case_number"]

    reference = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        index="trigram",
        default=lambda self: _("New"),
        help="Our own case number, from the litigation sequence: LAW/2026/0007.",
    )
    title = fields.Char(
        required=True,
        translate=True,
        index="trigram",
        tracking=True,
        help="What the department calls the case: مطالبة الوركاء بأجور متأخرة.",
    )
    our_capacity = fields.Selection(
        [
            ("plaintiff", "Plaintiff (مدعي)"),
            ("defendant", "Defendant (مدعى عليه)"),
            ("third_party", "Third Party (شخص ثالث)"),
            ("appellant", "Appellant (طاعن / مستأنِف)"),
            ("appellee", "Appellee (مطعون ضده / مستأنَف عليه)"),
        ],
        required=True,
        default="plaintiff",
        tracking=True,
        index=True,
        help="Which side we are on. It decides who chases whom and how a judgment "
        "against the case is read.",
    )
    party_ids = fields.One2many(
        "legal.lawsuit.party", "lawsuit_id", string="Parties", copy=True
    )
    opponent_names = fields.Char(
        string="Opponents",
        compute="_compute_opponent_names",
        store=True,
        help="The opponents' names in one string, so a case list can show who we "
        "are against without opening the file.",
    )

    court_id = fields.Many2one(
        "legal.court",
        string="Court",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Where the case is being heard. Required before it can be filed.",
    )
    court_body_id = fields.Many2one(
        "legal.gov.body",
        string="Court Body",
        related="court_id.gov_body_id",
        store=True,
        index=True,
        help="The court as a body, if it is registered as one - the handle the "
        "وكالة check and the letter register use.",
    )
    court_case_number = fields.Char(
        string="Court Case No.",
        copy=False,
        tracking=True,
        index="trigram",
        help="The number the court itself put on the case. It belongs to the "
        "court, not to us, so the clerk types it in when the case is registered.",
    )
    court_case_year = fields.Char(
        string="Court Case Year",
        copy=False,
        help="The year the court's number runs in: ٢٠٢٦. Quoted with the number "
        "at every counter, so it is a field of its own rather than buried in one.",
    )

    entity_id = fields.Many2one(
        "legal.entity",
        string="For",
        required=True,
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.company.legal_entity_id,
        help="The company entity the case concerns.",
    )
    subject = fields.Text(
        translate=True,
        help="What the case is about, in the words it will be argued in.",
    )
    claim_amount = fields.Monetary(
        string="Claim Amount",
        currency_field="currency_id",
        tracking=True,
        help="What is being claimed, for us or against us. The department's "
        "exposure, and the number a manager sums across the docket.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False)
        or self.env.company.currency_id,
        required=True,
    )

    lawyer_id = fields.Many2one(
        "res.users",
        string="Advocate",
        tracking=True,
        index=True,
        default=lambda self: self.env.user,
        help="The internal advocate running the case. Their name has to be on a "
        "valid وكالة بالمرافعة before the case can be filed.",
    )
    poa_id = fields.Many2one(
        "legal.poa",
        string="Power Of Attorney",
        ondelete="restrict",
        index=True,
        domain="[('scope', '=', 'litigation')]",
        help="The وكالة بالمرافعة the advocate stands on. Left empty, filing looks "
        "for a valid litigation deed for the advocate; either way, the court will "
        "not hear anybody who is not on one.",
    )
    external_counsel_id = fields.Many2one(
        "res.partner",
        string="External Counsel",
        ondelete="set null",
        help="An outside advocate retained on the case, where one is.",
    )

    state = fields.Selection(
        LAWSUIT_STATE_SELECTION,
        default="assessment",
        required=True,
        index=True,
        tracking=True,
        group_expand=True,
        help="Where the case is in its life. Moved by the buttons on the header, "
        "each of which checks server-side that the move is allowed.",
    )
    risk = fields.Selection(
        [
            ("low", "Low (منخفض)"),
            ("medium", "Medium (متوسط)"),
            ("high", "High (عالٍ)"),
        ],
        tracking=True,
        index=True,
        help="Our own reading of how the case is likely to go. Drives the manager's "
        "attention, not the workflow.",
    )

    hearing_ids = fields.One2many(
        "legal.hearing", "lawsuit_id", string="Hearings", copy=False
    )
    judgment_ids = fields.One2many(
        "legal.judgment", "lawsuit_id", string="Judgments", copy=False
    )
    correspondence_ids = fields.One2many(
        "legal.correspondence", "lawsuit_id", string="Letters", copy=False
    )
    hearing_count = fields.Integer(compute="_compute_counts")
    judgment_count = fields.Integer(compute="_compute_counts")
    correspondence_count = fields.Integer(compute="_compute_counts")
    party_count = fields.Integer(compute="_compute_counts")

    next_hearing_date = fields.Datetime(
        string="Next Hearing",
        compute="_compute_next_hearing_date",
        store=True,
        index=True,
        help="The date of the earliest sitting not yet held. Read off the "
        "hearings, so it moves forward on its own as sittings are minuted.",
    )
    next_deadline = fields.Date(
        string="Next Deadline",
        compute="_compute_next_deadline",
        store=True,
        index=True,
        help="The nearest thing the case is counting down to - the next hearing or "
        "an open appeal window - so the docket can be sorted by what is most "
        "urgent without opening a file.",
    )
    appeal_window_open = fields.Boolean(
        string="Appeal Window Open",
        compute="_compute_next_deadline",
        store=True,
        help="Whether a judgment on this case still has a live, non-extendable "
        "window to challenge it.",
    )
    latest_development = fields.Char(
        string="Latest Development",
        translate=True,
        tracking=True,
        help="One line on where the case stands, for the manager's list. The "
        "detail lives in the hearings and the letters.",
    )

    date_filed = fields.Date(string="Filed On", readonly=True, copy=False, tracking=True)
    date_closed = fields.Date(string="Closed On", readonly=True, copy=False)
    close_reason = fields.Char(string="Closing Reason", readonly=True, copy=False, tracking=True)
    is_closed = fields.Boolean(
        compute="_compute_is_closed", store=True, index=True, string="Closed"
    )

    confidential = fields.Boolean(
        tracking=True,
        help="Restricts the case to the legal manager and the officers of its "
        "court. Litigation is privileged by default, so this is often set.",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgent"), ("2", "Critical")],
        default="0",
        index=True,
        tracking=True,
    )
    colour = fields.Integer(string="Colour")
    note = fields.Html(translate=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("party_ids.role", "party_ids.partner_id")
    def _compute_opponent_names(self):
        for lawsuit in self:
            names = lawsuit.party_ids.filtered(
                lambda party: party.role == "opponent"
            ).mapped("partner_id.display_name")
            lawsuit.opponent_names = "، ".join(name for name in names if name)

    @api.depends("hearing_ids", "judgment_ids", "correspondence_ids", "party_ids")
    def _compute_counts(self):
        for lawsuit in self:
            lawsuit.hearing_count = len(lawsuit.hearing_ids)
            lawsuit.judgment_count = len(lawsuit.judgment_ids)
            lawsuit.correspondence_count = len(lawsuit.correspondence_ids)
            lawsuit.party_count = len(lawsuit.party_ids)

    @api.depends("hearing_ids.date", "hearing_ids.result")
    def _compute_next_hearing_date(self):
        """The next sitting we have not yet held.

        Keyed on the hearing having no recorded result rather than on the clock,
        so it is stable between midnights: a sitting stays "the next hearing"
        until it is minuted, and minuting it rolls the field to the one after.
        """
        for lawsuit in self:
            pending = lawsuit.hearing_ids.filtered(
                lambda hearing: hearing.date and not hearing.result
            ).sorted("date")
            lawsuit.next_hearing_date = pending[:1].date or False

    @api.depends(
        "next_hearing_date",
        "judgment_ids.appeal_deadline",
        "judgment_ids.appeal_filed",
        "state",
    )
    def _compute_next_deadline(self):
        """The nearest date the case is counting down to, and whether an appeal
        window is still open.

        The two live sources are a hearing not yet held and a judgment whose
        non-extendable challenge period has not lapsed and has not been used. The
        earlier of them is what the docket sorts on.
        """
        today = fields.Date.context_today(self)
        for lawsuit in self:
            candidates = []
            if lawsuit.next_hearing_date:
                candidates.append(lawsuit.next_hearing_date.date())
            open_window = False
            for judgment in lawsuit.judgment_ids:
                if (
                    judgment.appeal_deadline
                    and not judgment.appeal_filed
                    and judgment.appeal_deadline >= today
                ):
                    candidates.append(judgment.appeal_deadline)
                    open_window = True
            lawsuit.appeal_window_open = open_window
            lawsuit.next_deadline = min(candidates) if candidates else False

    @api.depends("state")
    def _compute_is_closed(self):
        for lawsuit in self:
            lawsuit.is_closed = lawsuit.state in CLOSED_STATES

    # ==================================================================
    # Create - number it from the sequence
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("reference") or vals.get("reference") == _("New"):
                vals["reference"] = self.env["ir.sequence"].next_by_code(
                    "legal.lawsuit"
                ) or _("New")
        return super().create(vals_list)

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default)
        for vals in vals_list:
            vals.setdefault("reference", _("New"))
        return vals_list

    # ==================================================================
    # The filing gate - a وكالة that will stand, a court and a number
    # ==================================================================
    def _filing_blockers(self):
        """Every reason this case cannot be filed, in one place and in words.

        Returns sentences rather than booleans so the button, the desk row and
        the test all read the same answer.
        """
        self.ensure_one()
        reasons = []
        if not self.court_id:
            reasons.append(_("No court has been chosen. A case is filed at a court."))
        if not self.court_case_number:
            reasons.append(
                _(
                    "The court's own case number has not been recorded. The case "
                    "cannot be tracked at the counter without it."
                )
            )
        poa = self.poa_id or self._find_litigation_poa()
        body = self.court_id.gov_body_id
        if not poa:
            reasons.append(
                _(
                    "No وكالة بالمرافعة is on file for %s, and the court will not "
                    "hear an advocate who is not named on one.",
                    self.lawyer_id.display_name or _("the advocate"),
                )
            )
        elif not poa._is_valid_for(body=body, scope="litigation"):
            reason = poa._blocking_reason(body=body)
            reasons.append(
                reason
                or _(
                    "The وكالة “%s” is not a valid litigation deed for this court.",
                    poa.display_name,
                )
            )
        return reasons

    def _find_litigation_poa(self):
        """A valid litigation deed for the advocate, if one exists.

        Searched by the advocate's system user first and their partner second,
        because a وكالة is granted to a person and the advocate may be recorded
        either way. Only ever used to *find* a deed the clerk did not name; it is
        the filing gate that decides whether the deed will actually stand.
        """
        self.ensure_one()
        if not self.lawyer_id:
            return self.env["legal.poa"]
        partner = self.lawyer_id.partner_id
        candidates = self.env["legal.poa"].search(
            [
                ("scope", "=", "litigation"),
                ("state", "=", "active"),
                ("company_id", "=", self.company_id.id),
                "|",
                ("agent_user_id", "=", self.lawyer_id.id),
                ("agent_partner_id", "=", partner.id),
            ]
        )
        body = self.court_id.gov_body_id
        for poa in candidates:
            if poa._is_valid_for(body=body, scope="litigation"):
                return poa
        return candidates[:1]

    # ==================================================================
    # Workflow - the buttons on the header
    # ==================================================================
    def _set_state(self, new_state, message=None):
        self.ensure_one()
        self.state = new_state
        if message:
            self.message_post(body=message)

    def action_prepare(self):
        for lawsuit in self:
            if lawsuit.state != "assessment":
                raise UserError(
                    _("“%s” is past assessment.", lawsuit.display_name)
                )
            lawsuit._set_state("preparation", _("Moved into preparation."))
        return True

    def action_file(self):
        """Register the case at the court - the move the وكالة gate guards."""
        for lawsuit in self:
            if lawsuit.state not in ("assessment", "preparation"):
                raise UserError(
                    _("“%s” has already been filed.", lawsuit.display_name)
                )
            blockers = lawsuit._filing_blockers()
            if blockers:
                raise UserError(
                    _(
                        "“%(case)s” cannot be filed yet:\n\n%(reasons)s",
                        case=lawsuit.display_name,
                        reasons="\n".join("• %s" % reason for reason in blockers),
                    )
                )
            if not lawsuit.poa_id:
                lawsuit.poa_id = lawsuit._find_litigation_poa()
            lawsuit.date_filed = fields.Date.context_today(lawsuit)
            lawsuit._set_state(
                "filed",
                _(
                    "Filed at %(court)s as case %(number)s.",
                    court=lawsuit.court_id.display_name,
                    number=lawsuit.court_case_number,
                ),
            )
        return True

    def action_start(self):
        for lawsuit in self:
            if lawsuit.state != "filed":
                raise UserError(
                    _("“%s” is not a filed case awaiting a hearing.", lawsuit.display_name)
                )
            lawsuit._set_state("in_progress", _("Now being heard."))
        return True

    def action_to_judgment(self):
        for lawsuit in self:
            if lawsuit.state not in ("in_progress", "appeal"):
                raise UserError(
                    _(
                        "A judgment is recorded on a case that is being heard, not on "
                        "“%s”.",
                        lawsuit.display_name,
                    )
                )
            lawsuit._set_state("judgment", _("Judgment issued."))
        return True

    def action_appeal(self):
        """An adverse move - it demands a reason, so it opens the dialog."""
        self.ensure_one()
        if self.state not in ("judgment", "enforcement"):
            raise UserError(
                _(
                    "“%s” is not at a point where a judgment can be challenged.",
                    self.display_name,
                )
            )
        return self._open_reason_wizard("appeal")

    def action_enforce(self):
        for lawsuit in self:
            if lawsuit.state not in ("judgment", "appeal"):
                raise UserError(
                    _(
                        "Enforcement follows a judgment; “%s” has not reached one.",
                        lawsuit.display_name,
                    )
                )
            lawsuit._set_state("enforcement", _("Moved to enforcement (تنفيذ)."))
        return True

    def action_close(self):
        """Closing is a separated duty and demands a reason, so it opens the dialog."""
        self.ensure_one()
        if self.state in CLOSED_STATES:
            raise UserError(_("“%s” is already closed.", self.display_name))
        self._check_close_rights()
        return self._open_reason_wizard("close")

    def action_reopen(self):
        for lawsuit in self:
            if lawsuit.state not in CLOSED_STATES:
                raise UserError(_("“%s” is not closed.", lawsuit.display_name))
            lawsuit._check_close_rights()
            lawsuit._engine_reopen()
        return True

    def _engine_reopen(self):
        self.ensure_one()
        self.write({"date_closed": False, "close_reason": False})
        self._set_state("in_progress", _("Re-opened."))

    def _check_close_rights(self):
        """Only an approver or above may close or re-open a case.

        Enforced here, server-side, rather than only by hiding the button: a
        hidden button stops a click, not an RPC, and separation of duties that a
        crafted request can walk around is not separation of duties.
        """
        if not self.env.user.has_group("legal_core.group_legal_approver"):
            raise UserError(
                _(
                    "Only a legal approver or manager may close or re-open a case. "
                    "The advocate who runs a file is not the one who declares it lost "
                    "or settled."
                )
            )

    def _open_reason_wizard(self, action_kind):
        self.ensure_one()
        titles = {
            "close": _("Close Case"),
            "appeal": _("Lodge Appeal / Challenge"),
        }
        return {
            "type": "ir.actions.act_window",
            "name": titles.get(action_kind, _("Reason")),
            "res_model": "legal.lawsuit.reason",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_lawsuit_id": self.id,
                "default_action_kind": action_kind,
            },
        }

    def _apply_close(self, reason):
        self.ensure_one()
        self._check_close_rights()
        self.write(
            {
                "date_closed": fields.Date.context_today(self),
                "close_reason": reason,
            }
        )
        self._set_state("closed", _("Closed: %s", reason))

    def _apply_appeal(self, reason):
        self.ensure_one()
        self._set_state(
            "appeal",
            _("Judgment challenged (طعن): %s", reason),
        )
        self.judgment_ids.filtered(
            lambda judgment: judgment.appeal_deadline and not judgment.appeal_filed
        ).write({"appeal_filed": True})

    # ==================================================================
    # Smart buttons
    # ==================================================================
    def action_open_hearings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Hearings"),
            "res_model": "legal.hearing",
            "view_mode": "calendar,list,form",
            "domain": [("lawsuit_id", "=", self.id)],
            "context": {
                "default_lawsuit_id": self.id,
                "default_court_id": self.court_id.id,
            },
        }

    def action_open_judgments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Judgments"),
            "res_model": "legal.judgment",
            "view_mode": "list,form",
            "domain": [("lawsuit_id", "=", self.id)],
            "context": {
                "default_lawsuit_id": self.id,
                "default_court_id": self.court_id.id,
            },
        }

    def action_open_correspondence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Letters"),
            "res_model": "legal.correspondence",
            "view_mode": "list,form",
            "domain": [("lawsuit_id", "=", self.id)],
            "context": {
                "default_lawsuit_id": self.id,
                "default_gov_body_id": self.court_id.gov_body_id.id,
                "default_entity_id": self.entity_id.id,
                "default_subject": self.title or "",
            },
        }

    # ==================================================================
    # Constraints
    # ==================================================================
    @api.constrains("state", "court_id", "court_case_number")
    def _check_filed_has_court(self):
        for lawsuit in self:
            if lawsuit.state in ("filed", "in_progress", "judgment", "appeal", "enforcement"):
                if not lawsuit.court_id:
                    raise ValidationError(
                        _(
                            "“%s” is recorded as filed but has no court. A filed case "
                            "is filed somewhere.",
                            lawsuit.display_name,
                        )
                    )
                if not lawsuit.court_case_number:
                    raise ValidationError(
                        _(
                            "“%s” is recorded as filed but carries no court case "
                            "number.",
                            lawsuit.display_name,
                        )
                    )

    @api.constrains("claim_amount")
    def _check_claim_amount(self):
        for lawsuit in self:
            if lawsuit.claim_amount < 0:
                raise ValidationError(
                    _("A claim amount cannot be negative.")
                )

    @api.depends("reference", "title")
    def _compute_display_name(self):
        for lawsuit in self:
            if lawsuit.reference and lawsuit.reference != _("New"):
                lawsuit.display_name = "%s - %s" % (lawsuit.reference, lawsuit.title or "")
            else:
                lawsuit.display_name = lawsuit.title or _("New")
