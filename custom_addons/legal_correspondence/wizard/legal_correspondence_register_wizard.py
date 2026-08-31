from odoo import _, api, fields, models


class LegalCorrespondenceRegisterWizard(models.TransientModel):
    """The mail room, in six fields - تسجيل كتاب وارد.

    A letter arrives at nine in the morning with a queue behind it. The clerk has
    the envelope, their number and a subject line, and nothing else - no file, no
    case, often not even a clear idea which section it belongs to. This wizard
    asks for exactly that and nothing more, because a form that demands a legal
    entity and a template before it will save is a form that produces a pile of
    unregistered letters on somebody's desk.

    Everything else is filled from configuration: the direction and the secrecy
    from the book, the reply window from the kind, the channel and the
    salutation from the body.
    """

    _name = "legal.correspondence.register.wizard"
    _description = "Register An Incoming Letter"

    register_id = fields.Many2one(
        "legal.register",
        string="Register",
        required=True,
        domain="[('direction', 'in', ('in', 'internal'))]",
        default=lambda self: self._default_register(),
    )
    kind_id = fields.Many2one(
        "legal.correspondence.kind",
        string="Kind",
        required=True,
        domain="[('is_contact_note', '=', False)]",
        default=lambda self: self.env.ref(
            "legal_correspondence.kind_in_letter", raise_if_not_found=False
        ),
    )
    gov_body_id = fields.Many2one("legal.gov.body", string="From Which Body", required=True)
    body_section = fields.Char(string="Section / Window")
    their_number = fields.Char(string="Their Number")
    their_date = fields.Date(
        string="Their Date", default=fields.Date.context_today
    )
    our_date = fields.Date(
        string="Received On",
        required=True,
        default=fields.Date.context_today,
        help="The day it reached us. The register number is allocated against it.",
    )
    subject = fields.Char(string="Subject", required=True)
    entity_id = fields.Many2one(
        "legal.entity",
        string="Concerns",
        default=lambda self: self.env.company.legal_entity_id.id,
    )
    reply_to_id = fields.Many2one(
        "legal.correspondence",
        string="In Reply To",
        help="Our letter this one answers, if we know it. Setting it stops the "
        "reply clock on that letter, which is the whole reason the clock exists.",
    )
    document_action = fields.Selection(
        [
            ("for_information", "For Information"),
            ("for_action", "For Action"),
            ("for_signature", "For Signature"),
            ("referred", "Referred"),
        ],
        string="Marked",
        default="for_action",
    )
    secrecy = fields.Selection(
        [("ordinary", "Ordinary"), ("secret", "Confidential")],
        default="ordinary",
        required=True,
    )
    attachment_ids = fields.Many2many("ir.attachment", string="Scans")
    note = fields.Text(string="Remark")

    @api.model
    def _default_register(self):
        return self.env["legal.register"].search(
            [("direction", "=", "in"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )

    @api.onchange("register_id")
    def _onchange_register_id(self):
        for wizard in self:
            if wizard.register_id:
                wizard.secrecy = wizard.register_id.secrecy
                if wizard.register_id.body_id and not wizard.gov_body_id:
                    wizard.gov_body_id = wizard.register_id.body_id

    @api.onchange("reply_to_id")
    def _onchange_reply_to_id(self):
        for wizard in self:
            parent = wizard.reply_to_id
            if not parent:
                continue
            wizard.gov_body_id = parent.gov_body_id
            wizard.body_section = parent.body_section
            wizard.entity_id = parent.entity_id
            wizard.secrecy = parent.secrecy
            if not wizard.subject:
                wizard.subject = parent.subject

    def action_register(self):
        """تسجيل - allocate the number and open the entry."""
        self.ensure_one()
        entry = self.env["legal.correspondence"].create(
            {
                "register_id": self.register_id.id,
                "kind_id": self.kind_id.id,
                "direction": self.register_id.direction,
                "secrecy": self.secrecy,
                "our_date": self.our_date,
                "their_number": self.their_number,
                "their_date": self.their_date,
                "gov_body_id": self.gov_body_id.id,
                "body_section": self.body_section,
                "subject": self.subject,
                "entity_id": self.entity_id.id,
                "reply_to_id": self.reply_to_id.id,
                "document_action": self.document_action,
                "reply_expected": self.kind_id.expects_reply,
                "reply_days": self.kind_id.default_reply_days,
                "attachment_ids": [(6, 0, self.attachment_ids.ids)],
                "body_html": self.note or False,
                "state": "registered",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Registered Entry"),
            "res_model": "legal.correspondence",
            "res_id": entry.id,
            "view_mode": "form",
            "target": "current",
        }
