from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalDocumentKind(models.Model):
    """A coarse grouping used only for menus and filters: identity papers,
    licences, clearances, contracts, court papers, evidence."""

    _name = "legal.document.kind"
    _description = "Document Kind"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)", "A document kind code must be unique."
    )


class LegalLicenceGrade(models.Model):
    """A class or grade on a licence: the Chamber's صنف (ممتاز، أولى، ثانية) and
    the Ministry of Planning's درجة for contractor classification.

    A ``Many2one`` rather than free text because a tender does not merely demand
    a valid Chamber identity, it demands ``هوية غرفة تجارة صنف (ممتاز) نافذة``,
    and a readiness check cannot evaluate a grade requirement against a string
    somebody typed. ``max_contract_value`` is what actually makes the grade
    mean something.
    """

    _name = "legal.licence.grade"
    _description = "Licence Grade"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    document_type_id = fields.Many2one(
        "legal.document.type", string="Applies To", ondelete="cascade", index=True
    )
    sequence = fields.Integer(
        default=10,
        help="Ascending order of seniority. A requirement for a minimum grade is "
        "satisfied by any grade with a lower or equal sequence.",
    )
    max_contract_value = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False),
    )
    active = fields.Boolean(default=True)


class LegalDocumentType(models.Model):
    """What a piece of paper *is* - نوع المستمسك.

    The type carries everything that is true of every instance: how long it is
    valid for, how far ahead it must be chased, whether it needs certification
    or notarisation or consular legalisation, which body issues it, and - the
    edge that makes the whole prerequisite graph traversable - which procedure
    produces it. That last field is what turns a blocked checklist line into a
    button that says "start the procedure that produces this".

    Two validity models, not one. Most artefacts expire on a date. But directive
    16180 of 2024 made the *latest paid* electricity and water bills mandatory
    attachments at the Registrar, and a utility bill does not expire - it goes
    stale. A freshness window in days models that correctly; an expiry date
    cannot.
    """

    _name = "legal.document.type"
    _description = "Document Type"
    _order = "sequence, name"
    _rec_names_search = ["name", "name_en", "code"]

    name = fields.Char(string="Name (Arabic)", required=True, translate=True, index="trigram")
    name_en = fields.Char(string="Name (English)")
    code = fields.Char(required=True, help="Stable key used by content packs.")
    kind_id = fields.Many2one("legal.document.kind", string="Kind", ondelete="restrict", index=True)
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction", string="Jurisdiction", ondelete="restrict", index=True
    )
    issuing_body_id = fields.Many2one(
        "legal.gov.body", string="Issued By", ondelete="restrict", index=True
    )

    # ------------------------------------------------------------------
    # Validity - two models, because Iraqi practice has two
    # ------------------------------------------------------------------
    validity_model = fields.Selection(
        [
            ("none", "Does Not Expire"),
            ("expiry", "Expires On A Date"),
            ("freshness", "Must Be Recent"),
        ],
        default="expiry",
        required=True,
        help="'Expires on a date' covers a licence or identity. 'Must be recent' "
        "covers a document such as a paid electricity bill or a bank letter, "
        "which never expires but is refused once it is older than the counter "
        "will accept.",
    )
    validity_value = fields.Integer(
        string="Valid For",
        default=1,
        help="Used with the unit below to compute an expiry date from the issue date.",
    )
    validity_uom = fields.Selection(
        [("day", "Days"), ("month", "Months"), ("year", "Years")],
        default="year",
        required=True,
    )
    freshness_days = fields.Integer(
        string="Accepted If Issued Within (days)",
        default=90,
        help="The Ministry of Planning classification system, for example, refuses "
        "any supporting letter issued more than one year before the application.",
    )
    notice_days = fields.Integer(
        string="Notice Period (days)",
        default=30,
        help="How far ahead of expiry this type starts appearing on the renewal board.",
    )
    renewal_lead_days = fields.Integer(
        string="Renewal Lead Time (days)",
        default=0,
        help="How long the renewal actually takes at the body. The renewal board "
        "buckets on expiry minus this, because 'you should have started last week' "
        "is actionable and 'expires in sixty days' is not.",
    )

    # ------------------------------------------------------------------
    # Authenticity - the Iraqi certification ladder
    # ------------------------------------------------------------------
    requires_certified_copy = fields.Boolean(
        string="Certified Copy (مصدقة)",
        help="A photocopy stamped طبق الأصل by the issuing body or a consulate.",
    )
    requires_notarisation = fields.Boolean(
        string="Notarised (الكاتب العدل)",
        help="Law 33 of 1998. A simple company's formation contract, and most "
        "instruments intended for use abroad.",
    )
    requires_legalisation = fields.Boolean(
        string="Consular Legalisation (التصديقات)",
        help="Iraq has no apostille. A foreign document must be certified by the "
        "issuing country's foreign ministry, then by the Iraqi mission there, then "
        "by دائرة التصديقات at the Iraqi Ministry of Foreign Affairs (Law 52 of 1970).",
    )
    requires_translation = fields.Boolean(
        string="Arabic Translation",
        help="Certified by the Iraqi Translators Association where the Registrar demands it.",
    )

    # ------------------------------------------------------------------
    # The edge that makes the prerequisite graph traversable
    # ------------------------------------------------------------------
    # NOTE: ``producer_procedure_type_id`` - the edge from a document back to the
    # procedure that obtains it - is added by ``legal_procedure``, which is where
    # the procedure model lives. Core must not depend on it: a customer may want
    # the body register and the document register without any workflow at all.
    grade_ids = fields.One2many("legal.licence.grade", "document_type_id", string="Grades")
    has_grades = fields.Boolean(compute="_compute_has_grades", store=True)

    is_per_subject = fields.Boolean(
        string="One Per Person",
        help="A passport or a residency belongs to a person, not to the company, "
        "so the checklist asks for one per subject on the file.",
    )
    company_register = fields.Boolean(
        string="Kept In The Company Register",
        default=True,
        help="When set, an instance of this type is filed once in the company's "
        "permanent register and reused by every file that needs it, instead of "
        "being uploaded again for the eleventh time.",
    )

    legal_basis = fields.Char(translate=True)
    legal_basis_url = fields.Char()
    last_verified_on = fields.Date()
    instruction = fields.Html(
        translate=True,
        help="What the counter actually wants: how many copies, stamped by whom, "
        "in what colour folder.",
    )
    sequence = fields.Integer(default=10)
    colour = fields.Integer()
    company_id = fields.Many2one("res.company", index=True)
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A document type code must be unique per company."
    )

    @api.depends("grade_ids")
    def _compute_has_grades(self):
        for document_type in self:
            document_type.has_grades = bool(document_type.grade_ids)

    @api.depends("name", "name_en")
    def _compute_display_name(self):
        for document_type in self:
            document_type.display_name = document_type.name or document_type.name_en or ""

    @api.constrains("validity_model", "validity_value")
    def _check_validity(self):
        for document_type in self:
            if document_type.validity_model == "expiry" and document_type.validity_value <= 0:
                raise ValidationError(
                    _(
                        "%(name)s expires on a date, so it needs a validity period greater than zero.",
                        name=document_type.display_name,
                    )
                )
