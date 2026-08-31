from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalJurisdiction(models.Model):
    """Federal Iraq, the Kurdistan Region, or a governorate.

    A first-class axis rather than a flag, because the *same* conceptual
    obligation is a different obligation in each: the corporate return is due 31
    May federally and 30 June in the Region; contract withholding is 3.3% or 7%
    federally and does not exist in the Region; a work permit costs IQD 250,000
    federally and IQD 110,000 in the Region; and the order is inverted - the
    federal route is residency then permit, while the Kurdish route makes the
    residency card a prerequisite of the permit. The Region also issues a
    fourteen-digit UEN in place of an Iraqi registry number.

    It sits on the body, the procedure type, the obligation and the document
    type from the first commit deliberately. Adding it afterwards is a data
    migration across every configuration table in the product.
    """

    _name = "legal.jurisdiction"
    _description = "Legal Jurisdiction"
    _parent_store = True
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(
        required=True,
        help="Short stable key used by content packs, e.g. IQ-FED, IQ-KRI.",
    )
    parent_id = fields.Many2one(
        "legal.jurisdiction", string="Part Of", ondelete="restrict", index=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        "legal.jurisdiction", "parent_id", string="Sub-jurisdictions"
    )
    company_ids = fields.Many2many(
        "res.company",
        string="Companies",
        help="Leave empty to make this jurisdiction available to every company.",
    )
    sequence = fields.Integer(default=10)
    note = fields.Html(translate=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)", "A jurisdiction code must be unique."
    )

    @api.constrains("parent_id")
    def _check_jurisdiction_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("A jurisdiction cannot be part of itself."))
