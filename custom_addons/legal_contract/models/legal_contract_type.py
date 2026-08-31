from odoo import _, api, fields, models


class LegalContractType(models.Model):
    """What a contract *is* - نوع العقد.

    The type carries the two facts that are true of every instance of it rather
    than of any one contract: which internal group reviews it by default, and the
    stable code a content pack keys on. A lease, a supply agreement and a power
    purchase contract route to different reviewers and expire on different
    ladders, so the reviewer is a property of the type and not a field a clerk
    re-answers on every file.
    """

    _name = "legal.contract.type"
    _description = "Contract Type"
    _order = "sequence, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(required=True, help="Stable key used by content packs and demo data.")
    default_review_group = fields.Selection(
        [
            ("officer", "Legal Officer"),
            ("approver", "Legal Approver"),
            ("manager", "Legal Manager"),
        ],
        string="Reviewed By",
        default="officer",
        required=True,
        help="Which rung of the ladder reviews a contract of this type by default. "
        "It is a hint the form fills in, not a lock: the internal-approval gate is "
        "always the approver, whatever this says.",
    )
    default_notice_days = fields.Integer(
        string="Default Notice (days)",
        default=30,
        help="How far ahead of expiry a contract of this type starts appearing on "
        "the renewal board, copied onto a new contract as its default.",
    )
    default_auto_renew = fields.Boolean(
        string="Renews Automatically By Default",
        help="Whether contracts of this type usually roll over unless notice is "
        "served. Copied onto a new contract, where it can be overridden.",
    )
    contract_count = fields.Integer(compute="_compute_contract_count")
    note = fields.Html(translate=True)
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", index=True)
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A contract type code must be unique per company."
    )

    def _compute_contract_count(self):
        counts = dict(
            self.env["legal.contract"]._read_group(
                [("type_id", "in", self.ids)], ["type_id"], ["__count"]
            )
        )
        for contract_type in self:
            contract_type.contract_count = counts.get(contract_type, 0)

    def action_open_contracts(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Contracts"),
            "res_model": "legal.contract",
            "view_mode": "list,form",
            "domain": [("type_id", "=", self.id)],
            "context": {"default_type_id": self.id},
        }


class LegalContractDepartment(models.Model):
    """The internal department that owns a contract - القسم المسؤول.

    A small typed register rather than a Many2one to ``hr.department``, on
    purpose: the HR application is not part of the community legal suite and must
    not be dragged in to answer "whose contract is this". A department that later
    installs HR loses nothing - this stays the legal department's own list of
    owning units, which is frequently coarser than the HR org chart anyway.
    """

    _name = "legal.contract.department"
    _description = "Responsible Department"
    _order = "sequence, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(help="Stable key used by content packs and demo data.")
    manager_id = fields.Many2one("res.users", string="Head Of Department")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", index=True)
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A department code must be unique per company."
    )
