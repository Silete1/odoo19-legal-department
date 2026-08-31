from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class LegalPoa(models.Model):
    """الوكالة - the instrument that lets somebody stand at the counter for us.

    A dedicated model rather than a document type, because a power of attorney is
    the only artefact in the department that is simultaneously a document, a
    permission and a blocker. The Iraqi counter does not merely want to see it
    filed: it will refuse to deal with a person whose name is not on it, for the
    body in question, on the day they turn up. So the POA has to be checkable in
    three dimensions - who, which body, when - and a row in the document register
    can only answer the third.

    That is why ``require_valid_poa`` on a transition genuinely **blocks**.
    Software that warns and proceeds has not prevented the failure, it has moved
    it to the pavement outside the ministry, where it costs a morning instead of
    a click.

    Revocation is a terminating state, not an archive flag. A revoked وكالة is
    still evidence of what the agent was allowed to do last March, and the
    letters filed under it stay valid; deleting or hiding the record would
    silently rewrite them.
    """

    _name = "legal.poa"
    _description = "Power Of Attorney"
    _inherit = ["mail.thread", "mail.activity.mixin", "legal.expiry.mixin"]
    _order = "expiry_date desc, id desc"
    _rec_names_search = ["name", "number", "agent_partner_id"]

    name = fields.Char(
        required=True,
        index="trigram",
        tracking=True,
        help="What the department calls it, e.g. “General power of attorney for Mr Ahmed at the Tax Commission”.",
    )
    number = fields.Char(
        string="Deed Number",
        index="trigram",
        tracking=True,
        help="The number the notary put on it. Quoted at the counter, so it is "
        "searchable rather than buried in a scan.",
    )
    entity_id = fields.Many2one(
        "legal.entity",
        string="Granted By",
        required=True,
        ondelete="cascade",
        index=True,
    )
    agent_partner_id = fields.Many2one(
        "res.partner",
        string="Agent",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="The person who may present the file. The counter checks this name "
        "against the identity card in their hand.",
    )
    agent_user_id = fields.Many2one(
        "res.users",
        string="Agent's System User",
        help="Set where the agent is also a user, so the desk can show them their "
        "own files.",
    )
    agent_is_lawyer = fields.Boolean(
        string="Advocate",
        help="An advocate's power of attorney is registered with the Bar Association and some "
        "counters - the courts above all - will accept nothing else.",
    )
    bar_association_id = fields.Many2one(
        "legal.gov.body",
        string="Bar Association",
        ondelete="restrict",
        help="Which branch of the Bar Association registered it.",
    )
    bar_registration_number = fields.Char(string="Advocate's Registration")
    scope = fields.Selection(
        [
            ("general", "General"),
            ("specific", "Specific"),
            ("litigation", "Litigation"),
        ],
        default="general",
        required=True,
        help="A specific power of attorney names the transaction it covers, and a counter "
        "reads it narrowly. Recording the scope is what lets the gate refuse a "
        "general errand presented on a litigation deed.",
    )
    scope_note = fields.Text(
        translate=True,
        help="For a specific deed: the words it actually uses. The counter reads "
        "these, so paraphrasing them is how a file gets refused.",
    )
    body_ids = fields.Many2many(
        "legal.gov.body",
        string="Valid At",
        help="Which counters accept it. Leave empty for a general deed good "
        "anywhere - but most Iraqi bodies want to see themselves named.",
    )
    notary_office = fields.Char(
        string="Notary",
        translate=True,
        help="Which notary office issued it. Asked for whenever a copy is needed.",
    )
    issue_date = fields.Date(tracking=True)

    state = fields.Selection(
        [
            ("draft", "Being Prepared"),
            ("active", "In Force"),
            ("revoked", "Revoked"),
            ("expired", "Lapsed"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    revoked_on = fields.Date(tracking=True)
    revocation_reason = fields.Char(translate=True, tracking=True)
    document_id = fields.Many2one(
        "legal.document",
        string="Register Entry",
        ondelete="set null",
        help="The scan in the company's permanent register, so the deed is filed "
        "once and reused rather than uploaded per file.",
    )
    attachment_ids = fields.Many2many("ir.attachment", string="Scans")
    case_ids = fields.One2many("legal.case", "poa_id", string="Files")
    case_count = fields.Integer(compute="_compute_case_count")
    note = fields.Html(translate=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _number_company_uniq = models.UniqueIndex(
        "(number, company_id) WHERE number IS NOT NULL",
        "That deed number is already recorded.",
    )

    def _compute_case_count(self):
        counts = dict(
            self.env["legal.case"]._read_group(
                [("poa_id", "in", self.ids)], ["poa_id"], ["__count"]
            )
        )
        for poa in self:
            poa.case_count = counts.get(poa, 0)

    @api.depends("name", "number")
    def _compute_display_name(self):
        for poa in self:
            poa.display_name = (
                "%s (%s)" % (poa.name, poa.number) if poa.number else (poa.name or "")
            )

    @api.constrains("state", "revoked_on")
    def _check_revocation(self):
        for poa in self:
            if poa.state == "revoked" and not poa.revocation_reason:
                raise ValidationError(
                    _(
                        "A revoked power of attorney needs a reason. The agent will ask, the counter "
                        "will ask, and in six months so will the auditor."
                    )
                )

    def _is_valid_for(self, body=None, on_date=None, scope=None):
        """The gate. Who, which body, when - all three, or it is not a pass.

        Asked with a future date when a submission is being planned around a
        known expiry, and with a past date when a filed letter is being
        justified after the fact.
        """
        self.ensure_one()
        if self.state != "active":
            return False
        if not self._is_valid_on(on_date or fields.Date.context_today(self)):
            return False
        if body and self.body_ids and body not in self.body_ids:
            return False
        if scope == "litigation" and self.scope != "litigation":
            return False
        return True

    def _blocking_reason(self, body=None, on_date=None):
        """Why the counter would refuse it - in the words the clerk needs.

        One method, read by the transition guard, the desk panel and the file's
        blocker summary, so the three can never disagree about what is wrong.
        """
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        if self.state == "revoked":
            return _("The power of attorney “%s” has been revoked.", self.display_name)
        if self.state == "draft":
            return _("The power of attorney “%s” has not been registered yet.", self.display_name)
        if self._is_expired(on_date):
            return _(
                "The power of attorney “%(name)s” lapsed on %(date)s.",
                name=self.display_name,
                date=self.expiry_date,
            )
        if body and self.body_ids and body not in self.body_ids:
            return _(
                "The power of attorney “%(name)s” is not registered at %(body)s, and the counter "
                "will not accept it.",
                name=self.display_name,
                body=body.display_name,
            )
        return ""

    def action_activate(self):
        for poa in self:
            if not poa.issue_date:
                raise UserError(
                    _("“%s” cannot be put in force without the date it was issued.", poa.name)
                )
            poa.state = "active"
        return True

    def action_revoke(self):
        """Revocation is a state, never a deletion."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Revoke Power Of Attorney"),
            "res_model": "legal.poa.revoke",
            "view_mode": "form",
            "target": "new",
            "context": {"default_poa_id": self.id},
        }

    def unlink(self):
        raise UserError(
            _(
                "A power of attorney that was in force cannot be deleted - files were presented "
                "under it. Revoke it with a reason, or archive it."
            )
        )

    @api.model
    def _cron_expire(self, limit=None):
        """Move lapsed deeds into the lapsed state.

        Deliberately a cron rather than a compute: ``state`` is what the gate
        reads, and a gate that lets an expired deed through because nothing has
        recomputed since midnight is worse than no gate. The compute
        ``expiry_state`` from the core mixin stays the live answer; this only
        stops a lapsed deed from *looking* in force on a list.
        """
        today = fields.Date.context_today(self)
        lapsed = self.search(
            [("state", "=", "active"), ("expiry_date", "<", today)], limit=limit
        )
        for poa in lapsed:
            poa.state = "expired"
            poa.message_post(body=_("Lapsed on %s.", poa.expiry_date))
        return len(lapsed)
