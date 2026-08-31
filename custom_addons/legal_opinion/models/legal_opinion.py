from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class LegalOpinion(models.Model):
    """A legal opinion - رأي قانوني - answered once and then frozen.

    The record is first class rather than an attachment on a case because the
    department asks the same question again and again, and the answer it gave
    last time is evidence: quotable, dated and unaltered. That is why issuing an
    opinion photographs its analysis and conclusion into an immutable snapshot,
    turns the fields read-only, and books an outgoing register number in the same
    breath. A signed opinion whose body can still be edited is not an opinion; it
    is a draft that lies about being signed.

    When the answer must change, the opinion is not reopened. A new opinion is
    drafted that supersedes it - the renewal pattern of ``legal.document`` - so
    the chain of what was advised, and when, stays legible.
    """

    _name = "legal.opinion"
    _description = "Legal Opinion"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issued_date desc, id desc"

    #: The fields the freeze protects. Once an opinion is issued these are the
    #: text a signature stands behind, so they are refused to every caller and
    #: changed only by drafting a revision.
    _FROZEN_FIELDS = (
        "subject",
        "question",
        "factual_background",
        "legal_basis",
        "analysis",
        "conclusion",
    )

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Reference",
        default=lambda self: _("New"),
        readonly=True,
        copy=False,
        index="trigram",
        help="The opinion's number, OPN/YYYY/####, allocated when the record is "
        "first saved and never reused.",
    )
    subject = fields.Char(
        string="Subject",
        required=True,
        translate=True,
        tracking=True,
        index="trigram",
        help="The one-line title the precedent library is searched by.",
    )
    requesting_department = fields.Char(
        string="Requesting Department",
        tracking=True,
        help="The department that asked the question - the group the library is "
        "grouped by, because a department reads its own past opinions first.",
    )
    requester_id = fields.Many2one(
        "res.users",
        string="Requested By",
        tracking=True,
        help="The person who referred the question.",
    )

    # ------------------------------------------------------------------
    # The question
    # ------------------------------------------------------------------
    question = fields.Html(
        string="Question Referred",
        sanitize=True,
        help="The question as it was asked, kept verbatim. The answer is only as "
        "precise as the question it answers.",
    )
    factual_background = fields.Html(
        string="Factual Background",
        sanitize=True,
        help="The facts the opinion is given on. If they were wrong the opinion is "
        "revised, not blamed.",
    )

    # ------------------------------------------------------------------
    # Who works it
    # ------------------------------------------------------------------
    legal_officer_id = fields.Many2one(
        "res.users",
        string="Legal Researcher",
        tracking=True,
        help="The officer who researches and drafts the opinion.",
    )
    reviewer_id = fields.Many2one(
        "res.users",
        string="Reviewer",
        tracking=True,
        help="The officer who reviews the draft before it goes up for approval.",
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Approver",
        tracking=True,
        help="The head who issues the opinion. Only an approver may.",
    )
    due_date = fields.Date(
        string="Due Date",
        tracking=True,
        help="When the answer is needed. An opinion past this date and not yet "
        "issued is overdue.",
    )

    # ------------------------------------------------------------------
    # The answer
    # ------------------------------------------------------------------
    legal_basis = fields.Text(
        string="Legal References",
        translate=True,
        help="The laws and articles the opinion rests on - the same "
        "basis / source / last-verified triple the rest of the suite records.",
    )
    legal_basis_url = fields.Char(
        string="Reference Link",
        help="A link to the text of the law relied on.",
    )
    last_verified_on = fields.Date(
        string="References Verified On",
        help="When the cited law was last checked to be still in force. A citation "
        "nobody has re-read since 2019 is a liability, not a support.",
    )
    analysis = fields.Html(
        string="Legal Analysis",
        sanitize=True,
        help="The reasoning. Read-only once the opinion is issued; a change is a "
        "revision.",
    )
    conclusion = fields.Html(
        string="Opinion / Conclusion",
        sanitize=True,
        help="The answer itself. Read-only once the opinion is issued.",
    )

    # ------------------------------------------------------------------
    # Scope
    # ------------------------------------------------------------------
    entity_id = fields.Many2one(
        "legal.entity",
        string="Legal Entity",
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.company.legal_entity_id.id,
        help="Which of our registered persons the opinion is written for.",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    confidential = fields.Boolean(
        string="Confidential",
        tracking=True,
        help="Restricts the opinion to the legal manager and the people named on "
        "it. Used for privileged advice - a labour complaint, a disciplinary "
        "question naming an employee.",
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    state = fields.Selection(
        [
            ("received", "Received"),
            ("assigned", "Assigned"),
            ("drafting", "Drafting"),
            ("review", "Under Review"),
            ("approval", "Awaiting Approval"),
            ("issued", "Issued"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="received",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    issued_date = fields.Date(
        string="Issued On",
        readonly=True,
        copy=False,
        tracking=True,
        help="The day the opinion was signed and frozen.",
    )

    # ------------------------------------------------------------------
    # The frozen copy and its register number
    # ------------------------------------------------------------------
    snapshot_html = fields.Html(
        string="Filed Copy",
        readonly=True,
        copy=False,
        sanitize=False,
        help="The analysis and conclusion as they read at the moment of issue. A "
        "reprint returns this, not a re-render against a since-edited record.",
    )
    snapshot_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Filed PDF",
        readonly=True,
        copy=False,
        ondelete="set null",
    )
    register_correspondence_id = fields.Many2one(
        "legal.correspondence",
        string="Register Entry",
        readonly=True,
        copy=False,
        ondelete="set null",
        help="The outgoing register line allocated when the opinion was issued. "
        "The opinion and the book agree because they are the same act.",
    )
    register_number = fields.Char(
        string="Register Number",
        related="register_correspondence_id.our_number",
        store=True,
        readonly=True,
        help="The صادر number the issued opinion carries.",
    )

    # ------------------------------------------------------------------
    # The revision chain
    # ------------------------------------------------------------------
    supersedes_id = fields.Many2one(
        "legal.opinion",
        string="Supersedes",
        ondelete="set null",
        index=True,
        copy=False,
        help="The earlier opinion this revision replaces.",
    )
    superseded_by_id = fields.Many2one(
        "legal.opinion",
        string="Superseded By",
        ondelete="set null",
        index=True,
        copy=False,
        help="The revision that replaced this opinion. Set, it means this is no "
        "longer the current advice.",
    )
    is_current = fields.Boolean(
        string="Current",
        compute="_compute_is_current",
        store=True,
        index=True,
        help="The one opinion in its chain that the precedent library should show.",
    )
    revision_count = fields.Integer(
        string="Revisions", compute="_compute_revision_count"
    )

    # ------------------------------------------------------------------
    # Related letters
    # ------------------------------------------------------------------
    correspondence_ids = fields.One2many(
        "legal.correspondence", "opinion_id", string="Letters", copy=False
    )
    correspondence_count = fields.Integer(
        string="Letter Count", compute="_compute_correspondence_count"
    )

    # ------------------------------------------------------------------
    # Derived flags
    # ------------------------------------------------------------------
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="Past its due date and not yet issued.",
    )
    is_frozen = fields.Boolean(
        string="Frozen", compute="_compute_is_frozen",
        help="Issued or closed - its text can no longer be edited.",
    )

    _reference_company_uniq = models.Constraint(
        "UNIQUE(name, company_id)",
        "That opinion reference already exists in this company.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("state", "superseded_by_id")
    def _compute_is_current(self):
        for opinion in self:
            opinion.is_current = not opinion.superseded_by_id

    @api.depends("state")
    def _compute_is_frozen(self):
        for opinion in self:
            opinion.is_frozen = opinion.state in ("issued", "closed")

    @api.depends("supersedes_id", "superseded_by_id")
    def _compute_revision_count(self):
        for opinion in self:
            opinion.revision_count = len(opinion._revision_chain())

    @api.depends("correspondence_ids")
    def _compute_correspondence_count(self):
        for opinion in self:
            opinion.correspondence_count = len(opinion.correspondence_ids)

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for opinion in self:
            opinion.is_overdue = bool(
                opinion.due_date
                and opinion.due_date < today
                and opinion.state not in ("issued", "closed")
            )

    def _search_is_overdue(self, operator, value):
        if operator not in ("=", "!="):
            raise UserError(_("Overdue can only be tested for equality."))
        today = fields.Date.context_today(self)
        want_overdue = (operator == "=" and value) or (operator == "!=" and not value)
        overdue = [
            ("due_date", "!=", False),
            ("due_date", "<", today),
            ("state", "not in", ["issued", "closed"]),
        ]
        if want_overdue:
            return overdue
        # The negation: no due date, or not yet past it, or already issued/closed.
        return [
            "|",
            "|",
            ("due_date", "=", False),
            ("due_date", ">=", today),
            ("state", "in", ["issued", "closed"]),
        ]

    # ------------------------------------------------------------------
    # The revision chain, walked both ways
    # ------------------------------------------------------------------
    def _revision_chain(self):
        self.ensure_one()
        ids = []
        node = self
        while node and node.id not in ids:
            ids.append(node.id)
            node = node.supersedes_id
        node = self.superseded_by_id
        while node and node.id not in ids:
            ids.append(node.id)
            node = node.superseded_by_id
        return ids

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains("supersedes_id")
    def _check_no_self_supersede(self):
        for opinion in self:
            if opinion.supersedes_id and opinion.supersedes_id.id == opinion.id:
                raise ValidationError(
                    _("An opinion cannot supersede itself.")
                )

    # ------------------------------------------------------------------
    # Create / write - the reference and the freeze
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) in (False, "New", _("New")):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "legal.opinion"
                ) or _("New")
        return super().create(vals_list)

    def _content_changes(self, fname, new_value):
        """Is this write actually changing a frozen field, or restating it?

        A client that reloads a form and saves it sends every field back;
        refusing a restated value would make the form unusable, so only a real
        change is refused.
        """
        self.ensure_one()
        current = self[fname] or ""
        new_value = new_value or ""
        return (new_value or False) != (current or False)

    def write(self, vals):
        """The freeze.

        ``readonly`` in the view greys the widget but stops nothing arriving over
        RPC, from a server action or from an import. The text a signature stands
        behind is protected here, for every caller, and moved only by a revision.
        """
        if not self.env.context.get("opinion_engine"):
            touched = [name for name in self._FROZEN_FIELDS if name in vals]
            if touched:
                for opinion in self:
                    if opinion.state not in ("issued", "closed"):
                        continue
                    changed = [
                        name
                        for name in touched
                        if opinion._content_changes(name, vals[name])
                    ]
                    if changed:
                        raise UserError(
                            _(
                                "Opinion %(ref)s is issued, so its %(fields)s is "
                                "frozen. The answer is signed and quoted as it "
                                "stands. To change it, issue a revision that "
                                "supersedes this one.",
                                ref=opinion.name,
                                fields=", ".join(
                                    opinion._fields[name]._description_string(self.env)
                                    for name in changed
                                ),
                            )
                        )
        return super().write(vals)

    def unlink(self):
        """An issued opinion is part of the record and cannot be deleted."""
        frozen = self.filtered(lambda o: o.state in ("issued", "closed"))
        if frozen:
            raise UserError(
                _(
                    "%s has been issued and cannot be deleted. It is quoted and "
                    "part of the record. Supersede it with a revision instead.",
                    ", ".join(frozen.mapped("name")),
                )
            )
        return super().unlink()

    # ------------------------------------------------------------------
    # Gates
    # ------------------------------------------------------------------
    def _ensure_approver(self, action):
        if not self.env.user.has_group("legal_core.group_legal_approver"):
            raise UserError(
                _(
                    "Only an approver or the legal manager may %s an opinion.",
                    action,
                )
            )

    def _move_to(self, allowed_from, target):
        for opinion in self:
            if opinion.state not in allowed_from:
                raise UserError(
                    _(
                        "Opinion %(ref)s is %(state)s and cannot move to "
                        "%(target)s from there.",
                        ref=opinion.name,
                        state=dict(self._fields["state"].selection).get(opinion.state),
                        target=dict(self._fields["state"].selection).get(target),
                    )
                )
        self.write({"state": target})

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------
    def action_assign(self):
        for opinion in self:
            if not opinion.legal_officer_id:
                raise UserError(
                    _(
                        "Name a legal researcher before assigning opinion %s.",
                        opinion.name,
                    )
                )
        self._move_to(("received",), "assigned")
        return True

    def action_start_drafting(self):
        self._move_to(("assigned",), "drafting")
        return True

    def action_submit_review(self):
        for opinion in self:
            if not (opinion.analysis or opinion.conclusion):
                raise UserError(
                    _(
                        "There is nothing to review in opinion %s: write the "
                        "analysis or the conclusion first.",
                        opinion.name,
                    )
                )
        self._move_to(("drafting",), "review")
        return True

    def action_request_approval(self):
        self._move_to(("review",), "approval")
        return True

    def action_return_for_revision(self):
        """Send the draft back a step - review to drafting, approval to review."""
        for opinion in self:
            if opinion.state == "review":
                opinion._move_to(("review",), "drafting")
            elif opinion.state == "approval":
                opinion._move_to(("approval",), "review")
            else:
                raise UserError(
                    _(
                        "Opinion %s can only be sent back while under review or "
                        "awaiting approval.",
                        opinion.name,
                    )
                )
        return True

    def action_approve_issue(self):
        """Issue the opinion: approver-only, freezes it and books its number."""
        self._ensure_approver(_("issue"))
        for opinion in self:
            if opinion.state != "approval":
                raise UserError(
                    _(
                        "Opinion %s must be awaiting approval before it is issued.",
                        opinion.name,
                    )
                )
            if not opinion.conclusion:
                raise UserError(
                    _(
                        "Opinion %s has no conclusion. An opinion is issued on its "
                        "answer, so the conclusion cannot be empty.",
                        opinion.name,
                    )
                )
            opinion._freeze_snapshot()
            opinion.with_context(opinion_engine=True).write(
                {
                    "state": "issued",
                    "issued_date": fields.Date.context_today(opinion),
                    "approver_id": opinion.approver_id.id or self.env.user.id,
                }
            )
            opinion._allocate_register_number()
            opinion.message_post(
                body=_(
                    "Issued and frozen%(number)s.",
                    number=(
                        _(" as register %s", opinion.register_number)
                        if opinion.register_number
                        else ""
                    ),
                )
            )
        return True

    def action_close(self):
        """Close an issued opinion. A closing act, so approver-gated."""
        self._ensure_approver(_("close"))
        self._move_to(("issued",), "closed")
        return True

    def action_revise(self):
        """Draft a new opinion that supersedes this one.

        The renewal pattern of ``legal.document``: an issued opinion is never
        reopened, because its text is signed. A revision is a fresh record that
        carries the old reasoning forward as its starting point and points back
        at what it replaced.
        """
        self.ensure_one()
        if self.state not in ("issued", "closed"):
            raise UserError(
                _(
                    "Only an issued opinion is revised. A draft is edited in place."
                )
            )
        if self.superseded_by_id:
            raise UserError(
                _(
                    "Opinion %(ref)s has already been revised by %(new)s.",
                    ref=self.name,
                    new=self.superseded_by_id.name,
                )
            )
        revision = self.copy(
            {
                "state": "drafting",
                "supersedes_id": self.id,
                "subject": self.subject,
            }
        )
        self.superseded_by_id = revision.id
        self.message_post(
            body=_("Superseded by revision %s.", revision.name)
        )
        revision.message_post(
            body=_("Drafted as a revision of %s.", self.name)
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Revision"),
            "res_model": "legal.opinion",
            "res_id": revision.id,
            "view_mode": "form",
            "target": "current",
        }

    # ------------------------------------------------------------------
    # The freeze and the register number
    # ------------------------------------------------------------------
    def _freeze_snapshot(self):
        """Photograph the analysis and conclusion as they read at issue."""
        for opinion in self:
            if opinion.snapshot_html:
                continue
            parts = []
            if opinion.analysis:
                parts.append(
                    "<h3>%s</h3>%s" % (_("Legal Analysis"), opinion.analysis)
                )
            if opinion.conclusion:
                parts.append(
                    "<h3>%s</h3>%s" % (_("Opinion / Conclusion"), opinion.conclusion)
                )
            opinion.with_context(opinion_engine=True).snapshot_html = "".join(parts)

    def _allocate_register_number(self):
        """Book the issued opinion into the outgoing correspondence register.

        The same act that freezes the artifact allocates its صادر number, so the
        opinion and the book cannot disagree: they are one record created once.
        """
        self.ensure_one()
        if self.register_correspondence_id:
            return
        Correspondence = self.env["legal.correspondence"]
        register = self.env.ref(
            "legal_correspondence.register_out_general", raise_if_not_found=False
        )
        if not register or register.company_id != self.company_id:
            register = self.env["legal.register"].search(
                [("direction", "=", "out"), ("company_id", "=", self.company_id.id)],
                limit=1,
            )
        kind = self.env.ref(
            "legal_correspondence.kind_out_letter", raise_if_not_found=False
        )
        if not kind:
            kind = self.env["legal.correspondence.kind"].search(
                [("direction", "=", "out")], limit=1
            )
        if not register or not kind:
            raise UserError(
                _(
                    "No outgoing register or letter kind is configured, so opinion "
                    "%s cannot be booked into the register. Configure an outgoing "
                    "register first.",
                    self.name,
                )
            )
        entry = Correspondence.create(
            {
                "kind_id": kind.id,
                "register_id": register.id,
                "direction": "out",
                # Kept ordinary on purpose: the confidentiality is enforced on the
                # opinion; a secret register line with no body officer would be
                # unreadable to the very approver who just issued it.
                "secrecy": "ordinary",
                "subject": _("Legal Opinion %(ref)s - %(subject)s", ref=self.name, subject=self.subject or ""),
                "body_html": self.snapshot_html,
                "entity_id": self.entity_id.id or False,
                "company_id": self.company_id.id,
                "opinion_id": self.id,
                "our_date": fields.Date.context_today(self),
            }
        )
        entry.action_register()
        self.register_correspondence_id = entry.id

    # ------------------------------------------------------------------
    # Smart buttons
    # ------------------------------------------------------------------
    def action_view_revisions(self):
        self.ensure_one()
        chain = self._revision_chain()
        return {
            "type": "ir.actions.act_window",
            "name": _("Revision Chain"),
            "res_model": "legal.opinion",
            "view_mode": "list,form",
            "domain": [("id", "in", chain)],
            "context": {"default_supersedes_id": self.id},
        }

    def action_view_correspondence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Letters"),
            "res_model": "legal.correspondence",
            "view_mode": "list,form",
            "domain": [("opinion_id", "=", self.id)],
            "context": {
                "default_opinion_id": self.id,
                "default_direction": "out",
                "default_entity_id": self.entity_id.id,
                "default_subject": self.subject or "",
            },
        }
