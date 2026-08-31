from odoo import _, api, fields, models


class LegalRequestCategory(models.Model):
    """What kind of question came in - and what it usually turns into.

    Configuration, not a hard-coded ``Selection``, for the same reason the
    correspondence *kind* is: a department that starts receiving a new class of
    request - a data-protection review, say - adds a row rather than waiting for
    a developer. The category also carries a *default target kind*, which is the
    triage desk's first guess at what the request will become: a consultation
    becomes a legal opinion, a contract review becomes a vetted contract, a
    dispute becomes a litigation file. That guess pre-selects the convert hook;
    it never forces it.
    """

    _name = "legal.request.category"
    _description = "Legal Request Category"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        translate=True,
        index="trigram",
        help="What the department calls this class of request, e.g. Legal Consultation.",
    )
    code = fields.Char(
        help="A short, stable handle used in imports and reports, e.g. CONSULT.",
    )
    sequence = fields.Integer(default=10)
    default_target_kind = fields.Selection(
        [
            ("opinion", "Legal Opinion"),
            ("consultation", "Legal Consultation"),
            ("contract", "Contract Review"),
            ("dispute", "Litigation File"),
            ("claim", "Claim"),
            ("poa", "Power Of Attorney"),
            ("letter", "Official Letter"),
            ("compliance", "Compliance Matter"),
            ("property", "Property Matter"),
            ("other", "Other"),
        ],
        string="Usually Becomes",
        default="other",
        help="The triage desk's first guess at what a request of this category "
        "turns into. It pre-selects the conversion; it does not force it.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        default=lambda self: self.env.company,
        index=True,
        help="Leave empty to share the category across companies.",
    )

    _code_company_uniq = models.UniqueIndex(
        "(code, company_id) WHERE code IS NOT NULL",
        "That category code is already in use.",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for category in self:
            category.display_name = (
                "%s (%s)" % (category.name, category.code)
                if category.code
                else (category.name or "")
            )
