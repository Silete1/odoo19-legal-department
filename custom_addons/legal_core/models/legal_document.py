from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalDocument(models.Model):
    """The company's permanent document register - سجل مستمسكات الشركة.

    Every dated artefact the company owns lives here exactly once: the
    certificate of incorporation, the tax card, the Chamber identity with its
    class, the contractor classification with its grade, the municipal licence,
    the civil defence permit, a visa, a residency, a power of attorney. One
    register rather than a copy per file, so that an expiring registration
    raises one alert rather than one alert for every open case that happens to
    reference it.

    The rule that matters most here is that **a renewal never edits the record
    it renews**. It creates a new document that supersedes the old one, and the
    old one stays, expired, with the letters that were sent under it. The
    alternative - overwriting the expiry date - is how a department loses the
    ability to answer "what were we operating under in March", which is exactly
    the question an auditor or a court asks. ``unlink`` is refused for the same
    reason: a document that was real is archived, never deleted.
    """

    _name = "legal.document"
    _description = "Legal Document"
    _inherit = ["mail.thread", "mail.activity.mixin", "legal.expiry.mixin"]
    _order = "expiry_date desc, id desc"
    _rec_names_search = ["name", "number"]

    name = fields.Char(required=True, index="trigram", tracking=True)
    document_type_id = fields.Many2one(
        "legal.document.type",
        string="Type",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    kind_id = fields.Many2one(related="document_type_id.kind_id", store=True, index=True)

    entity_id = fields.Many2one(
        "legal.entity",
        string="Belongs To",
        ondelete="restrict",
        index=True,
        help="The legal person this document belongs to. Empty for a document that "
        "belongs to a person rather than to the company. Deletion is restricted: the "
        "document register is permanent, so an entity that still owns documents is "
        "archived, never deleted out from under its own certificate of incorporation.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Person",
        index=True,
        help="For a passport, a residency, a work permit or a personal power of attorney.",
    )

    number = fields.Char(string="Document Number", index="trigram", tracking=True)
    issuing_body_id = fields.Many2one(
        "legal.gov.body", string="Issued By", ondelete="restrict", index=True, tracking=True
    )
    grade_id = fields.Many2one(
        "legal.licence.grade",
        string="Grade / Class",
        ondelete="restrict",
        domain="[('document_type_id', '=', document_type_id)]",
        help="The Chamber's صنف or the Ministry of Planning's درجة. A tender may "
        "demand a specific class, not merely a valid card.",
    )
    issue_date = fields.Date(tracking=True)
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False),
    )

    state = fields.Selection(
        [
            ("active", "In Force"),
            ("superseded", "Superseded"),
            ("cancelled", "Cancelled"),
        ],
        default="active",
        required=True,
        index=True,
        tracking=True,
    )
    is_current = fields.Boolean(
        string="Current",
        compute="_compute_is_current",
        store=True,
        index=True,
        help="The one instance of this type that a checklist should pick up.",
    )
    supersedes_id = fields.Many2one(
        "legal.document", string="Supersedes", ondelete="set null", index=True
    )
    superseded_by_id = fields.Many2one(
        "legal.document", string="Superseded By", ondelete="set null", index=True
    )
    replacement_reason = fields.Char(translate=True)

    attachment_ids = fields.Many2many(
        "ir.attachment", string="Scans", help="The scanned original, and its certified copies."
    )
    attachment_count = fields.Integer(string="Scan Count", compute="_compute_attachment_count")

    confidential = fields.Boolean(
        help="Restricts the document to the legal manager and the officers of the "
        "issuing body. Used for personal papers and anything privileged.",
    )
    note = fields.Html(translate=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _number_type_company_uniq = models.Constraint(
        "UNIQUE(number, document_type_id, company_id)",
        "That document number already exists for this document type.",
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends("state", "superseded_by_id")
    def _compute_is_current(self):
        for document in self:
            document.is_current = document.state == "active" and not document.superseded_by_id

    def _compute_attachment_count(self):
        for document in self:
            document.attachment_count = len(document.attachment_ids)

    @api.onchange("document_type_id", "issue_date")
    def _onchange_document_type(self):
        """Fill the expiry date, the notice window and the renewal lead time from
        the type, so a clerk entering a Chamber identity types the issue date and
        nothing else."""
        for document in self:
            document_type = document.document_type_id
            if not document_type:
                continue
            document.notice_days = document_type.notice_days
            document.renewal_lead_days = document_type.renewal_lead_days
            if document_type.validity_model == "expiry" and document.issue_date:
                document.expiry_date = document._compute_expiry_from_type()
            elif document_type.validity_model == "none":
                document.expiry_date = False

    def _compute_expiry_from_type(self):
        self.ensure_one()
        document_type = self.document_type_id
        if not (self.issue_date and document_type and document_type.validity_model == "expiry"):
            return False
        unit = {"day": "days", "month": "months", "year": "years"}[document_type.validity_uom]
        return self.issue_date + relativedelta(**{unit: document_type.validity_value})

    # ------------------------------------------------------------------
    # Freshness, the second validity model
    # ------------------------------------------------------------------
    def _is_fresh_on(self, on_date=None):
        """For a type that goes stale rather than expiring - a paid utility bill,
        a bank letter, a تأييد. The Ministry of Planning refuses any supporting
        letter issued more than a year before the application; the Registrar
        wants the *latest* electricity bill."""
        self.ensure_one()
        if self.document_type_id.validity_model != "freshness":
            return True
        if not self.issue_date:
            return False
        on_date = on_date or fields.Date.context_today(self)
        window = self.document_type_id.freshness_days or 0
        return (on_date - self.issue_date).days <= window

    def _is_acceptable_on(self, on_date=None, minimum_grade=None):
        """The single question the readiness matrix asks of every document.

        It is deliberately asked about a *date*, because an Iraqi tender demands
        documents ``نافذ الصلاحية عند تاريخ الغلق`` - in force as at the closing
        date - and a check that only knows about today cannot answer it.
        """
        self.ensure_one()
        if self.state != "active":
            return False
        if not self._is_valid_on(on_date or fields.Date.context_today(self)):
            return False
        if not self._is_fresh_on(on_date):
            return False
        if minimum_grade and self.grade_id:
            return self.grade_id.sequence <= minimum_grade.sequence
        if minimum_grade and not self.grade_id:
            return False
        return True

    # ------------------------------------------------------------------
    # Supersession - the reason this register is trustworthy
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        documents = super().create(vals_list)
        documents._supersede_previous()
        return documents

    def _supersede_previous(self):
        """A newly issued document of the same type, for the same owner, retires
        the one it replaces.

        Done on create rather than by a wizard because the common case is a clerk
        recording this year's Chamber card, and asking them to remember to retire
        last year's is asking them to keep two facts in sync by hand - which is
        the failure mode this whole design exists to remove.
        """
        for document in self:
            if not document.is_current or document.supersedes_id:
                continue
            domain = [
                ("id", "!=", document.id),
                ("document_type_id", "=", document.document_type_id.id),
                ("state", "=", "active"),
                ("superseded_by_id", "=", False),
                ("company_id", "=", document.company_id.id),
            ]
            if document.entity_id:
                domain.append(("entity_id", "=", document.entity_id.id))
            if document.partner_id:
                domain.append(("partner_id", "=", document.partner_id.id))
            previous = self.search(domain)
            if not previous:
                continue
            previous.write({"state": "superseded", "superseded_by_id": document.id})
            document.supersedes_id = previous[:1].id
            for old in previous:
                old.message_post(
                    body=_(
                        "Superseded by %(name)s issued on %(date)s.",
                        name=document.name,
                        date=document.issue_date or _("an unrecorded date"),
                    )
                )

    def unlink(self):
        """A document that was real is archived, never deleted.

        Letters were sent under it, checklists were satisfied by it and
        submissions cited it. Deleting the row would silently rewrite all of
        them, and the register would stop being evidence.
        """
        raise UserError(
            _(
                "A document in the register cannot be deleted, because letters and "
                "checklists refer to it. Archive it, or mark it cancelled with a reason."
            )
        )

    def action_archive_cancelled(self):
        self.write({"state": "cancelled", "active": False})
