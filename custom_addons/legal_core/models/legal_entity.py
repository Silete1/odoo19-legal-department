from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalEntityForm(models.Model):
    """The legal form of a person: شركة محدودة، مساهمة، تضامنية، بسيطة، مشروع فردي،
    فرع شركة أجنبية.

    Carries the minimum capital from Article 28 of Companies Law 21 of 1997,
    because the figure is a fact about the form rather than about any one
    company, and because the Registrar checks it at the capital-increase
    counter.
    """

    _name = "legal.entity.form"
    _description = "Legal Entity Form"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction", string="Jurisdiction", ondelete="restrict", index=True
    )
    minimum_capital = fields.Monetary(
        currency_field="currency_id",
        help="Article 28 of Companies Law 21 of 1997: IQD 2,000,000 for a joint "
        "stock company, IQD 1,000,000 for a limited company, IQD 500,000 for a "
        "simple, partnership or individual enterprise.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False),
    )
    requires_notarised_contract = fields.Boolean(
        help="A شركة بسيطة must have its formation contract notarised at الكاتب العدل.",
    )
    legal_basis = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)", "An entity form code must be unique."
    )


class LegalEntity(models.Model):
    """The legal person the department acts for - الشخصية المعنوية.

    Deliberately not ``res.company``. A group holds several registered persons -
    the operating LLC, the branch of the foreign parent, an individual
    enterprise used for one licence - and a branch of a foreign company is a
    legal person that is emphatically not a company in the accounting sense. It
    is also not ``res.partner``, because a partner is somebody you trade with
    and this is somebody you *are*.

    Where a deployment genuinely has one company and one legal person, the
    company's own entity is created automatically and the distinction costs the
    user nothing: they never see the model.
    """

    _name = "legal.entity"
    _description = "Legal Entity"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"
    _rec_names_search = ["name", "name_en", "identifier_index"]

    # Two stored names rather than one translated field, because both print on
    # the same page: the Registrar's Arabic name and the English name the
    # foreign parent uses appear together on a bilingual letterhead, and
    # translate=True can only ever render the reader's language.
    name = fields.Char(string="Name (Arabic)", required=True, index="trigram", tracking=True)
    name_en = fields.Char(string="Name (English)", index="trigram", tracking=True)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Related Contact",
        help="Optional link to the contact record, where one exists.",
    )
    entity_form_id = fields.Many2one(
        "legal.entity.form", string="Legal Form", ondelete="restrict", index=True
    )
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction",
        string="Jurisdiction",
        required=True,
        ondelete="restrict",
        index=True,
    )
    is_foreign_branch = fields.Boolean(
        string="Branch of a Foreign Company",
        help="Regulation 2 of 2017 applies: audited accounts and an activity "
        "report are due to the Registrar within eight months of the year end, "
        "and a change of branch manager must be notified within sixty working days.",
    )
    parent_company_name = fields.Char(
        string="Foreign Parent", help="For a branch, the name of the parent abroad."
    )
    incorporation_date = fields.Date()
    financial_year_end = fields.Date(
        string="Financial Year End",
        help="Drives every deadline expressed as an offset from the year end - "
        "the corporate return, the foreign branch's eight-month accounts filing, "
        "and the general assembly clock.",
    )
    capital = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False),
    )
    activity_description = fields.Text(
        string="Registered Activity", translate=True, help="النشاط المسجل"
    )
    address = fields.Text(translate=True)

    identifier_ids = fields.One2many(
        "legal.entity.identifier", "entity_id", string="Identifiers"
    )
    identifier_index = fields.Char(
        compute="_compute_identifier_index",
        store=True,
        index="trigram",
        help="Every identifier concatenated, so the entity is findable by any "
        "number a clerk happens to be holding.",
    )
    document_ids = fields.One2many("legal.document", "entity_id", string="Documents")
    document_count = fields.Integer(compute="_compute_document_count")

    signatory_ids = fields.One2many(
        "legal.signatory", "entity_id", string="Authorised Signatories"
    )
    note = fields.Html(translate=True)
    active = fields.Boolean(default=True)

    @api.depends("identifier_ids.value")
    def _compute_identifier_index(self):
        for entity in self:
            entity.identifier_index = " ".join(
                identifier.value for identifier in entity.identifier_ids if identifier.value
            )

    def _compute_document_count(self):
        counts = dict(
            self.env["legal.document"]._read_group(
                [("entity_id", "in", self.ids)], ["entity_id"], ["__count"]
            )
        )
        for entity in self:
            entity.document_count = counts.get(entity, 0)

    @api.depends("name", "name_en")
    def _compute_display_name(self):
        for entity in self:
            entity.display_name = entity.name or entity.name_en or ""

    def action_open_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Documents"),
            "res_model": "legal.document",
            "view_mode": "list,form",
            "domain": [("entity_id", "=", self.id)],
            "context": {"default_entity_id": self.id},
        }


