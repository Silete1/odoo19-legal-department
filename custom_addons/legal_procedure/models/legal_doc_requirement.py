from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class LegalDocumentType(models.Model):
    """The edge core deliberately does not know about.

    ``legal.document.type`` lives in ``legal_core`` because a customer may want
    the body register and the document register with no workflow at all. But the
    moment procedures exist, a document type gains one enormously useful
    property: the procedure that *obtains* it. That single foreign key is what
    turns a blocked checklist line from a dead end into a button - "the tax card
    is missing, start the procedure that produces one" - and it is what lets the
    expiry ladder open the right renewal instead of telling somebody a licence
    lapsed and leaving them to work out which counter reissues it.

    It is added here rather than in core so that core stays honest about its own
    dependencies.
    """

    _inherit = "legal.document.type"

    producer_procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Obtained By",
        ondelete="set null",
        index=True,
        help="The procedure that produces this document. Read by the checklist "
        "when a line is blocked, and by the renewal board when one expires.",
    )
    renewal_procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Renewed By",
        ondelete="set null",
        index=True,
        help="Where a renewal differs from a first issue - and at most Iraqi "
        "counters it does, being shorter and cheaper.",
    )

    def _procedure_for_renewal(self):
        """The file to open when this type expires.

        Prefers the renewal procedure and falls back to the one that first issues
        it, because a department with only the first-issue procedure configured
        should still be offered something rather than nothing.
        """
        self.ensure_one()
        return self.renewal_procedure_type_id or self.producer_procedure_type_id


class LegalDocRequirement(models.Model):
    """A document one procedure demands - المستمسكات المطلوبة.

    The requirement hangs off the procedure type and, optionally, off one step:
    the Registrar wants the lease at submission and the paid electricity bill
    only at the final counter, and a checklist that demands everything on day one
    is a checklist people learn to ignore.

    **``applicability_domain`` is the whole point.** "An MoI approval is needed
    if any founder is foreign" is not a rule about the procedure, it is a rule
    about *this file*, and the difference between expressing it as a domain and
    expressing it as a Python ``if`` is the difference between a product a
    consultant configures and a product a vendor forks. The idiom is the OCA's
    ``tier.definition``: store the filter, evaluate it against the record, and
    let the checklist grow or shrink accordingly.
    """

    _name = "legal.doc.requirement"
    _description = "Document Requirement"
    _order = "procedure_type_id, sequence, id"

    document_type_id = fields.Many2one(
        "legal.document.type",
        string="Document",
        required=True,
        ondelete="restrict",
        index=True,
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Demanded At",
        ondelete="cascade",
        index=True,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
        help="Leave empty for a document the file needs throughout. Naming a step "
        "keeps the day-one checklist to what is actually needed on day one.",
    )
    is_required = fields.Boolean(
        default=True,
        help="A required document blocks the advance. An optional one is listed "
        "so the clerk knows the counter may ask.",
    )
    per_subject = fields.Boolean(
        string="One Per Person",
        help="A passport is per person, a commercial registration is per company. "
        "The checklist expands a per-subject requirement into one line for every "
        "name on the ت list.",
    )
    applicability_domain = fields.Char(
        string="Only When",
        help="A filter evaluated against the file. Leave empty for a document "
        "every file needs.",
    )
    minimum_grade_id = fields.Many2one(
        "legal.licence.grade",
        string="Minimum Grade",
        ondelete="restrict",
        domain="[('document_type_id', '=', document_type_id)]",
        help="A tender does not merely demand a Chamber identity, it demands "
        "صنف ممتاز. A grade requirement is satisfied by any grade at least as senior.",
    )
    copies = fields.Integer(
        string="Copies",
        default=1,
        help="How many the counter keeps. Trivial, and the single most common "
        "reason for a second trip.",
    )
    note = fields.Text(
        translate=True,
        help="What the counter actually wants: stamped by whom, on what paper, "
        "in what colour folder.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # Two partial indexes rather than one plain UNIQUE, because Postgres treats
    # NULLs as distinct: a single UNIQUE over a nullable step_id would happily
    # let the same document be demanded five times "throughout the procedure".
    _document_step_uniq = models.UniqueIndex(
        "(document_type_id, procedure_type_id, step_id) WHERE step_id IS NOT NULL",
        "That document is already demanded at that step.",
    )
    _document_procedure_uniq = models.UniqueIndex(
        "(document_type_id, procedure_type_id) WHERE step_id IS NULL",
        "That document is already demanded throughout this procedure.",
    )

    @api.depends("document_type_id", "step_id")
    def _compute_display_name(self):
        for requirement in self:
            requirement.display_name = requirement.document_type_id.display_name or ""

    @api.constrains("step_id", "procedure_type_id")
    def _check_step_belongs_to_procedure(self):
        for requirement in self:
            if (
                requirement.step_id
                and requirement.step_id.procedure_type_id != requirement.procedure_type_id
            ):
                raise ValidationError(
                    _(
                        "“%(document)s” is demanded at a step belonging to another procedure.",
                        document=requirement.document_type_id.display_name,
                    )
                )

    @api.constrains("applicability_domain")
    def _check_applicability_domain(self):
        case_model = self.env["legal.case"]
        for requirement in self.filtered("applicability_domain"):
            try:
                domain = Domain(safe_eval(requirement.applicability_domain, {"uid": self.env.uid}))
                domain.validate(case_model)
            except ValidationError:
                raise
            except Exception as error:  # noqa: BLE001 - the message is the product
                raise ValidationError(
                    _(
                        "The condition on the “%(document)s” requirement is not a usable "
                        "filter: %(error)s",
                        document=requirement.document_type_id.display_name,
                        error=error,
                    )
                ) from error
            if domain.optimize(case_model).is_false():
                raise ValidationError(
                    _(
                        "The condition on the “%s” requirement can never be true, so the "
                        "document would never be asked for on any file.",
                        requirement.document_type_id.display_name,
                    )
                )

    def _applies_to(self, case):
        """Does this requirement apply to that file?

        Uses :meth:`filtered_domain` so it answers correctly for a file that is
        still being typed, and swallows a broken filter rather than breaking the
        checklist - a requirement that cannot be evaluated is reported by
        ``action_validate`` on the procedure, which is where a configurer will
        look for it.
        """
        self.ensure_one()
        if not self.applicability_domain:
            return True
        try:
            domain = safe_eval(self.applicability_domain, {"uid": self.env.uid})
            return bool(case.filtered_domain(domain))
        except Exception:  # noqa: BLE001
            return True
