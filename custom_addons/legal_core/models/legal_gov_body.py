from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalGovBodyType(models.Model):
    """What kind of counter this is.

    A record rather than a Selection, for two reasons. It is the first thing a
    customer outside Iraq would change, and the real list is much longer than
    "ministry": the bodies that actually block an Iraqi filing include the Bar
    Association, Al-Rasheed Bank, the Translators Association, the notary, the
    newspapers that must publish a formation decision, and the electricity and
    water directorates whose paid bills Council of Ministers directive 16180 of
    1 April 2024 made mandatory attachments at the Registrar. A model that
    assumes a government hierarchy cannot hold any of them, and the requirement
    then degrades into a free-text note nobody can search or chase.
    """

    _name = "legal.gov.body.type"
    _description = "Government Body Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)", "A body type code must be unique."
    )


class LegalGovBodyContact(models.Model):
    """A named human at a counter.

    Iraqi follow-up is personal. Knowing that the section head is Abu Ahmed and
    that he answers his mobile before eleven is worth more than any escalation
    rule. A free-text note on the body cannot be searched, cannot be dialled
    from a desk panel, and cannot be handed over when the clerk who knew him
    leaves.
    """

    _name = "legal.gov.body.contact"
    _description = "Government Body Contact"
    _order = "sequence, name"

    body_id = fields.Many2one(
        "legal.gov.body", string="Body", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        "res.company", related="body_id.company_id", store=True, index=True
    )
    name = fields.Char(required=True, translate=True)
    role = fields.Char(translate=True, help="مدير القسم، معاون، موظف الاستعلامات")
    section = fields.Char(translate=True, help="The section or window inside the body.")
    phone = fields.Char()
    mobile = fields.Char()
    email = fields.Char()
    note = fields.Text(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class LegalGovBody(models.Model):
    """An external body the department deals with - الجهة.

    Everything that makes one body differ from another lives here as
    configuration, so that adding the General Commission for Taxes is data
    entry: its addressee block, its working calendar, its opening hours, its
    channel, its named contacts, and the officers who may see its files.

    Two decisions are worth stating because they are easy to get wrong.

    Officers are a ``Many2many`` traversed by a record rule, **not** a
    ``res.groups`` per body. A group per ministry would mean that installing a
    content pack creates security objects, which is precisely the "forked, not
    configured" failure this product exists to avoid.

    The calendar is a real ``resource.calendar``. Iraqi offices work Sunday to
    Thursday and close for Eid and the national holidays, so a target counted in
    calendar days cries wolf every weekend. Counting in the body's own working
    days is the difference between a chase list people act on and one they learn
    to ignore.
    """

    _name = "legal.gov.body"
    _description = "Government Body"
    _inherit = ["mail.thread"]
    _parent_store = True
    _order = "sequence, name"
    _rec_names_search = ["name", "short_name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram", tracking=True)
    short_name = fields.Char(
        translate=True, help="What a clerk actually calls it: الضرائب، الإقامة، الغرفة."
    )
    code = fields.Char(
        required=True,
        help="Stable key used by content packs, e.g. GCT, MOT-REG, PSSO, CHAMBER-BGD.",
    )
    body_type_id = fields.Many2one(
        "legal.gov.body.type",
        string="Type",
        required=True,
        ondelete="restrict",
        index=True,
    )
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction",
        string="Jurisdiction",
        required=True,
        ondelete="restrict",
        index=True,
    )
    parent_id = fields.Many2one(
        "legal.gov.body", string="Part Of", ondelete="restrict", index=True
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("legal.gov.body", "parent_id", string="Sections")

    # ------------------------------------------------------------------
    # What a letter to this body must say
    # ------------------------------------------------------------------
    letterhead_recipient = fields.Text(
        string="Addressee Block",
        translate=True,
        help="Printed verbatim as الجهة الموجه إليها, for example:\n"
        "وزارة النفط / دائرة الدراسات والتخطيط والمتابعة / قسم سمات الدخول",
    )
    salutation = fields.Char(translate=True, default="السيد المدير العام المحترم")

    # ------------------------------------------------------------------
    # How to reach it
    # ------------------------------------------------------------------
    address = fields.Text(translate=True)
    open_hours = fields.Char(
        translate=True, help="For example: 08:30 - 14:15، عطلة الجمعة والسبت"
    )
    phone = fields.Char()
    email = fields.Char()
    portal_url = fields.Char(
        help="tasjeel.mot.gov.iq, tax.mof.gov.iq, or the ur.gov.iq service page."
    )
    channel = fields.Selection(
        [("paper", "Paper"), ("online", "Online"), ("hybrid", "Both")],
        default="paper",
        required=True,
        help="Roughly half of Iraqi services are still paper. A hybrid body needs "
        "both a letter and a portal reference, and the portal reference is often "
        "the only handle that exists on an online filing.",
    )
    contact_ids = fields.One2many(
        "legal.gov.body.contact", "body_id", string="Contacts"
    )

    resource_calendar_id = fields.Many2one(
        "resource.calendar",
        string="Working Calendar",
        help="Sunday to Thursday, with Eid and national closures entered as leaves, "
        "so that a target counted in working days matches what the counter does.",
    )
    officer_ids = fields.Many2many(
        "res.users",
        string="Follow-up Officers",
        help="Who deals with this body. Read by a record rule - never a security "
        "group per body.",
    )
    default_user_id = fields.Many2one("res.users", string="Default Responsible")

    colour = fields.Integer(string="Colour")
    sequence = fields.Integer(default=10)
    note = fields.Html(
        translate=True,
        help="Which counter, which floor, how many photocopies, who to ask for.",
    )

    # ------------------------------------------------------------------
    # Provenance, so a shipped figure can be challenged
    # ------------------------------------------------------------------
    legal_basis = fields.Char(
        translate=True, help="The law or regulation that constitutes this body."
    )
    legal_basis_url = fields.Char()
    last_verified_on = fields.Date(
        help="When a human last confirmed that these details and the procedures "
        "hanging off them are still current. Iraqi practice changes by circular, "
        "and a shipped figure nobody has re-read is a liability at the counter.",
    )
    verification_status = fields.Selection(
        [
            ("verified", "Verified"),
            ("stale", "Needs Re-check"),
            ("not_researched", "Not Researched"),
        ],
        default="not_researched",
        required=True,
        help="A body shipped with no procedures and this flag set is an honest gap "
        "the customer can fill. Silence would read as 'the module does not cover "
        "this', which is false - it covers it the moment somebody configures it.",
    )

    company_id = fields.Many2one("res.company", string="Company", index=True)
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A body code must be unique per company."
    )

    @api.constrains("parent_id")
    def _check_body_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("A government body cannot be a section of itself."))

    @api.depends("name", "short_name")
    def _compute_display_name(self):
        for body in self:
            body.display_name = body.short_name or body.name

    # ------------------------------------------------------------------
    # Working-time helpers, used by every clock in the product
    # ------------------------------------------------------------------
    def _plan_days(self, days, from_datetime):
        """Add ``days`` of *this body's* working time to a datetime.

        Falls back to the company calendar, and then to plain calendar days, so
        a body configured in a hurry still produces a usable deadline rather
        than an error. Everything that says "they have not answered in six
        working days" goes through here.
        """
        self.ensure_one()
        calendar = self.resource_calendar_id or self.env.company.resource_calendar_id
        if not calendar:
            return fields.Datetime.add(from_datetime, days=days)
        return calendar.plan_days(days, from_datetime, compute_leaves=True)
