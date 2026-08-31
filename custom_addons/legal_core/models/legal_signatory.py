from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalSignatory(models.Model):
    """Who may sign an official letter, and the seal that makes it real.

    An Iraqi كتاب رسمي is constituted by three things printed together: the
    letterhead, the signature of the most senior manager, and the ختم. A system
    that prints an unstamped page and calls it an official letter has produced a
    draft, not a letter, and the counter will say so.

    Holding the specimen signature and the seal as images, scoped to the bodies
    that accept them and bounded by validity dates, also solves a real
    operational problem: when the managing director changes, every template that
    named him is wrong, and the department finds out one rejected letter at a
    time. Here the change is one record with an end date.
    """

    _name = "legal.signatory"
    _description = "Authorised Signatory"
    _order = "sequence, name"
    _rec_names_search = ["name", "name_en"]

    # Both stored, because a bilingual letter prints both on the same page.
    name = fields.Char(string="Name (Arabic)", required=True, index="trigram")
    name_en = fields.Char(string="Name (English)")
    title = fields.Char(
        string="Title (Arabic)",
        required=True,
        help="المدير المفوض، المدير العام، معاون المدير العام - printed under the signature.",
    )
    title_en = fields.Char(string="Title (English)")

    entity_id = fields.Many2one(
        "legal.entity", string="Signs For", required=True, ondelete="cascade", index=True
    )
    user_id = fields.Many2one(
        "res.users",
        string="System User",
        help="Optional. Links the signatory to the person who approves in the system.",
    )
    partner_id = fields.Many2one("res.partner", string="Contact")

    specimen_signature = fields.Binary(
        string="Specimen Signature",
        attachment=True,
        help="Scanned or drawn. Printed on the letter where the template asks for it.",
    )
    stamp_image = fields.Binary(
        string="Official Seal (الختم)",
        attachment=True,
        help="The department seal, printed over or beside the signature block.",
    )

    valid_from = fields.Date()
    valid_to = fields.Date(
        help="Leave empty while the appointment stands. Setting it retires the "
        "signatory without deleting the letters they signed.",
    )
    body_ids = fields.Many2many(
        "legal.gov.body",
        string="Accepted By",
        help="Which counters accept this signature. Leave empty for all of them. "
        "Some bodies hold a filed specimen and will refuse anything else.",
    )
    is_default = fields.Boolean(
        string="Default Signatory",
        help="Used when a letter template does not name one explicitly.",
    )
    appointment_document_id = fields.Many2one(
        "legal.document",
        string="Appointment Document",
        help="The محضر or Registrar ratification that appointed them.",
    )
    sequence = fields.Integer(default=10)
    note = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    @api.depends("name", "title")
    def _compute_display_name(self):
        for signatory in self:
            signatory.display_name = " - ".join(
                part for part in (signatory.name, signatory.title) if part
            )

    @api.constrains("valid_from", "valid_to")
    def _check_validity_window(self):
        for signatory in self:
            if (
                signatory.valid_from
                and signatory.valid_to
                and signatory.valid_to < signatory.valid_from
            ):
                raise ValidationError(
                    _("A signatory cannot stop being valid before they start.")
                )

    def _is_valid_on(self, on_date=None):
        """Was this person authorised to sign on that date?

        Asked with a past date when a letter is reprinted, and with a future
        date when a submission is being planned around a known handover.
        """
        self.ensure_one()
        on_date = on_date or fields.Date.context_today(self)
        if self.valid_from and on_date < self.valid_from:
            return False
        if self.valid_to and on_date > self.valid_to:
            return False
        return True

    @api.model
    def _default_for(self, entity, body=None, on_date=None):
        """Pick the signatory a letter should carry.

        Prefers one the body explicitly accepts over a general default, because
        a body that keeps a filed specimen will reject anybody else, and that
        rejection costs a trip.
        """
        domain = [("entity_id", "=", entity.id)]
        candidates = self.search(domain, order="sequence, id")
        candidates = candidates.filtered(lambda s: s._is_valid_on(on_date))
        if body:
            specific = candidates.filtered(lambda s: body in s.body_ids)
            if specific:
                return specific[0]
            candidates = candidates.filtered(lambda s: not s.body_ids)
        default = candidates.filtered("is_default")
        return (default or candidates)[:1]
