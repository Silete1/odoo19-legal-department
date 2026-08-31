from odoo import _, api, fields, models

#: The remedies against an Iraqi ruling. ``objection`` (اعتراض) reopens a
#: judgment given in absentia; ``appeal`` (استئناف) takes it to the court above;
#: ``cassation`` (تمييز) asks the highest court to quash it; ``labor`` is the
#: labour courts' own combined route, which runs to a different clock. The
#: engine keys its day-counts on this together with the court degree.
REMEDY_SELECTION = [
    ("objection", "Objection (اعتراض على حكم غيابي)"),
    ("appeal", "Appeal (استئناف)"),
    ("cassation", "Cassation (تمييز)"),
    ("labor", "Labour Remedy (طعن أمام محاكم العمل)"),
]

#: A challenge to a full judgment (حكم) and a challenge to an interlocutory
#: decision (قرار) run to different clocks - cassation is thirty days against a
#: judgment and seven against a decision - so the rule is keyed on this too.
RULING_TYPE_SELECTION = [
    ("judgment", "Judgment (حكم)"),
    ("decision", "Decision (قرار)"),
]


class LegalAppealRule(models.Model):
    """How many days there are to challenge a ruling - as data, not law in code.

    The periods are statutory: the Iraqi Civil Procedure Code and the labour law
    fix them, and getting one wrong loses a client's right of appeal. That is
    precisely why they are a **configurable table with a verification status**
    rather than constants buried in a compute. A statute a customer's counsel can
    read, challenge and correct from an ordinary form is a statute the department
    can trust; a number a developer hard-coded is one nobody can audit.

    A rule is matched on three keys - the remedy, whether the ruling is a full
    judgment or an interlocutory decision, and (optionally) the degree of the
    court that issued it - so a single labour clock and a single cassation clock
    can each be stated once and still answer for every court that runs to them.
    """

    _name = "legal.appeal.rule"
    _description = "Appeal Window Rule"
    _order = "sequence, remedy"

    name = fields.Char(
        required=True,
        translate=True,
        help="What the rule is called: مدة الاستئناف، مدة التمييز على القرارات.",
    )
    remedy = fields.Selection(
        REMEDY_SELECTION,
        required=True,
        index=True,
        help="The challenge this period governs.",
    )
    ruling_type = fields.Selection(
        RULING_TYPE_SELECTION,
        string="Against",
        default="judgment",
        required=True,
        index=True,
        help="Whether the period is the one for challenging a full judgment or an "
        "interlocutory decision. Cassation, above all, differs between the two.",
    )
    court_degree = fields.Selection(
        selection="_selection_court_degree",
        string="Court Degree",
        index=True,
        help="Restrict the rule to rulings from courts of this degree. Left empty, "
        "the rule answers for any court whose ruling invokes the remedy - which is "
        "how one cassation period can cover the whole system.",
    )
    days = fields.Integer(
        string="Days To Challenge",
        required=True,
        help="Counted from the date of official notification (التبليغ), in "
        "calendar days - these statutory periods run over weekends and holidays.",
    )
    non_extendable = fields.Boolean(
        string="Non-extendable",
        default=True,
        help="Almost always true: a statutory appeal period does not stretch "
        "because the office was shut. The flag is carried onto every deadline the "
        "rule produces so nobody treats it as a soft target.",
    )
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction",
        string="Jurisdiction",
        ondelete="restrict",
        index=True,
        help="Restrict the rule to Federal Iraq or the Region, whose periods can "
        "differ. Left empty, it applies to both.",
    )
    legal_basis = fields.Char(
        translate=True,
        help="The article that fixes the period - e.g. المادة ١٧١ من قانون "
        "المرافعات المدنية - so a shipped number can be checked against the text.",
    )
    verification_status = fields.Selection(
        [
            ("verified", "Verified"),
            ("stale", "Needs Re-check"),
            ("not_researched", "Not Researched"),
        ],
        default="not_researched",
        required=True,
        help="Iraqi periods change by amendment. A rule nobody has re-read is a "
        "liability at the court, and saying so is more honest than a silent figure.",
    )
    sequence = fields.Integer(default=10)
    note = fields.Html(translate=True)
    company_id = fields.Many2one("res.company", string="Company", index=True)
    active = fields.Boolean(default=True)

    @api.model
    def _selection_court_degree(self):
        return self.env["legal.court"]._fields["degree"].selection

    @api.model
    def _match(self, remedy, ruling_type="judgment", court_degree=False,
               jurisdiction=False, company=False):
        """The most specific rule for a ruling, or an empty recordset.

        Specificity is deliberate: a rule that names the court degree beats one
        that does not, and a company-specific override beats the shared default,
        so a labour clock stated once for ``court_degree = labor`` wins over a
        generic appeal clock without either having to know about the other.
        """
        if not remedy:
            return self.browse()
        domain = [
            ("remedy", "=", remedy),
            ("ruling_type", "=", ruling_type or "judgment"),
            ("company_id", "in", (False, company.id if company else False)),
        ]
        candidates = self.search(domain)

        def score(rule):
            return (
                1 if rule.court_degree and rule.court_degree == court_degree else 0,
                1 if rule.company_id else 0,
                1 if (rule.jurisdiction_id and rule.jurisdiction_id == jurisdiction) else 0,
            )

        eligible = candidates.filtered(
            lambda rule: (not rule.court_degree or rule.court_degree == court_degree)
            and (not rule.jurisdiction_id or rule.jurisdiction_id == jurisdiction)
        )
        return eligible.sorted(key=score, reverse=True)[:1]
