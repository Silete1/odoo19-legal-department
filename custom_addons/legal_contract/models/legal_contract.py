import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

#: The contract lifecycle. English source; the Arabic ships in i18n/ar.po. The
#: order is the order an Iraqi contract actually walks: it arrives, legal reads
#: it, the two sides negotiate, it is approved internally, it goes to the other
#: side, it is made ready, it is signed, it becomes in force, and it eventually
#: expires, is terminated, or is closed out.
STATE_SELECTION = [
    ("received", "Received"),
    ("legal_review", "Legal Review"),
    ("negotiation", "Negotiation"),
    ("internal_approval", "Internal Approval"),
    ("counterparty_review", "With Counterparty"),
    ("to_sign", "Ready To Sign"),
    ("signed", "Signed"),
    ("active", "In Force"),
    ("expired", "Expired"),
    ("terminated", "Terminated"),
    ("closed", "Closed"),
]

#: The states in which a contract is finished and no longer walks forward.
CLOSED_STATES = ("expired", "terminated", "closed")


class LegalContractParty(models.Model):
    """One party to the contract other than us.

    A contract is not a single ``counterparty`` field, because a supply agreement
    routinely names a second party, a guarantor standing behind them and a
    witness to the signature, and a department later asked "who guaranteed this"
    cannot answer it from a free-text box. Each party is a row with a role, so
    the question is a filter rather than a reading of the prose.
    """

    _name = "legal.contract.party"
    _description = "Contract Party"
    _order = "sequence, id"

    contract_id = fields.Many2one(
        "legal.contract", required=True, ondelete="cascade", index=True
    )
    partner_id = fields.Many2one(
        "res.partner", string="Party", required=True, ondelete="restrict", index=True
    )
    role = fields.Selection(
        [
            ("counterparty", "Counterparty"),
            ("guarantor", "Guarantor"),
            ("beneficiary", "Beneficiary"),
            ("witness", "Witness"),
        ],
        required=True,
        default="counterparty",
        index=True,
    )
    reference = fields.Char(
        string="Their Reference",
        help="Their identifier for the contract, if they gave it one.",
    )
    signatory_name = fields.Char(
        string="Signed For Them By",
        help="The named individual who signs for this party.",
    )
    note = fields.Char(string="Remark")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one(related="contract_id.company_id", store=True, index=True)


