from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalRegister(models.Model):
    """A register book - سجل.

    One record per bound book the department actually keeps. Most departments
    keep two, صادر and وارد, and that is what this module ships; a department
    that answers to three ministries keeps a book per ministry, and one holding
    classified files keeps a separate سري book with a different key holder. All
    three shapes are the same model with different rows, which is the whole
    point: the book is configuration, never a Selection.

    Two fields here carry more weight than they look.

    ``write_group_id`` is the key to the drawer. In an Iraqi department the
    register is not a shared spreadsheet - one named person, the مسؤول السجل,
    allocates numbers, and everybody else asks him. ``ir.model.access`` cannot
    express "may create the record but may not allocate its number", so this is
    checked in Python at the moment a number is taken.

    ``retention_years`` is not decoration. The Council of Ministers'
    document-retention instructions require صادر and وارد registers to be kept
    for ten years, and a department that archives them in three has destroyed
    evidence it was obliged to hold. Recording the obligation on the book is how
    a purge routine, or an auditor, can be told about it.
    """

    _name = "legal.register"
    _description = "Correspondence Register"
    _order = "sequence, code"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(
        required=True,
        help="Stable key used by content packs and by wizards, e.g. OUT, IN, SECRET-OUT.",
    )
    direction = fields.Selection(
        [
            ("out", "صادر - Outgoing"),
            ("in", "وارد - Incoming"),
            ("internal", "داخلي - Internal"),
        ],
        required=True,
        default="out",
        help="Which of the two books this is. A department keeping one combined "
        "book still keeps two directions in it, so this is on the book and "
        "repeated on the entry.",
    )
    secrecy = fields.Selection(
        [("ordinary", "عادي - Ordinary"), ("secret", "سري - Confidential")],
        required=True,
        default="ordinary",
        help="A سري book is kept physically apart and its entries are visible only "
        "to the legal manager and the officers of the body concerned.",
    )
    body_id = fields.Many2one(
        "legal.gov.body",
        string="Body",
        ondelete="restrict",
        index=True,
        help="Optional. A department that answers to one ministry often keeps a "
        "book per ministry; a general book leaves this empty.",
    )

    # ------------------------------------------------------------------
    # Numbering
    # ------------------------------------------------------------------
    prefix = fields.Char(
        help="What the department already writes in front of the counter, e.g. "
        "ق or ص. Used only when a book has no numbers in it yet - after that, "
        "the next number is deduced from the last one, so changing this does "
        "not silently renumber a book in progress.",
    )
    sequence_id = fields.Many2one(
        "ir.sequence",
        string="Number Format",
        ondelete="restrict",
        copy=False,
        help="Provisioned automatically. It holds the padding and the prefix "
        "where an Odoo administrator expects to find them; the allocation "
        "itself goes through the editable chain on the entry, because a "
        "counter's number must remain typeable by the clerk.",
    )
    retention_years = fields.Integer(
        string="Retention (years)",
        default=10,
        help="How long the book must be kept. The Council of Ministers' "
        "document-retention instructions put صادر and وارد registers at ten "
        "years; a department that archives them sooner has destroyed evidence "
        "it was obliged to hold.",
    )
    write_group_id = fields.Many2one(
        "res.groups",
        string="Registrar Group",
        help="Only a member of this group may allocate a number in this book. "
        "Leave empty to let anyone who can create an entry register it. "
        "Enforced in Python: ir.model.access can say who may create a row, but "
        "not who may take the next number out of the book.",
    )

    note = fields.Html(
        translate=True,
        help="Where the physical book is kept, who holds the key, how the "
        "numbers were written before the system arrived.",
    )
    sequence = fields.Integer(default=10)
    colour = fields.Integer(string="Colour")
    entry_count = fields.Integer(compute="_compute_entry_count")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A register code must be unique per company."
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for register in self:
            register.display_name = register.name or register.code or ""

    def _compute_entry_count(self):
        counts = dict(
            self.env["legal.correspondence"]._read_group(
                [("register_id", "in", self.ids)], ["register_id"], ["__count"]
            )
        )
        for register in self:
            register.entry_count = counts.get(register, 0)

    # ------------------------------------------------------------------
    # Provisioning
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        registers = super().create(vals_list)
        registers._provision_sequence()
        return registers

    def _provision_sequence(self):
        """Give every new book its ``ir.sequence``.

        ``use_date_range`` because the book restarts on 1 January, and ``no_gap``
        because a register with a hole in it is a register somebody has been
        editing - which is exactly the accusation the book exists to answer.
        """
        for register in self:
            if register.sequence_id:
                continue
            register.sequence_id = self.env["ir.sequence"].sudo().create(
                {
                    "name": _("Register: %s", register.name or register.code),
                    "code": "legal.register.%s" % (register.code or register.id),
                    "implementation": "no_gap",
                    "use_date_range": True,
                    "prefix": "%s/%%(range_year)s/" % register.prefix
                    if register.prefix
                    else "%(range_year)s/",
                    "padding": 4,
                    "company_id": register.company_id.id,
                }
            )

    def unlink(self):
        """A book with entries in it is archived, never deleted.

        Deleting it would orphan every number it allocated, and the department
        would lose the ability to say which book a quoted number came out of.
        """
        for register in self:
            if self.env["legal.correspondence"].search_count(
                [("register_id", "=", register.id)], limit=1
            ):
                raise UserError(
                    _(
                        "The register '%s' already has entries in it. Archive it "
                        "instead - the numbers it allocated are quoted in letters "
                        "that have already left the building.",
                        register.display_name,
                    )
                )
        return super().unlink()

    # ------------------------------------------------------------------
    # The key to the drawer
    # ------------------------------------------------------------------
    def _may_allocate(self, user=None):
        """May this user take the next number out of this book?"""
        self.ensure_one()
        user = user or self.env.user
        if self.env.su or user._is_superuser() or user._is_admin():
            return True
        if not self.write_group_id:
            return True
        return self.write_group_id.id in user.all_group_ids.ids

    def _check_may_allocate(self):
        for register in self:
            if not register._may_allocate():
                raise UserError(
                    _(
                        "Only a member of '%(group)s' may allocate a number in the "
                        "register '%(register)s'. In this department the book has "
                        "one keeper; ask them to register the entry, or have the "
                        "legal manager add you to the group.",
                        group=register.write_group_id.display_name,
                        register=register.display_name,
                    )
                )

    def action_open_entries(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "legal.correspondence",
            "view_mode": "list,form,calendar",
            "domain": [("register_id", "=", self.id)],
            "context": {"default_register_id": self.id},
        }