class LegalEntityIdentifierKind(models.Model):
    """What kind of number this is: a registration number, a tax file number, a
    social security project number, a Chamber membership number, a UEN."""

    _name = "legal.entity.identifier.kind"
    _description = "Entity Identifier Kind"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)", "An identifier kind code must be unique."
    )


class LegalEntityIdentifier(models.Model):
    """Our file number *at* a body - one row per (entity, body, kind).

    This is the model the three architectures disagreed about and the one a
    clerk is asked for first at every window. The Registrar issues a
    registration number, the General Commission for Taxes a tax file number
    (and a separate number per assessment section), the Social Security
    Department a project number, the Chamber a membership number, the Ministry
    of Planning a classification registration, and the Kurdistan registry a
    fourteen-digit UEN. Flattening those into one ``company_registration_number``
    field loses the only piece of data that lets a clerk answer the first
    question they are asked.
    """

    _name = "legal.entity.identifier"
    _description = "Entity Identifier"
    _order = "body_id, kind_id"
    _rec_names_search = ["value"]

    entity_id = fields.Many2one(
        "legal.entity", required=True, ondelete="cascade", index=True
    )
    body_id = fields.Many2one(
        "legal.gov.body", string="Issued By", required=True, ondelete="restrict", index=True
    )
    kind_id = fields.Many2one(
        "legal.entity.identifier.kind", string="Kind", required=True, ondelete="restrict"
    )
    value = fields.Char(required=True, index="trigram", help="The number itself.")
    section = fields.Char(
        translate=True,
        help="The section inside the body that holds this file, e.g. قسم الشركات، "
        "قسم كبار مكلفي الدخل. Clerks are routed by section, not by body.",
    )
    issue_date = fields.Date()
    document_id = fields.Many2one(
        "legal.document",
        string="Evidenced By",
        help="The card or certificate that carries this number.",
    )
    note = fields.Char(translate=True)
    active = fields.Boolean(default=True)

    _entity_body_kind_uniq = models.Constraint(
        "UNIQUE(entity_id, body_id, kind_id)",
        "This entity already has an identifier of that kind at that body.",
    )

    @api.depends("kind_id", "value", "body_id")
    def _compute_display_name(self):
        for identifier in self:
            identifier.display_name = f"{identifier.kind_id.name or ''} {identifier.value or ''}".strip()

    @api.constrains("entity_id", "body_id")
    def _check_same_jurisdiction(self):
        """A Kurdish registry cannot issue a federal company's number, and the
        mistake is easy to make when both packs are installed."""
        for identifier in self:
            entity_jurisdiction = identifier.entity_id.jurisdiction_id
            body_jurisdiction = identifier.body_id.jurisdiction_id
            if not entity_jurisdiction or not body_jurisdiction:
                continue
            related = (
                body_jurisdiction == entity_jurisdiction
                or body_jurisdiction in entity_jurisdiction.child_ids
                or entity_jurisdiction in body_jurisdiction.child_ids
            )
            if not related:
                raise ValidationError(
                    _(
                        "%(body)s is in %(body_jurisdiction)s but %(entity)s is registered "
                        "in %(entity_jurisdiction)s. Check the jurisdiction before recording "
                        "this identifier.",
                        body=identifier.body_id.display_name,
                        body_jurisdiction=body_jurisdiction.name,
                        entity=identifier.entity_id.display_name,
                        entity_jurisdiction=entity_jurisdiction.name,
                    )
                )
