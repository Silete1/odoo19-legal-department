from odoo import _, api, fields, models


class LegalLawsuitParty(models.Model):
    """A party to the الدعوى who is not us.

    A line model rather than a bare ``Many2many`` to ``res.partner`` because a
    case has more than opponents on it: the co-defendant we are jointly sued
    with, the third party pulled in (إدخال شخص ثالث), the guarantor. Each is a
    partner in a role, and the role is what a case list needs to show and what a
    letter needs to address. Reusing ``res.partner`` keeps the opponent's contact
    details in one place rather than retyped on every case they appear in.
    """

    _name = "legal.lawsuit.party"
    _description = "Lawsuit Party"
    _order = "sequence, id"

    lawsuit_id = fields.Many2one(
        "legal.lawsuit",
        string="Lawsuit",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Party",
        required=True,
        ondelete="restrict",
        index=True,
        help="The person or company, held in the partner register so their "
        "details are entered once and reused across every case they touch.",
    )
    role = fields.Selection(
        [
            ("opponent", "Opponent (خصم)"),
            ("co_party", "On Our Side (طرف معنا)"),
            ("third_party", "Third Party (شخص ثالث)"),
            ("guarantor", "Guarantor (كفيل / ضامن)"),
            ("other", "Other"),
        ],
        default="opponent",
        required=True,
        index=True,
        help="Where this party stands in the case. Opponents are what a case list "
        "shows; the rest matter when the file is worked.",
    )
    capacity = fields.Char(
        translate=True,
        help="How they appear - المدعى عليه الأول، بصفته الشخصية، بصفته مديراً "
        "مفوضاً. Printed on the letter, so it is recorded rather than assumed.",
    )
    note = fields.Char(translate=True)
    sequence = fields.Integer(default=10)

    @api.depends("partner_id", "role")
    def _compute_display_name(self):
        for party in self:
            party.display_name = party.partner_id.display_name or _("Party")