class LegalContract(models.Model):
    """A contract or agreement.

    The single transactional model of the module. It inherits the expiry mixin,
    so its renewal is chased on the same board as every licence and identity the
    company holds, and it carries a lifecycle ``state`` rather than a free
    "status" so that the gates - who may approve, who may terminate - are
    enforced in Python where a client cannot route around them.
    """

    _name = "legal.contract"
    _description = "Contract"
    _inherit = ["mail.thread", "mail.activity.mixin", "legal.expiry.mixin"]
    _order = "signature_date desc, id desc"
    _rec_names_search = ["name", "title"]

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        string="Reference",
        default="New",
        readonly=True,
        copy=False,
        index="trigram",
        tracking=True,
        help="Allocated CON/YYYY/#### the moment the contract is created.",
    )
    title = fields.Char(
        required=True,
        translate=True,
        tracking=True,
        help="What the contract is, in a line: 'Head office lease, Karrada'.",
    )
    type_id = fields.Many2one(
        "legal.contract.type",
        string="Type",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    entity_id = fields.Many2one(
        "legal.entity",
        string="Our Party",
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.company.legal_entity_id,
        help="The legal person of ours that is party to the contract.",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    # ------------------------------------------------------------------
    # Parties
    # ------------------------------------------------------------------
    party_ids = fields.One2many("legal.contract.party", "contract_id", string="Parties")
    counterparty_id = fields.Many2one(
        "res.partner",
        string="Counterparty",
        compute="_compute_counterparty",
        store=True,
        index=True,
        help="The primary counterparty, lifted from the parties table so a list "
        "and a board can show and group on it without opening the file.",
    )
    party_count = fields.Integer(compute="_compute_party_count")

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------
    responsible_department_id = fields.Many2one(
        "legal.contract.department",
        string="Responsible Department",
        index=True,
        tracking=True,
    )
    internal_owner_id = fields.Many2one(
        "res.users",
        string="Internal Owner",
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
        help="The business owner the contract belongs to internally.",
    )
    legal_officer_id = fields.Many2one(
        "res.users",
        string="Legal Officer",
        index=True,
        tracking=True,
        help="The lawyer handling the review and negotiation.",
    )

    # ------------------------------------------------------------------
    # Value
    # ------------------------------------------------------------------
    value = fields.Monetary(
        string="Contract Value",
        currency_field="currency_id",
        tracking=True,
        help="The value as originally agreed. Amendments do not overwrite it; the "
        "current value is computed as this plus the applied amendments.",
    )
    current_value = fields.Monetary(
        string="Current Value",
        currency_field="currency_id",
        compute="_compute_current_value",
        store=True,
        help="The original value plus the value change of every applied amendment.",
    )

    # ------------------------------------------------------------------
    # Dates. expiry_date / notice_days / renewal_lead_days come from the mixin.
    # ------------------------------------------------------------------
    effective_date = fields.Date(
        string="Effective Date",
        tracking=True,
        help="The date the contract is agreed to take effect from.",
    )
    signature_date = fields.Date(string="Signature Date", tracking=True, copy=False)
    commencement_date = fields.Date(
        string="Commencement Date",
        tracking=True,
        help="The date performance actually begins, which is not always the "
        "signature date.",
    )
    auto_renew = fields.Boolean(
        string="Auto-renews",
        tracking=True,
        help="Rolls over for a further term unless notice is served within the "
        "notice period below.",
    )
    notice_period_days = fields.Integer(
        string="Renewal Notice (days)",
        default=30,
        help="How long before expiry notice must be served to stop an automatic "
        "renewal, or to end the contract at term.",
    )
    governing_law = fields.Char(
        string="Governing Law",
        help="The law the contract is governed by, e.g. 'Iraqi Civil Code'.",
    )

    # ------------------------------------------------------------------
    # Risk & confidentiality
    # ------------------------------------------------------------------
    confidential = fields.Boolean(
        tracking=True,
        help="Restricts the contract to its owner, its legal officer and the legal "
        "manager. Used for anything commercially or personally sensitive.",
    )
    risk = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        default="low",
        required=True,
        index=True,
        tracking=True,
        string="Risk",
    )

    # ------------------------------------------------------------------
    # Signature
    # ------------------------------------------------------------------
    signature_status = fields.Selection(
        [
            ("unsigned", "Unsigned"),
            ("ours_signed", "Signed By Us"),
            ("fully_signed", "Fully Signed"),
        ],
        default="unsigned",
        required=True,
        index=True,
        tracking=True,
    )
    signed_document_id = fields.Many2one(
        "legal.document",
        string="Signed Document",
        ondelete="set null",
        copy=False,
        index=True,
        help="The signed PDF, filed once in the company's permanent document "
        "register so its expiry is chased on the same board as every other artefact.",
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    state = fields.Selection(
        STATE_SELECTION,
        default="received",
        required=True,
        index=True,
        tracking=True,
        group_expand=True,
    )
    is_closed = fields.Boolean(compute="_compute_is_closed", store=True, index=True)

    # ------------------------------------------------------------------
    # Related registers
    # ------------------------------------------------------------------
    obligation_ids = fields.One2many(
        "legal.contract.obligation", "contract_id", string="Obligations"
    )
    obligation_count = fields.Integer(compute="_compute_obligation_count")
    obligation_overdue_count = fields.Integer(compute="_compute_obligation_count")
    modification_ids = fields.One2many(
        "legal.contract.modification", "contract_id", string="Amendments"
    )
    modification_count = fields.Integer(compute="_compute_modification_count")

    note = fields.Html(translate=True)
    active = fields.Boolean(default=True)

    _value_positive = models.Constraint(
        "CHECK(value >= 0)", "A contract value cannot be negative."
    )

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("party_ids.role", "party_ids.partner_id")
    def _compute_counterparty(self):
        for contract in self:
            counterparties = contract.party_ids.filtered(
                lambda party: party.role == "counterparty"
            )
            contract.counterparty_id = counterparties[:1].partner_id

    @api.depends("party_ids")
    def _compute_party_count(self):
        # Separate from _compute_counterparty on purpose: that one is stored
        # (lists group on the counterparty) while this count is live, and one
        # compute serving both trips the registry's consistency warnings.
        for contract in self:
            contract.party_count = len(contract.party_ids)

    @api.depends("value", "modification_ids.value_change", "modification_ids.state")
    def _compute_current_value(self):
        for contract in self:
            applied = contract.modification_ids.filtered(
                lambda amendment: amendment.state == "applied"
            )
            contract.current_value = contract.value + sum(applied.mapped("value_change"))

    @api.depends("state")
    def _compute_is_closed(self):
        for contract in self:
            contract.is_closed = contract.state in CLOSED_STATES

    def _compute_obligation_count(self):
        obligations = dict(
            self.env["legal.contract.obligation"]._read_group(
                [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
            )
        )
        today = fields.Date.context_today(self)
        for contract in self:
            contract.obligation_count = obligations.get(contract, 0)
            contract.obligation_overdue_count = len(
                contract.obligation_ids.filtered(
                    lambda ob: ob.status == "pending"
                    and ob.due_date
                    and ob.due_date < today
                )
            )

    def _compute_modification_count(self):
        counts = dict(
            self.env["legal.contract.modification"]._read_group(
                [("contract_id", "in", self.ids)], ["contract_id"], ["__count"]
            )
        )
        for contract in self:
            contract.modification_count = counts.get(contract, 0)

    # ==================================================================
    # Onchange / defaults from the type
    # ==================================================================
    @api.onchange("type_id")
    def _onchange_type_id(self):
        for contract in self:
            contract_type = contract.type_id
            if not contract_type:
                continue
            contract.notice_days = contract_type.default_notice_days
            contract.auto_renew = contract_type.default_auto_renew

    # ==================================================================
    # Constraints
    # ==================================================================
    @api.constrains("effective_date", "expiry_date")
    def _check_date_order(self):
        for contract in self:
            if (
                contract.effective_date
                and contract.expiry_date
                and contract.expiry_date < contract.effective_date
            ):
                raise ValidationError(
                    _(
                        "The expiry date of contract %(title)s is before its "
                        "effective date. A contract cannot end before it begins.",
                        title=contract.title or contract.name,
                    )
                )

    # ==================================================================
    # Create - allocate the reference
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                company_id = vals.get("company_id") or self.env.company.id
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company_id)
                    .next_by_code("legal.contract")
                    or "New"
                )
        return super().create(vals_list)

    # ==================================================================
    # Gating
    # ==================================================================
    def _ensure_group(self, group_xmlid, action_label):
        """Refuse an action the current user is not senior enough to take.

        The gate is here rather than on the button because a button is a client
        hint, and the separation of duties an audit checks - the drafter of a
        contract cannot also approve it, and only the manager may terminate one -
        has to hold against a write that arrives over RPC.
        """
        if not self.env.user.has_group(group_xmlid):
            raise UserError(
                _(
                    "You do not have the authority to %(action)s. This is reserved "
                    "for a more senior role.",
                    action=action_label,
                )
            )

    def _require_state(self, expected, action_label):
        for contract in self:
            if contract.state not in expected:
                raise UserError(
                    _(
                        "Contract %(title)s cannot %(action)s from its current state.",
                        title=contract.title or contract.name,
                        action=action_label,
                    )
                )

    # ==================================================================
    # Workflow
    # ==================================================================
    def action_submit_review(self):
        self._require_state(("received",), _("be submitted for review"))
        self.write({"state": "legal_review"})
        for contract in self:
            contract.message_post(body=_("Submitted for legal review."))
        return True

    def action_start_negotiation(self):
        self._require_state(("legal_review",), _("move to negotiation"))
        self.write({"state": "negotiation"})
        return True

    def action_request_internal_approval(self):
        self._require_state(
            ("legal_review", "negotiation"), _("be sent for internal approval")
        )
        for contract in self:
            if not contract.counterparty_id:
                raise UserError(
                    _(
                        "Contract %s has no counterparty, so there is nothing to "
                        "approve. Add the other party before requesting approval.",
                        contract.title or contract.name,
                    )
                )
        self.write({"state": "internal_approval"})
        for contract in self:
            contract.message_post(body=_("Awaiting internal approval."))
        return True

    def action_grant_internal_approval(self):
        """Grant internal approval - the separation-of-duties gate.

        Reserved for the approver rung and above. This is the move a drafting
        clerk must not be able to make on their own file, so the check is here
        and not merely in the button's ``groups``.
        """
        self._ensure_group(
            "legal_core.group_legal_approver", _("grant internal approval")
        )
        self._require_state(("internal_approval",), _("be approved"))
        self.write({"state": "counterparty_review"})
        for contract in self:
            contract.message_post(
                body=_("Internally approved and sent to the counterparty.")
            )
        return True

    def action_counterparty_returned(self):
        self._require_state(("counterparty_review",), _("be marked ready to sign"))
        self.write({"state": "to_sign"})
        return True

    def action_mark_signed(self):
        """Record the signature.

        Reserved for the approver rung: signing binds the company, and the same
        clerk who prepared the file should not be the one recording that it is
        executed. If a signed document has not yet been filed the contract still
        moves, but the signature status stays "signed by us" rather than "fully
        signed" until the counter-signed copy is in the register.
        """
        self._ensure_group("legal_core.group_legal_approver", _("record a signature"))
        self._require_state(("to_sign", "counterparty_review"), _("be signed"))
        today = fields.Date.context_today(self)
        for contract in self:
            values = {"state": "signed"}
            if not contract.signature_date:
                values["signature_date"] = today
            if contract.signature_status == "unsigned":
                values["signature_status"] = (
                    "fully_signed" if contract.signed_document_id else "ours_signed"
                )
            contract.write(values)
            contract.message_post(body=_("Recorded as signed."))
        return True

    def action_activate(self):
        self._require_state(("signed",), _("be activated"))
        today = fields.Date.context_today(self)
        for contract in self:
            values = {"state": "active"}
            if not contract.commencement_date:
                values["commencement_date"] = contract.effective_date or today
            contract.write(values)
            contract.message_post(body=_("The contract is now in force."))
        return True

    def action_terminate(self):
        """Terminate the contract - reserved for the legal manager alone."""
        self._ensure_group("legal_core.group_legal_manager", _("terminate a contract"))
        self._require_state(("active", "signed"), _("be terminated"))
        self.write({"state": "terminated"})
        for contract in self:
            contract.message_post(body=_("Contract terminated."))
        return True

    def action_close(self):
        self._require_state(("active", "expired"), _("be closed"))
        self.write({"state": "closed"})
        return True

    def action_reset_to_review(self):
        """Send a stalled file back to legal review, keeping its trail."""
        self._ensure_group(
            "legal_core.group_legal_approver", _("reopen a contract for review")
        )
        self._require_state(
            ("negotiation", "internal_approval", "counterparty_review", "to_sign"),
            _("be sent back to review"),
        )
        self.write({"state": "legal_review"})
        return True

    # ==================================================================
    # Smart buttons
    # ==================================================================
    def action_open_obligations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Obligations"),
            "res_model": "legal.contract.obligation",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
        }

    def action_open_modifications(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Amendments"),
            "res_model": "legal.contract.modification",
            "view_mode": "list,form",
            "domain": [("contract_id", "=", self.id)],
            "context": {"default_contract_id": self.id},
        }

    def action_open_signed_document(self):
        self.ensure_one()
        if not self.signed_document_id:
            return self.action_file_signed_document()
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.document",
            "res_id": self.signed_document_id.id,
            "view_mode": "form",
        }

    def action_file_signed_document(self):
        """Open the wizard that files the signed contract into the register."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("File Signed Contract"),
            "res_model": "legal.contract.sign",
            "view_mode": "form",
            "target": "new",
            "context": {"default_contract_id": self.id},
        }

    # ==================================================================
    # Cron
    # ==================================================================
    @api.model
    def _cron_expire(self, limit=None):
        """Move in-force contracts past their expiry into ``expired``.

        A separate state rather than a computed colour, because "expired" is a
        fact the department reports on and a manager acts on - renew, let lapse,
        renegotiate - and a colour can be neither grouped nor escalated.
        """
        today = fields.Date.context_today(self)
        due = self.search(
            [("state", "=", "active"), ("expiry_date", "<", today)], limit=limit
        )
        for contract in due:
            contract.state = "expired"
            contract.message_post(
                body=_("Expired on %(date)s.", date=contract.expiry_date)
            )
        return len(due)
