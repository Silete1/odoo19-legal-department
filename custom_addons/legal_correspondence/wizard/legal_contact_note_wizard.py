from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalContactNoteWizard(models.TransientModel):
    """تدوين اتصال - what the counter actually said.

    This is the wizard that makes the follow-up honest. An Iraqi file does not
    move because a letter was sent; it moves because somebody rang Abu Ahmed and
    he said the papers are with the legal adviser and to come back after Eid.
    None of that is correspondence - no number was taken and nothing entered the
    book - but all of it is evidence, and without somewhere to put it the
    department either loses it or fakes a letter to hold it.

    ``promised_on`` is the field that earns the whole model. It moves the reply
    clock onto the date the counter gave, so the next chase does not fire on a
    body that has already answered. Software that chases people who answered is
    software people switch off.
    """

    _name = "legal.contact.note.wizard"
    _description = "Record A Call Or A Personal Visit"

    correspondence_id = fields.Many2one(
        "legal.correspondence",
        string="About",
        help="The letter this call was about. Leave empty for a call that "
        "concerns nothing we have written yet.",
    )
    kind_id = fields.Many2one(
        "legal.correspondence.kind",
        string="How",
        required=True,
        domain="[('is_contact_note', '=', True)]",
        default=lambda self: self.env.ref(
            "legal_correspondence.kind_phone_note", raise_if_not_found=False
        ),
    )
    gov_body_id = fields.Many2one("legal.gov.body", string="Body", required=True)
    body_section = fields.Char(string="Section / Window")
    contact_date = fields.Date(
        string="تاريخ الاتصال - When", required=True, default=fields.Date.context_today
    )
    spoke_to = fields.Char(
        string="مع من - Spoke To",
        required=True,
        help="The name, and the section if you have it. In Iraqi follow-up this is "
        "worth more than any escalation rule.",
    )
    said = fields.Text(
        string="ماذا قالوا - What They Said",
        required=True,
        help="Verbatim where possible. 'The file is with the legal adviser' and "
        "'the file is missing' need different next steps.",
    )
    promised_on = fields.Date(
        string="وعد بـ - Promised For",
        help="The date they gave. It moves the reply clock and suppresses the "
        "next chase, so we stop ringing a body that has already answered.",
    )
    entity_id = fields.Many2one(
        "legal.entity",
        string="Concerns",
        default=lambda self: self.env.company.legal_entity_id.id,
    )
    subject = fields.Char(string="م/ الموضوع")

    @api.onchange("correspondence_id")
    def _onchange_correspondence_id(self):
        for wizard in self:
            parent = wizard.correspondence_id
            if not parent:
                continue
            wizard.gov_body_id = parent.gov_body_id
            wizard.body_section = parent.body_section
            wizard.entity_id = parent.entity_id
            wizard.subject = parent.subject

    def action_record(self):
        """حفظ التدوين - no register number is taken."""
        self.ensure_one()
        if not self.kind_id.is_contact_note:
            raise UserError(
                _(
                    "'%s' is not a contact note, so recording it here would take a "
                    "register number for a telephone call.",
                    self.kind_id.display_name,
                )
            )
        parent = self.correspondence_id
        note = self.env["legal.correspondence"].create(
            {
                "kind_id": self.kind_id.id,
                "direction": "internal",
                "secrecy": parent.secrecy if parent else "ordinary",
                "our_date": self.contact_date,
                "gov_body_id": self.gov_body_id.id,
                "body_section": self.body_section,
                "subject": self.subject or _("Contact note - %s", self.gov_body_id.display_name),
                "entity_id": self.entity_id.id,
                "reply_to_id": parent.id if parent else False,
                "spoke_to": self.spoke_to,
                "said": self.said,
                "promised_on": self.promised_on,
                "state": "registered",
            }
        )
        if parent:
            parent.message_post(
                body=_(
                    "Spoke to %(who)s at %(body)s: %(said)s%(promise)s",
                    who=self.spoke_to,
                    body=self.gov_body_id.display_name,
                    said=self.said,
                    promise=_(" Promised for %s.", self.promised_on)
                    if self.promised_on
                    else "",
                )
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Contact Note"),
            "res_model": "legal.correspondence",
            "res_id": note.id,
            "view_mode": "form",
            "target": "current",
        }
