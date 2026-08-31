from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

#: The degrees of the Iraqi court system, in the order a case climbs them. Kept
#: as a Selection rather than a table because - unlike a government body, whose
#: type a customer outside Iraq will want to redefine - the ladder of degrees is
#: what the appeal-window rules are keyed on, and a free list would let a court
#: be filed under a degree no rule answers for.
COURT_DEGREE_SELECTION = [
    ("first_instance", "First Instance (بداءة)"),
    ("appeal", "Appeal (استئناف)"),
    ("cassation", "Cassation (تمييز)"),
    ("labor", "Labour (عمل)"),
    ("misdemeanor_felony", "Misdemeanour / Felony (جنح وجنايات)"),
    ("administrative", "Administrative Judiciary (قضاء إداري)"),
    ("personal_status", "Personal Status (أحوال شخصية)"),
]


class LegalCourt(models.Model):
    """المحكمة - a court the department litigates in.

    A configuration model, shared across companies the way the government-body
    register is, because two companies in the same group answer to the same
    محكمة البداءة and neither should have to re-enter it. It carries a degree so
    the appeal-window engine knows which clock a judgment from it starts, and a
    ``parent_court_id`` so a first-instance judgment knows which court of appeal
    sits above it.

    The optional ``gov_body_id`` is the bridge to the rest of the product: point
    a court at a ``legal.gov.body`` of type COURT and its working calendar, its
    named contacts and the officers who may see its files all come for free, and
    a letter to the court is written through the register like any other.
    """

    _name = "legal.court"
    _description = "Court"
    _order = "degree, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(
        required=True,
        translate=True,
        index="trigram",
        help="What the court is called: محكمة بداءة الكرخ، محكمة استئناف بغداد/الرصافة.",
    )
    code = fields.Char(
        help="A short stable key, so a content pack or an import can find the "
        "court without matching its Arabic name letter for letter.",
    )
    degree = fields.Selection(
        COURT_DEGREE_SELECTION,
        required=True,
        index=True,
        help="Which rung of the court ladder this is. The appeal-window rules are "
        "keyed on it, so it decides how long there is to challenge a judgment.",
    )
    governorate_id = fields.Many2one(
        "legal.jurisdiction",
        string="Governorate",
        ondelete="restrict",
        index=True,
        help="Where the court sits. A governorate under Federal Iraq or the "
        "Kurdistan Region, so a case list can be grouped by where it is being heard.",
    )
    parent_court_id = fields.Many2one(
        "legal.court",
        string="Court Of Appeal Above",
        ondelete="restrict",
        index=True,
        help="The court that hears a challenge to this one's judgments - the "
        "court of appeal above a first-instance court. Used to suggest where an "
        "appeal is lodged.",
    )
    gov_body_id = fields.Many2one(
        "legal.gov.body",
        string="Government Body",
        ondelete="set null",
        index=True,
        help="The court as a body in the register, so its working calendar, its "
        "contacts and its officers drive the same clocks and letters as every "
        "other counter. Optional - a court can be recorded without one.",
    )
    court_count = fields.Integer(
        string="Sub-courts", compute="_compute_court_count"
    )
    child_court_ids = fields.One2many(
        "legal.court", "parent_court_id", string="Courts Below"
    )
    lawsuit_count = fields.Integer(compute="_compute_lawsuit_count")
    address = fields.Char(translate=True)
    note = fields.Html(translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="Left empty, the court is shared by every company - which is almost "
        "always right, since a court is not owned by whoever litigates in it.",
    )
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)",
        "A court code must be unique per company.",
    )

    @api.constrains("parent_court_id")
    def _check_court_recursion(self):
        if self._has_cycle("parent_court_id"):
            raise ValidationError(
                _("A court cannot sit in appeal over itself.")
            )

    def _compute_court_count(self):
        for court in self:
            court.court_count = len(court.child_court_ids)

    def _compute_lawsuit_count(self):
        counts = dict(
            self.env["legal.lawsuit"]._read_group(
                [("court_id", "in", self.ids)], ["court_id"], ["__count"]
            )
        )
        for court in self:
            court.lawsuit_count = counts.get(court, 0)

    def action_open_lawsuits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Lawsuits"),
            "res_model": "legal.lawsuit",
            "view_mode": "list,form",
            "domain": [("court_id", "=", self.id)],
            "context": {"default_court_id": self.id},
        }
