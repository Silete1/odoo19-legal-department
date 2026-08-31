from odoo import _, api, fields, models

from .legal_constants import DOCUMENT_LINE_STATUS_SELECTION, SATISFYING_LINE_STATUS


class LegalCaseDocument(models.Model):
    """One line of the checklist - سطر المستمسكات.

    Everything the product says about a required document collapses into
    ``line_status``: one badge, drawn from a **fixed six-word vocabulary no
    configurer may extend**. غير مطلوب / لم يُقدَّم / مُقدَّم / قيد التدقيق /
    مقبول / مرفوض / منتهي الصلاحية. The closed list is the point. The gate, the
    readiness meter, the phase rail and the desk row all read the same sentence,
    so they can never disagree about whether the file is ready; the moment a
    seventh word can be added, each of those four surfaces has to guess what it
    means and they will guess differently.

    ``company_document_id`` points at the permanent register in ``legal_core``
    rather than holding its own upload. That is what stops the tax card being
    scanned for the eleventh time, and it is what makes an expiring registration
    raise *one* alert instead of one per open file that happens to reference it.

    :meth:`_is_satisfied` and :meth:`_blocking_reason` are the only two places in
    the product that decide whether a document is good enough. Everything else
    asks them.
    """

    _name = "legal.case.document"
    _description = "Case Document Line"
    _order = "case_id, sequence, id"

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", index=True
    )
    requirement_id = fields.Many2one(
        "legal.doc.requirement",
        string="Requirement",
        ondelete="set null",
        index=True,
        help="The configured row this line was instantiated from. Empty on a line "
        "a clerk added because the counter asked for something nobody expected - "
        "which is itself worth knowing, and is how the configuration gets fixed.",
    )
    document_type_id = fields.Many2one(
        "legal.document.type",
        string="Document",
        required=True,
        ondelete="restrict",
        index=True,
    )
    subject_id = fields.Many2one(
        "legal.case.subject",
        string="For",
        ondelete="cascade",
        index=True,
        help="Set on a per-person requirement, so eight experts produce eight "
        "passport lines rather than one line nobody can tick.",
    )
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Demanded At",
        related="requirement_id.step_id",
        store=True,
        index=True,
    )
    company_document_id = fields.Many2one(
        "legal.document",
        string="From The Register",
        ondelete="set null",
        index=True,
        help="The instance in the company's permanent register that satisfies this "
        "line. Pointing at the register rather than re-uploading is what stops the "
        "tax card being scanned for the eleventh time.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        string="Scans",
        help="For a document that belongs to this file alone and has no place in "
        "the permanent register.",
    )
    minimum_grade_id = fields.Many2one(
        "legal.licence.grade", string="Minimum Grade", ondelete="restrict"
    )
    is_required = fields.Boolean(default=True)
    is_blocking = fields.Boolean(
        compute="_compute_line_status",
        store=True,
        index=True,
        help="Whether this line stops the file moving. Computed in the same place "
        "as the status, so a line can never be shown as satisfied and still block.",
    )
    line_status = fields.Selection(
        DOCUMENT_LINE_STATUS_SELECTION,
        string="Status",
        compute="_compute_line_status",
        store=True,
        index=True,
        default="missing",
    )
    # Deliberately NOT stored, and `depends_context` names the reason: this is
    # a translated *sentence*, and a stored one is frozen in whichever language
    # happened to compute it first in that worker - which is how the Arabic
    # queue ended up reading “عقد إيجار مصدق” has not been provided. The status
    # and the blocking flag above stay stored, because those are the facts a
    # manager filters and groups on; only the wording is composed on read.
    blocking_reason = fields.Char(
        compute="_compute_blocking_reason",
        depends_context=("lang",),
        help="Why this line stops the file, in the reader's own language.",
    )
    verified_on = fields.Date(
        help="When somebody actually looked at it, as opposed to when it was "
        "uploaded.",
    )
    verified_by_id = fields.Many2one("res.users", string="Checked By")
    rejected = fields.Boolean(
        help="Set when the counter refused the copy that was handed over. It is a "
        "different fact from 'not provided' and the clerk needs to see which.",
    )
    rejection_reason = fields.Char(translate=True)
    accepted = fields.Boolean(
        string="Counter Kept It",
        help="Handing a photocopy over the counter is not the same as the counter "
        "keeping it, and a gate that treats the two alike lets a file leave "
        "incomplete.",
    )
    round = fields.Integer(default=1, required=True, index=True)
    superseded = fields.Boolean(
        readonly=True,
        help="Marked when the file is returned for correction. The line is kept, "
        "not deleted: what the counter objected to in round one is the only thing "
        "round two is measured against.",
    )
    copies = fields.Integer(related="requirement_id.copies", readonly=True)
    note = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company", related="case_id.company_id", store=True, index=True
    )

    #: Everything that can change a checklist line's verdict. Named once so
    #: the stored status and the composed sentence can never drift apart.
    _JUDGEMENT_DEPENDS = (
        "is_required",
        "company_document_id",
        "company_document_id.state",
        "company_document_id.expiry_date",
        "attachment_ids",
        "accepted",
        "rejected",
        "rejection_reason",
        "verified_on",
        "minimum_grade_id",
        "superseded",
    )

    def _judge(self):
        """The one place a checklist line is judged. Returns (status, reason).

        Order matters and is deliberate. Rejection beats everything, because a
        counter that refused the copy has said the loudest thing anybody has said
        about this line. Expiry beats acceptance, because a document that was
        accepted in March and lapsed in June is not accepted now - and the whole
        reason ``legal.document`` holds a live expiry check rather than a stored
        flag is so that this line goes red the day it should.

        Split out of the compute so that the stored verdict and the translated
        sentence can be computed by two different methods without two different
        definitions of "blocked".
        """
        self.ensure_one()
        line = self
        today = fields.Date.context_today(self)
        reason = ""
        if not line.is_required:
            status = "not_required"
        elif line.rejected:
            status = "rejected"
            reason = line.rejection_reason or _(
                "The counter refused “%s”.", line.document_type_id.display_name
            )
        elif line.company_document_id:
            document = line.company_document_id
            if not document._is_acceptable_on(today, minimum_grade=line.minimum_grade_id):
                if document._is_expired(today):
                    status = "expired"
                    reason = _(
                        "“%(document)s” expired on %(date)s.",
                        document=document.display_name,
                        date=document.expiry_date,
                    )
                elif line.minimum_grade_id:
                    status = "under_review"
                    reason = _(
                        "“%(document)s” is not at least %(grade)s.",
                        document=document.display_name,
                        grade=line.minimum_grade_id.display_name,
                    )
                else:
                    status = "under_review"
                    reason = _(
                        "“%s” is in the register but is not currently acceptable.",
                        document.display_name,
                    )
            elif line.accepted:
                status = "accepted"
            elif line.verified_on:
                status = "provided"
                reason = _(
                    "“%s” has been handed over but the counter has not kept it yet.",
                    document.display_name,
                )
            else:
                status = "under_review"
                reason = _("“%s” has not been checked yet.", document.display_name)
        elif line.attachment_ids:
            status = "accepted" if line.accepted else "under_review"
            if status == "under_review":
                reason = _(
                    "“%s” has been uploaded but not checked.",
                    line.document_type_id.display_name,
                )
        else:
            status = "missing"
            reason = _("“%s” has not been provided.", line.document_type_id.display_name)
        return status, reason

    def _is_blocking_status(self, status):
        return bool(
            self.is_required
            and not self.superseded
            and status not in SATISFYING_LINE_STATUS
        )

    @api.depends(*_JUDGEMENT_DEPENDS)
    def _compute_line_status(self):
        """The stored half: the facts a manager filters and groups on."""
        for line in self:
            status, _reason = line._judge()
            line.line_status = status
            line.is_blocking = line._is_blocking_status(status)

    # A separate method from the one above, and not by preference: Odoo warns
    # that a compute serving both a stored and a non-stored field will recompute
    # and rewrite the stored ones every time the unstored one is read.
    @api.depends(*_JUDGEMENT_DEPENDS)
    def _compute_blocking_reason(self):
        """The unstored half: the wording, in the language of whoever is reading.

        Not stored, because a stored sentence is frozen in whichever language
        happened to compute it first in that worker - which is exactly how an
        Arabic work queue ends up reading “عقد إيجار مصدق” has not been provided.
        """
        for line in self:
            status, reason = line._judge()
            line.blocking_reason = reason if line._is_blocking_status(status) else ""

    @api.depends("document_type_id", "subject_id")
    def _compute_display_name(self):
        for line in self:
            name = line.document_type_id.display_name or ""
            if line.subject_id:
                name = "%s - %s" % (name, line.subject_id.display_name)
            line.display_name = name

    def _is_satisfied(self):
        """The only definition of "this line is done".

        Read by the gate on a transition, by the readiness meter, by the phase
        rail and by the desk row. One method, so those four can never disagree -
        and they *will* disagree the day any of them reimplements it.
        """
        self.ensure_one()
        return self.superseded or self.line_status in SATISFYING_LINE_STATUS

    def _blocking_reason(self):
        """Why this line stops the file, in the words the clerk needs."""
        self.ensure_one()
        if self._is_satisfied():
            return ""
        return self.blocking_reason or _(
            "“%s” is missing.", self.document_type_id.display_name
        )

    def _supersede_for_new_round(self, new_round):
        """A return does not delete the previous round's lines.

        The lines that were satisfied are marked superseded and kept, and fresh
        lines are raised for the new round. Deleting them would erase what the
        counter objected to, which is the only thing the correction can be
        measured against.
        """
        satisfied = self.filtered(lambda line: line._is_satisfied() and not line.superseded)
        satisfied.write({"superseded": True})
        values = [
            {
                "case_id": line.case_id.id,
                "requirement_id": line.requirement_id.id,
                "document_type_id": line.document_type_id.id,
                "subject_id": line.subject_id.id,
                "is_required": line.is_required,
                "minimum_grade_id": line.minimum_grade_id.id,
                "company_document_id": line.company_document_id.id,
                "round": new_round,
                "sequence": line.sequence,
            }
            for line in satisfied
        ]
        if values:
            self.create(values)
        return True

    def action_pick_from_register(self):
        """Offer the register entries that would actually satisfy this line.

        Filtered to the right type and to what is in force, because a picker
        that lists every document the company has ever held invites a clerk to
        attach last year's card and find out at the counter.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Choose From The Register"),
            "res_model": "legal.document",
            "view_mode": "list,form",
            "target": "new",
            "domain": [
                ("document_type_id", "=", self.document_type_id.id),
                ("state", "=", "active"),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {
                "default_document_type_id": self.document_type_id.id,
                "default_entity_id": self.case_id.entity_id.id,
            },
        }

    def action_mark_accepted(self):
        self.write(
            {
                "accepted": True,
                "rejected": False,
                "verified_on": fields.Date.context_today(self),
                "verified_by_id": self.env.uid,
            }
        )
        for line in self:
            line.case_id._log(
                "document",
                _("“%s” accepted at the counter.", line.document_type_id.display_name),
                closes_step=False,
            )
        return True
