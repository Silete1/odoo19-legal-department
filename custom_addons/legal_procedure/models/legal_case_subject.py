from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models


class LegalCaseSubject(models.Model):
    """The numbered ت column of the official letter - قائمة الأشخاص.

    One Iraqi entry-visa letter routinely covers eight experts, listed in a
    numbered table with name, nationality, passport number and profession. That
    table is not decoration - it is the operative part of the letter, the
    counter checks each line against a passport, and a single wrong digit sends
    the whole letter back.

    **Both names are stored, and neither is translated.** ``translate=True``
    renders the reader's language and one language only, which is exactly wrong
    here: the Arabic name and the Latin transliteration print *on the same page*,
    because the Arabic is what the ministry files and the Latin is what the
    passport says. Two columns is the only shape that can produce that page.
    """

    _name = "legal.case.subject"
    _description = "Case Subject"
    _order = "case_id, sequence, id"
    _rec_names_search = ["name_ar", "name_en", "document_number"]

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(
        default=10,
        help="The ت number. It is quoted back by the counter, so it has to be "
        "stable and it has to be visible.",
    )
    name_ar = fields.Char(
        string="Name (Arabic)",
        required=True,
        index="trigram",
        help="As the ministry will file it.",
    )
    name_en = fields.Char(
        string="Name (Latin)",
        index="trigram",
        help="As the passport spells it. A mismatch here is the single most "
        "common reason a visa letter comes back.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        index=True,
        help="Where the person already exists in the system - an employee, a "
        "founder, a director.",
    )
    nationality_id = fields.Many2one("res.country", string="Nationality", index=True)
    profession = fields.Char(translate=True, help="Printed in the letter's table.")
    document_type = fields.Selection(
        [
            ("passport", "Passport"),
            ("id_card", "National Identity"),
            ("residency", "Residency Card"),
            ("other", "Other"),
        ],
        default="passport",
        required=True,
    )
    document_number = fields.Char(string="Document Number", index="trigram")
    document_expiry = fields.Date(
        string="Document Expires",
        help="Feeds a blocking check. You cannot ask for a one-year visa on a "
        "passport that expires in four months, and the counter will say so.",
    )
    minimum_validity_months = fields.Integer(
        string="Validity Demanded (months)",
        default=6,
        help="How much life the counter insists the document still has. Six months "
        "is the usual Iraqi answer; a one-year residency application wants twelve.",
    )
    note = fields.Char(translate=True)
    active = fields.Boolean(default=True)

    @api.depends("name_ar", "name_en")
    def _compute_display_name(self):
        for subject in self:
            subject.display_name = subject.name_ar or subject.name_en or ""

    def _blocking_reason(self):
        """Why this person would stop the file at the counter.

        Returns the sentence rather than a boolean, so the gate, the desk row and
        the readiness meter all show the same words. A person whose passport
        expires inside the window the body demands is not a warning - the counter
        refuses the application outright, and it is cheaper to find out here.
        """
        self.ensure_one()
        if not self.document_expiry:
            return ""
        months = self.minimum_validity_months or 0
        threshold = fields.Date.context_today(self) + relativedelta(months=months)
        if self.document_expiry >= threshold:
            return ""
        if self.document_expiry < fields.Date.context_today(self):
            return _(
                "%(name)s's document expired on %(date)s.",
                name=self.display_name,
                date=self.document_expiry,
            )
        return _(
            "%(name)s's document expires on %(date)s, inside the %(months)s month(s) "
            "the counter demands.",
            name=self.display_name,
            date=self.document_expiry,
            months=months,
        )
