import uuid
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain

from odoo.addons.legal_core.models.legal_engine import engine_guard, in_engine


class LegalCorrespondenceLine(models.Model):
    """A row of the numbered subject table - جدول الموضوع.

    An Iraqi letter that concerns eleven engineers is **one** letter with eleven
    numbered rows, not eleven letters. Modelling those rows as records rather
    than as free text in the body is what lets the department later answer "which
    letter did we ask for Ahmed's visa in", which is the question the counter
    asks when it loses him.
    """

    _name = "legal.correspondence.line"
    _description = "Correspondence Subject Line"
    _order = "sequence, id"

    correspondence_id = fields.Many2one(
        "legal.correspondence", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Subject / Name", required=True)
    reference = fields.Char(
        string="Reference",
        help="Their identifier for this row: a passport number, a national ID, a "
        "plot number, an invoice number.",
    )
    partner_id = fields.Many2one("res.partner", string="Person", index=True)
    note = fields.Char(string="Remark")


class LegalCorrespondence(models.Model):
    """One entry in the register - قيد في سجل الصادر أو الوارد.

    This is the surface of the whole product, and it is first class rather than a
    line on a file for one blunt reason: **the letter arrives before the file
    exists**. An unprompted tax assessment, a summons, a circular changing a fee
    - all of them land in the mail room addressed to a company that has no open
    case for them, and a design that requires a parent record before an entry can
    be written forces the clerk to either invent a file or keep the letter in a
    drawer until somebody decides. Both of those lose letters.

    ``case_id`` is deliberately **not defined here**. The procedure engine lives
    in ``legal_procedure``, which may not be installed - a customer may want the
    register, the document trail and the official letter without any workflow at
    all - so that module adds the field by ``_inherit``. Declaring a lazy
    ``Many2one('legal.case')`` here would make this module unloadable on its own.

    The rules that make this a register rather than a table:

    * A registered entry's number, date, book and direction can never be
      rewritten. ``readonly`` is a client hint and stops nothing that arrives
      over RPC, so the refusal is in :meth:`write`.
    * A registered entry cannot be deleted. A mistake is **voided** with a
      reason: the number stays, struck through, exactly as a clerk draws a line
      across the page and writes ملغى. A paper register has no deleted rows, and
      a gap in ours is an accusation nobody can answer.
    * A contact note consumes no number, because it never touched the book.
    """

    _name = "legal.correspondence"
    _description = "Correspondence Entry"
    _inherit = ["mail.thread", "mail.activity.mixin", "legal.sequence.mixin"]
    _order = "our_date desc, id desc"
    _rec_names_search = ["our_number", "their_number", "subject"]

    _sequence_field = "our_number"
    _sequence_date_field = "our_date"
    _sequence_index = "register_id"

    #: Written once and then part of the record. See :meth:`write`.
    _LOCKED_ONCE_REGISTERED = ("our_number", "our_date", "register_id", "direction")

    # ------------------------------------------------------------------
    # The book
    # ------------------------------------------------------------------
    register_id = fields.Many2one(
        "legal.register",
        string="Register",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Which book the number comes out of. Empty only for a contact note, "
        "which takes no number.",
    )
    kind_id = fields.Many2one(
        "legal.correspondence.kind",
        string="Kind",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    direction = fields.Selection(
        [
            ("out", "صادر - Outgoing"),
            ("in", "وارد - Incoming"),
            ("internal", "داخلي - Internal"),
        ],
        required=True,
        default="out",
        index=True,
        tracking=True,
    )
    secrecy = fields.Selection(
        [("ordinary", "عادي - Ordinary"), ("secret", "سري - Confidential")],
        required=True,
        default="ordinary",
        index=True,
        tracking=True,
    )
    is_contact_note = fields.Boolean(
        related="kind_id.is_contact_note", store=True, index=True
    )

    # ------------------------------------------------------------------
    # The two numbers. They are not the same field and never will be.
    # ------------------------------------------------------------------
    our_number = fields.Char(
        string="رقم الصادر - Our Number",
        copy=False,
        index="trigram",
        tracking=True,
        help="Our number in our book. Editable while the entry is a draft, so a "
        "department migrating in October types 1,247 and the chain continues "
        "from there. Once registered it is part of the record.",
    )
    our_date = fields.Date(
        string="تاريخ الصادر - Our Date",
        default=fields.Date.context_today,
        copy=False,
        index=True,
        tracking=True,
    )
    their_number = fields.Char(
        string="رقم كتابهم - Their Number",
        index="trigram",
        tracking=True,
        help="Free text on purpose. It follows their format, not ours, and every "
        "attempt to normalise it loses the string the counter will quote back.",
    )
    their_date = fields.Date(string="تاريخ كتابهم - Their Date", tracking=True)

    # ------------------------------------------------------------------
    # Who it is with
    # ------------------------------------------------------------------
    gov_body_id = fields.Many2one(
        "legal.gov.body",
        string="الجهة - Government Body",
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    body_section = fields.Char(
        string="Section / Window",
        help="القسم أو الشعبة: which counter inside the body actually holds it.",
    )
    referred_to_body_id = fields.Many2one(
        "legal.gov.body",
        string="Referred To",
        ondelete="restrict",
        index=True,
        tracking=True,
        help="The hand-off. When the Ministry of Oil refers the file to Residency, "
        "that is an edge between two bodies and it belongs here - not as an extra "
        "date field bolted onto the first body's block, which is where an "
        "unmodelled hand-off always ends up and where it becomes unsearchable.",
    )
    referral_date = fields.Date(string="Referred On", tracking=True)
    body_reference = fields.Char(
        string="Their File Number",
        help="The internal file number the body gave us. The only handle some "
        "counters will answer to on the telephone.",
    )
    entity_id = fields.Many2one(
        "legal.entity",
        string="Legal Entity",
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.company.legal_entity_id.id,
        help="Which of our registered persons this letter is written for.",
    )

    # ------------------------------------------------------------------
    # What it says
    # ------------------------------------------------------------------
    subject = fields.Char(
        string="م/ الموضوع", required=True, translate=True, index="trigram", tracking=True
    )
    body_html = fields.Html(string="نص الكتاب - Letter Text", sanitize=False)
    line_ids = fields.One2many(
        "legal.correspondence.line", "correspondence_id", string="Subject Table"
    )
    letter_template_id = fields.Many2one(
        "legal.letter.template", string="Template", ondelete="restrict"
    )
    signatory_id = fields.Many2one(
        "legal.signatory", string="Signed By", ondelete="restrict", tracking=True
    )
    document_action = fields.Selection(
        [
            ("for_information", "للتفضل بالاطلاع - For Information"),
            ("for_action", "للإجراء اللازم - For Action"),
            ("for_signature", "للتوقيع - For Signature"),
            ("referred", "أحيلت - Referred"),
        ],
        string="Marked",
        default="for_action",
        help="What the manager wrote across the top when the letter was minuted.",
    )

    # ------------------------------------------------------------------
    # The filed copy
    # ------------------------------------------------------------------
    snapshot_html = fields.Html(
        string="Filed Copy",
        readonly=True,
        copy=False,
        sanitize=False,
        help="The letter as it was rendered at the moment it was registered. A "
        "reprint returns this, not a re-render against today's template, because "
        "the template will have changed and the copy in the ministry's file will "
        "not have.",
    )
    snapshot_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Filed PDF",
        readonly=True,
        copy=False,
        ondelete="set null",
    )

    # ------------------------------------------------------------------
    # How it travelled
    # ------------------------------------------------------------------
    outbound_method = fields.Selection(
        [
            ("hand_carried", "تسليم باليد - Hand Carried"),
            ("courier", "بريد سريع - Courier"),
            ("email", "بريد إلكتروني - Email"),
            ("portal", "بوابة إلكترونية - Portal"),
            ("registered_post", "بريد مسجل - Registered Post"),
        ],
        default="hand_carried",
    )
    carried_by_id = fields.Many2one(
        "res.partner",
        string="المراجع / المعتمد - Carried By",
        index=True,
        help="The person who physically walked the letter to the counter. This is "
        "a documented role, not a courtesy note: the Registrar wants his "
        "authorisation letter and a colour scan of his identity card before it "
        "will hand him anything back.",
    )
    channel = fields.Selection(
        [("paper", "ورقي - Paper"), ("online", "إلكتروني - Online"), ("hybrid", "كلاهما - Both")],
        default="paper",
        required=True,
    )
    portal_ref = fields.Char(
        string="Portal Reference",
        help="On an online filing this is often the only handle that exists - "
        "there is no paper number to quote and no counter to walk to.",
    )
    portal_url = fields.Char(string="Portal Link")

    # ------------------------------------------------------------------
    # The reply clock
    # ------------------------------------------------------------------
    # Computed-stored-but-writable rather than an onchange, because an onchange
    # only fires in a form view: an entry created by the mail-room wizard, by an
    # import or by legal_procedure would otherwise carry no reply clock at all,
    # and the clerk would never know the chase was silently switched off.
    reply_expected = fields.Boolean(
        string="Expects A Reply",
        compute="_compute_reply_defaults",
        store=True,
        readonly=False,
        tracking=True,
        help="Taken from the kind, and overridable per entry.",
    )
    reply_days = fields.Integer(
        string="Reply Within (working days)",
        compute="_compute_reply_defaults",
        store=True,
        readonly=False,
        help="Counted through the body's own calendar, so a target does not fall "
        "due on a Friday the counter was never open on.",
    )
    reply_due_on = fields.Date(
        string="Reply Due",
        compute="_compute_reply_due_on",
        store=True,
        index=True,
        help="Planned through the body's working calendar. A contact note with a "
        "promised date moves it: when the section head says 'after Eid', the "
        "clock follows him.",
    )
    reply_state = fields.Selection(
        [
            ("awaiting", "بانتظار الرد - Awaiting"),
            ("answered", "مجاب - Answered"),
            ("late", "متأخر - Late"),
        ],
        string="Reply",
        compute="_compute_reply_state",
        search="_search_reply_state",
        help="Never stored, because it changes at midnight without anybody "
        "writing to the record, and a board that is a day stale is a board "
        "people learn to ignore.",
    )
    reply_to_id = fields.Many2one(
        "legal.correspondence",
        string="In Reply To",
        ondelete="set null",
        index=True,
        help="The entry this one answers, chases or returns.",
    )
    answer_ids = fields.One2many(
        "legal.correspondence", "reply_to_id", string="Answers And Notes"
    )
    is_substantive_reply = fields.Boolean(
        string="Answers Its Parent",
        compute="_compute_is_substantive_reply",
        store=True,
        index=True,
        help="True for an entry that actually answers the one it hangs off. A "
        "receipt, a contact note and our own reminder are all excluded, because a "
        "وصل proves the letter was received and closes nothing - and a system "
        "that counts a receipt as an answer reports a two-day turnaround at a "
        "body that has not yet read the file. Stored so that the reply board can "
        "be searched with one subquery instead of five that need not agree on "
        "which answer they matched.",
    )
    thread_count = fields.Integer(compute="_compute_thread_count")
    round = fields.Integer(
        string="Round",
        default=1,
        tracking=True,
        help="How many times this matter has gone round. Incremented only by an "
        "entry whose kind is 'sent back for completion' - a reminder never "
        "increments it, and a receipt never increments it. This is the number "
        "that makes rework visible instead of hiding it inside a long first "
        "cycle.",
    )

    # ------------------------------------------------------------------
    # The telephone
    # ------------------------------------------------------------------
    spoke_to = fields.Char(
        string="Spoke To",
        help="Who answered. In Iraqi follow-up this is the single most valuable "
        "field on the record.",
    )
    said = fields.Text(string="What They Said")
    promised_on = fields.Date(
        string="Promised For",
        index=True,
        help="The date the counter promised. It moves the reply clock and "
        "suppresses the next chase, so the software stops chasing a body that "
        "has already answered.",
    )

    # ------------------------------------------------------------------
    # Housekeeping
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("draft", "مسودة - Draft"),
            ("registered", "مسجل - Registered"),
            ("void", "ملغى - Void"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    void_reason = fields.Char(string="Reason For Voiding", copy=False, tracking=True)
    verification_token = fields.Char(
        copy=False,
        readonly=True,
        index=True,
        help="Encoded in the QR on the printed letter, so a reader can check the "
        "number against the register. It is not a signature.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "legal_correspondence_attachment_rel",
        "correspondence_id",
        "attachment_id",
        string="Scans",
    )
    attachment_count = fields.Integer(
        string="Scan Count", compute="_compute_attachment_count"
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
    )
    colour = fields.Integer(string="Colour")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _number_register_company_uniq = models.Constraint(
        "UNIQUE(register_id, our_number, company_id)",
        "That number already exists in this register. A register has no repeated "
        "numbers, and a mistaken entry is voided rather than renumbered.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("our_number", "their_number", "subject")
    def _compute_display_name(self):
        for record in self:
            number = record.our_number or record.their_number or _("draft")
            record.display_name = "%s - %s" % (number, record.subject or "")

    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = len(record.attachment_ids)

    def _compute_thread_count(self):
        counts = dict(
            self.env["legal.correspondence"]._read_group(
                [("reply_to_id", "in", self.ids)], ["reply_to_id"], ["__count"]
            )
        )
        for record in self:
            record.thread_count = counts.get(record, 0)

    @api.depends(
        "reply_expected",
        "reply_days",
        "our_date",
        "state",
        "kind_id",
        "gov_body_id",
        "answer_ids.promised_on",
        "answer_ids.state",
    )
    def _compute_reply_due_on(self):
        """When we may reasonably start complaining.

        Two refinements over "date plus seven". The days are counted through the
        body's own calendar, because Iraqi offices work Sunday to Thursday and
        close for Eid, and a target that falls on a closed counter produces an
        escalation nobody believes. And a promise recorded on the telephone wins:
        if the section head said 'after Eid', the clock is his, not ours.
        """
        for record in self:
            if not record.reply_expected or record.state != "registered":
                record.reply_due_on = False
                continue
            promises = record.answer_ids.filtered(
                lambda answer: answer.promised_on and answer.state == "registered"
            ).mapped("promised_on")
            if promises:
                record.reply_due_on = max(promises)
                continue
            start = record.our_date or fields.Date.context_today(record)
            days = record.reply_days or record.kind_id.default_reply_days or 0
            if not days:
                record.reply_due_on = start
                continue
            planned = False
            if record.gov_body_id:
                planned = record.gov_body_id._plan_days(
                    days, datetime.combine(start, time(8, 0))
                )
            record.reply_due_on = (
                planned.date() if planned else start + timedelta(days=days)
            )

    @api.depends("kind_id")
    def _compute_reply_defaults(self):
        for record in self:
            record.reply_expected = record.kind_id.expects_reply
            record.reply_days = record.kind_id.default_reply_days

    @api.depends("state", "direction", "kind_id")
    def _compute_is_substantive_reply(self):
        for record in self:
            kind = record.kind_id
            record.is_substantive_reply = bool(
                record.state == "registered"
                and record.direction != "out"
                and kind
                and not kind.is_contact_note
                and not kind.is_acknowledgement
                and not kind.is_reminder
            )

    @api.depends(
        "reply_expected", "reply_due_on", "state", "answer_ids.is_substantive_reply"
    )
    def _compute_reply_state(self):
        today = fields.Date.context_today(self)
        for record in self:
            if not record.reply_expected or record.state != "registered":
                record.reply_state = False
            elif record._is_answered():
                record.reply_state = "answered"
            elif record.reply_due_on and record.reply_due_on < today:
                record.reply_state = "late"
            else:
                record.reply_state = "awaiting"

    def _is_answered(self):
        self.ensure_one()
        return bool(self.answer_ids.filtered("is_substantive_reply"))

    def _search_reply_state(self, operator, value):
        """Make the board searchable without storing a value that goes stale.

        Expressed as ordinary domains over stored columns, so the database does
        the work rather than every entry being read into memory and filtered.
        The single stored ``is_substantive_reply`` flag on the child is what
        makes "has been answered" one subquery instead of four that need not
        agree on which answer they matched.
        """
        if operator not in ("in", "not in", "=", "!="):
            raise UserError(_("Reply state can only be compared for equality."))
        values = [value] if operator in ("=", "!=") else list(value)
        negate = operator in ("not in", "!=")

        today = fields.Date.context_today(self)
        base = Domain("reply_expected", "=", True) & Domain("state", "=", "registered")
        answered = Domain("answer_ids.is_substantive_reply", "=", True)

        pieces = []
        for wanted in values:
            if wanted == "answered":
                pieces.append(base & answered)
            elif wanted == "late":
                pieces.append(base & ~answered & Domain("reply_due_on", "<", today))
            elif wanted == "awaiting":
                pieces.append(
                    base
                    & ~answered
                    & (
                        Domain("reply_due_on", "=", False)
                        | Domain("reply_due_on", ">=", today)
                    )
                )
        domain = Domain.OR(pieces) if pieces else Domain.FALSE
        return ~domain if negate else domain

    # ------------------------------------------------------------------
    # Onchanges - fill from configuration so the clerk types four fields
    # ------------------------------------------------------------------
    @api.onchange("register_id")
    def _onchange_register_id(self):
        for record in self:
            if record.register_id:
                record.direction = record.register_id.direction
                record.secrecy = record.register_id.secrecy
                if record.register_id.body_id and not record.gov_body_id:
                    record.gov_body_id = record.register_id.body_id

    @api.onchange("kind_id")
    def _onchange_kind_id(self):
        # The reply clock itself is a stored compute, not set here - see
        # _compute_reply_defaults. This onchange only handles what a form has to
        # do immediately: face the entry the right way and clear a number the
        # new kind may not carry.
        for record in self:
            kind = record.kind_id
            if not kind:
                continue
            record.direction = kind.direction
            if kind.is_contact_note:
                record.register_id = False
                record.our_number = False

    @api.onchange("gov_body_id")
    def _onchange_gov_body_id(self):
        for record in self:
            if record.gov_body_id:
                record.channel = record.gov_body_id.channel
                if not record.portal_url:
                    record.portal_url = record.gov_body_id.portal_url
                if record.entity_id and not record.signatory_id:
                    record.signatory_id = self.env["legal.signatory"]._default_for(
                        record.entity_id, record.gov_body_id, record.our_date
                    )

    @api.onchange("letter_template_id")
    def _onchange_letter_template_id(self):
        for record in self:
            template = record.letter_template_id
            if not template:
                continue
            if template.body_id and not record.gov_body_id:
                record.gov_body_id = template.body_id
            if template.signatory_id:
                record.signatory_id = template.signatory_id
            subject, body = template.render_for(record)
            if subject:
                record.subject = subject
            if body:
                record.body_html = body

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("state", "void_reason")
    def _check_void_reason(self):
        for record in self:
            if record.state == "void" and not (record.void_reason or "").strip():
                raise ValidationError(
                    _(
                        "Voiding an entry needs a reason. The number stays in the "
                        "book for ever and somebody will ask, years from now, why "
                        "there is a line drawn across it."
                    )
                )

    @api.constrains("kind_id", "our_number")
    def _check_contact_note_has_no_number(self):
        for record in self:
            if record.kind_id.is_contact_note and record.our_number:
                raise ValidationError(
                    _(
                        "A contact note never touched the register, so it cannot "
                        "carry a register number. Record the call as a note against "
                        "the letter it concerns."
                    )
                )

    @api.constrains("referred_to_body_id", "gov_body_id")
    def _check_referral(self):
        for record in self:
            if (
                record.referred_to_body_id
                and record.referred_to_body_id == record.gov_body_id
            ):
                raise ValidationError(
                    _("A body cannot refer a file to itself.")
                )

    def _must_check_constrains_date_sequence(self):
        # A contact note has no number and no date to agree with.
        return not self.kind_id.is_contact_note

    # ------------------------------------------------------------------
    # Numbering
    # ------------------------------------------------------------------
    def _get_last_sequence_domain(self, relaxed=False):
        """The chain is per register book, per company, and per period.

        The period is *deduced*, not configured: whatever the last number in this
        book looks like decides whether the book restarts in January. A book
        writing ``2026/0148`` restarts; one writing ``1247`` does not; and the
        department is never asked a question it would answer wrongly.
        """
        self.ensure_one()
        if not self.register_id or not self.our_date:
            return "WHERE FALSE", {}
        where_string = (
            "WHERE register_id = %(register_id)s "
            "AND company_id = %(company_id)s "
            "AND our_number IS NOT NULL "
        )
        param = {
            "register_id": self.register_id.id,
            "company_id": self.company_id.id,
        }
        if not relaxed:
            domain = [
                ("register_id", "=", self.register_id.id),
                ("company_id", "=", self.company_id.id),
                ("our_number", "!=", False),
            ]
            if self._origin.id:
                domain.append(("id", "!=", self._origin.id))
            # sudo: the book is complete whatever this user is allowed to read.
            # A number hidden by a record rule is still a number that was used.
            reference = self.sudo().search(domain, order="id desc", limit=1).our_number
            reset = self._deduce_sequence_number_reset(reference) if reference else "year"
            if reset in ("year", "month"):
                where_string += (
                    " AND date_trunc(%(period)s, our_date::timestamp without time zone) "
                    "= date_trunc(%(period)s, %(date)s::timestamp without time zone) "
                )
                param["period"] = reset
                param["date"] = self.our_date
        return where_string, param

    def _get_starting_sequence(self):
        """The shape of the first number in a brand-new book.

        ``ق/2026/0000``, which the incrementer turns into ``ق/2026/0001``. The
        prefix and the padding come from the register's ``ir.sequence`` so that
        an administrator changes them where they expect to.
        """
        self.ensure_one()
        register = self.register_id
        prefix = (register.prefix or "").strip().strip("/")
        padding = register.sequence_id.padding or 4
        year = (self.our_date or fields.Date.context_today(self)).year
        zeroes = "0" * max(padding, 1)
        if prefix:
            return "%s/%s/%s" % (prefix, year, zeroes)
        return "%s/%s" % (year, zeroes)

    # ------------------------------------------------------------------
    # Create / write / unlink - the register rules
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault("verification_token", uuid.uuid4().hex[:16].upper())
            if vals.get("reply_to_id") and "round" not in vals:
                parent = self.browse(vals["reply_to_id"])
                kind = self.env["legal.correspondence.kind"].browse(vals.get("kind_id"))
                vals["round"] = parent.round + (1 if kind.is_return else 0)
        records = super().create(vals_list)
        born_registered = records.filtered(lambda record: record.state == "registered")
        if born_registered:
            born_registered._after_registration()
        return records

    def _value_changes(self, fname, new_value):
        """Is this write actually changing the field, or restating it?

        A client that reloads a form and saves it sends every field back. Raising
        on a restated value would make the form unusable, so only a real change
        is refused.
        """
        self.ensure_one()
        field = self._fields[fname]
        current = self[fname]
        if field.type == "many2one":
            return (new_value or False) != (current.id or False)
        if field.type == "date":
            return fields.Date.to_date(new_value) != current
        return (new_value or False) != (current or False)

    def write(self, vals):
        """The lock, and the key to the drawer.

        ``readonly`` on a field is a client hint: it greys the widget and stops
        nothing that arrives over RPC, from a server action, or from an import.
        The number, the date, the book and the direction of a registered entry
        are what the ministry has in *its* book, so the refusal has to be here.
        """
        # A register entry moves draft -> registered -> void and never back. The
        # number is quoted in the ministry's own book and in replies already
        # written, so un-registering it (state -> draft, then edit or unlink) or
        # un-voiding it must be refused for every caller, engine included - none
        # of them has a legitimate reason to walk the book backwards.
        if "state" in vals:
            allowed_from = {
                "draft": {"draft", "registered", "void"},
                "registered": {"registered", "void"},
                "void": {"void"},
            }
            for record in self:
                target = vals["state"]
                if target not in allowed_from.get(record.state, {record.state}):
                    raise UserError(
                        _(
                            "Entry %(entry)s cannot go from %(old)s back to %(new)s. "
                            "A register moves forward only: a mistake is voided with a "
                            "reason, never un-registered.",
                            entry=record.display_name,
                            old=record.state,
                            new=target,
                        )
                    )

        allocating = in_engine()
        if not allocating:
            locked = [name for name in self._LOCKED_ONCE_REGISTERED if name in vals]
            if locked:
                for record in self:
                    if record.state == "draft":
                        continue
                    changed = [
                        name for name in locked if record._value_changes(name, vals[name])
                    ]
                    if changed:
                        raise UserError(
                            _(
                                "Entry %(entry)s is already in the register, so its "
                                "%(fields)s cannot be changed. The ministry has this "
                                "number in its own book. Void it with a reason and "
                                "register a fresh entry - that is what a line drawn "
                                "across a page means.",
                                entry=record.display_name,
                                fields=", ".join(
                                    record._fields[name]._description_string(self.env)
                                    for name in changed
                                ),
                            )
                        )

        becoming = self.browse()
        if vals.get("state") == "registered":
            becoming = self.filtered(lambda record: record.state != "registered")

        result = super().write(vals)

        if becoming:
            becoming._after_registration()
        return result

    def unlink(self):
        """Only a draft may be deleted.

        The rest is the book. A number that was allocated is quoted on an
        envelope, in the ministry's own register and probably in a reply that has
        already been written, and deleting the row leaves a gap nobody can
        explain.
        """
        registered = self.filtered(lambda record: record.state != "draft")
        if registered:
            raise UserError(
                _(
                    "%s cannot be deleted: it has a register number. Void it with a "
                    "reason instead - the number stays in the book, struck through, "
                    "so the register never has a hole in it.",
                    ", ".join(registered.mapped("display_name")),
                )
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def _check_ready_to_register(self):
        for record in self:
            if record.kind_id.is_contact_note:
                if not record.spoke_to:
                    raise UserError(
                        _(
                            "A contact note is only worth keeping if it says who was "
                            "spoken to. That name is the most valuable field on the "
                            "record."
                        )
                    )
                continue
            if not record.register_id:
                raise UserError(
                    _("Entry '%s' needs a register book before it can be numbered.", record.subject)
                )
            if not record.our_date:
                raise UserError(
                    _("Entry '%s' needs a date. The number is allocated against it.", record.subject)
                )
            if record.register_id.company_id != record.company_id:
                raise UserError(
                    _("The register '%s' belongs to another company.", record.register_id.display_name)
                )

    def action_register(self):
        """تسجيل - take the number and put the entry in the book."""
        self._check_ready_to_register()
        self.write({"state": "registered"})
        return True

    def _after_registration(self):
        """Everything that happens at the moment the entry enters the book."""
        for record in self:
            if record.register_id:
                record.register_id._check_may_allocate()
            if not record.kind_id.is_contact_note:
                if not record.our_date:
                    with engine_guard():
                        record.our_date = fields.Date.context_today(record)
                if not record.our_number:
                    record._set_next_sequence()
            record._freeze_snapshot()
            record._create_issued_document()
            record.message_post(
                body=_(
                    "Registered as %(number)s on %(date)s.",
                    number=record.our_number or _("a contact note (no number)"),
                    date=record.our_date or fields.Date.context_today(record),
                )
            )

    def _freeze_snapshot(self):
        """Keep the letter as it read on the day it left.

        Templates change - a new managing director, a corrected address, a
        reworded formula - and a reprint that re-renders against today's template
        produces a document that is not the one in the ministry's file. Freezing
        the rendered body at issue means a reprint is a photocopy, which is what
        the word reprint means.
        """
        for record in self:
            if record.snapshot_html or record.direction == "in":
                continue
            if record.letter_template_id:
                subject, body = record.letter_template_id.render_for(record)
                if subject and not record.subject:
                    record.subject = subject
                record.snapshot_html = body or record.body_html
            elif record.body_html:
                record.snapshot_html = record.body_html

    def _create_issued_document(self):
        """File a document that arrived as a letter, once, in the one register.

        A licence that comes back as an incoming letter is a document; typing it
        again into the document register is how the two registers start
        disagreeing.
        """
        for record in self:
            kind = record.kind_id
            if not kind.is_issued_document or not kind.document_type_id:
                continue
            if not record.entity_id:
                continue
            self.env["legal.document"].create(
                {
                    "name": record.subject or record.display_name,
                    "document_type_id": kind.document_type_id.id,
                    "entity_id": record.entity_id.id,
                    "number": record.their_number or record.our_number,
                    "issuing_body_id": record.gov_body_id.id or False,
                    "issue_date": record.their_date or record.our_date,
                    "company_id": record.company_id.id,
                }
            )

    def action_void(self):
        """Open the void wizard. Voiding without a reason is not offered."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Void Entry"),
            "res_model": "legal.correspondence.void.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_correspondence_id": self.id},
        }

    def action_open_contact_note(self):
        """Record a telephone call or a personal مراجعة against this entry."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Contact Note"),
            "res_model": "legal.contact.note.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_correspondence_id": self.id,
                "default_gov_body_id": self.gov_body_id.id,
            },
        }

    def action_open_thread(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Thread"),
            "res_model": "legal.correspondence",
            "view_mode": "list,form",
            "domain": [("reply_to_id", "=", self.id)],
            "context": {
                "default_reply_to_id": self.id,
                "default_gov_body_id": self.gov_body_id.id,
                "default_entity_id": self.entity_id.id,
                "default_subject": self.subject,
            },
        }

    def action_reply(self):
        """Draft the next entry in this thread, carrying the context forward."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("New Entry In This Thread"),
            "res_model": "legal.correspondence",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_reply_to_id": self.id,
                "default_gov_body_id": self.gov_body_id.id,
                "default_body_section": self.body_section,
                "default_body_reference": self.body_reference,
                "default_entity_id": self.entity_id.id,
                "default_subject": self.subject,
                "default_secrecy": self.secrecy,
                "default_their_number": self.our_number,
            },
        }

    # ------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------
    #: Arabic-Indic digits. Iraqi government output is mixed and both are read
    #: fluently, so the choice is a company setting rather than a house style.
    _ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

    def _localise_numerals(self, text):
        """Print ٠-٩ where the company asked for them.

        Western digits are the default because a reference number gets quoted
        back over the telephone and read off a screen by somebody who typed it
        in Latin, but a department whose whole outgoing book is in Arabic-Indic
        numerals must not have its letters come out inconsistent with its own
        register.
        """
        self.ensure_one()
        text = "" if text is None else str(text)
        if self.company_id.legal_numeral_system == "arabic":
            return text.translate(self._ARABIC_INDIC)
        return text

    def _format_letter_date(self, value):
        """The date as an Iraqi letter writes it, with the Hijri date beside it
        only where the company asked.

        The research behind ``legal_core`` found no rule requiring dual dating on
        Iraqi correspondence - the Registrar's bulletin and الوقائع العراقية use
        Gregorian alone - so this is off by default. The conversion below is the
        arithmetical civil calendar, which can differ by a day from the observed
        one; that is stated here rather than hidden, because a letter is not the
        place to be quietly wrong about a date.
        """
        self.ensure_one()
        if not value:
            return ""
        gregorian = fields.Date.to_string(value)
        if not self.company_id.legal_show_hijri:
            return gregorian
        return "%s  (%s هـ)" % (gregorian, self._to_hijri(value))

    @api.model
    def _to_hijri(self, value):
        """The tabular (arithmetical) Hijri date, as an integer conversion.

        The standard civil-calendar algorithm over the Julian day number; it puts
        Eid al-Fitr 1445 on 10 April 2024 and 1 Ramadan 1446 on 1 March 2025,
        which is what an Iraqi reader expects. It is arithmetic, not observation,
        so a month may begin a day either side of the announced sighting.
        """
        julian_day = value.toordinal() + 1721425
        remainder = julian_day - 1948440 + 10632
        cycles = (remainder - 1) // 10631
        remainder = remainder - 10631 * cycles + 354
        year_in_cycle = ((10985 - remainder) // 5316) * ((50 * remainder) // 17719) + (
            remainder // 5670
        ) * ((43 * remainder) // 15238)
        remainder = (
            remainder
            - ((30 - year_in_cycle) // 15) * ((17719 * year_in_cycle) // 50)
            - (year_in_cycle // 16) * ((15238 * year_in_cycle) // 43)
            + 29
        )
        month = (24 * remainder) // 709
        day = remainder - (709 * month) // 24
        year = 30 * cycles + year_in_cycle - 30
        return "%02d/%02d/%04d" % (day, month, year)

    def action_print_letter(self):
        """طباعة الكتاب - pick the report that matches the letterhead paper.

        An ``ir.actions.report`` carries exactly one paper format, and the two
        letterhead variants need different top margins, so there are two reports.
        The clerk should never have to know that.
        """
        self.ensure_one()
        drawn = self.letter_template_id.letterhead_variant == "drawn"
        xml_id = (
            "legal_correspondence.action_report_official_letter_drawn"
            if drawn
            else "legal_correspondence.action_report_official_letter"
        )
        return self.env.ref(xml_id).report_action(self)

    def action_snapshot_pdf(self):
        """Attach the rendered PDF of the filed copy.

        Offered as a button rather than done automatically at registration
        because it needs wkhtmltopdf, and a department whose server has no PDF
        engine must still be able to register letters.
        """
        self.ensure_one()
        report = self.env.ref(
            "legal_correspondence.action_report_official_letter", raise_if_not_found=False
        )
        if not report:
            raise UserError(_("The official letter report is not installed."))
        try:
            content, _content_type = report._render_qweb_pdf(report.report_name, [self.id])
        except Exception as error:  # noqa: BLE001 - surfaced to the user verbatim
            raise UserError(
                _(
                    "The PDF could not be produced on this server (%s). The filed "
                    "copy is still kept as HTML on the entry.",
                    error,
                )
            ) from error
        attachment = self.env["ir.attachment"].create(
            {
                "name": "%s.pdf" % (self.our_number or self.display_name),
                "type": "binary",
                "raw": content,
                "mimetype": "application/pdf",
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        self.snapshot_attachment_id = attachment
        self.attachment_ids = [(4, attachment.id)]
        return True
