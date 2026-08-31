import re

from markupsafe import Markup

from odoo import _, api, fields, models

#: The placeholders a template may use, and what each resolves to. Deliberately
#: a fixed, documented vocabulary rendered by ``str`` substitution rather than
#: QWeb or ``safe_eval``: a letter template is edited by the legal manager, not
#: by a developer, and giving that person an expression language is giving them
#: a way to execute arbitrary code from a form view.
PLACEHOLDERS = (
    "our_number",
    "our_date",
    "their_number",
    "their_date",
    "body",
    "body_section",
    "body_reference",
    "subject",
    "entity",
    "entity_en",
    "signatory",
    "signatory_title",
    "salutation",
    "today",
)

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


class LegalLetterTemplate(models.Model):
    """The shape of a letter this department sends often - نموذج كتاب.

    A department writes the same eight letters all year: a request for a
    good-standing certificate, a covering letter for an annual return, a chase, a
    request to correct a name. Holding them as templates is not a convenience -
    it is how the salutation, the addressee block and the signature block stay
    correct when the managing director changes, instead of being wrong in
    fourteen saved Word files nobody will find.

    ``letterhead_variant`` exists because Iraqi departments print on two kinds of
    paper and the difference is four centimetres of top margin. On pre-printed
    paper the emblem is already there and drawing it again produces a letter with
    two emblems; on plain paper, not drawing it produces a letter the counter
    will not accept. Each variant therefore has its own paper format.
    """

    _name = "legal.letter.template"
    _description = "Official Letter Template"
    _order = "sequence, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(required=True, help="Stable key used by content packs.")
    body_id = fields.Many2one(
        "legal.gov.body",
        string="Addressed To",
        ondelete="restrict",
        index=True,
        help="Optional. A template written for one counter carries its salutation "
        "and its filed signature; a general template leaves this empty.",
    )
    subject_template = fields.Char(
        string="Subject (م/)",
        translate=True,
        help="Printed after م/ as the bold subject line. May use the placeholders "
        "listed on the Placeholders tab.",
    )
    body_template = fields.Html(
        string="Body",
        translate=True,
        sanitize=False,
        help="The text of the letter. Placeholders in braces are substituted at "
        "issue and the result is frozen onto the entry, so a reprint returns the "
        "filed copy rather than a re-render against today's template.",
    )
    signatory_id = fields.Many2one(
        "legal.signatory",
        string="Signed By",
        ondelete="restrict",
        help="Leave empty to let the entry pick the signatory this body accepts.",
    )
    letterhead_variant = fields.Selection(
        [
            ("preprinted", "Pre-printed paper (leave the head blank)"),
            ("drawn", "Draw the emblem and the letterhead"),
        ],
        default="preprinted",
        required=True,
        help="Pre-printed paper already carries the emblem, so drawing it again "
        "produces a letter with two. Each variant prints on its own paper format.",
    )
    show_qr = fields.Boolean(
        string="Print Verification QR",
        default=True,
        help="Encodes the entry's verification token, so a reader can check the "
        "number against the register. It is not a signature.",
    )
    show_subject_table = fields.Boolean(
        string="Print The Numbered Table",
        help="The ت table. This is where the several people covered by one letter "
        "go - a visa request for eleven engineers is one letter and eleven rows, "
        "not eleven letters.",
    )
    cc_list = fields.Text(
        string="Copies To (نسخة منه إلى)",
        translate=True,
        help="One recipient per line, printed at the bottom left.",
    )
    sequence = fields.Integer(default=10)
    note = fields.Text(translate=True)
    company_id = fields.Many2one("res.company", index=True)
    active = fields.Boolean(default=True)

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "A letter template code must be unique per company."
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for template in self:
            template.display_name = template.name or template.code or ""

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _placeholder_values(self, correspondence):
        """The vocabulary, resolved against one entry."""
        self.ensure_one()
        signatory = correspondence.signatory_id or self.signatory_id
        body = correspondence.gov_body_id or self.body_id
        return {
            "our_number": correspondence.our_number or "",
            "our_date": fields.Date.to_string(correspondence.our_date) or "",
            "their_number": correspondence.their_number or "",
            "their_date": fields.Date.to_string(correspondence.their_date) or "",
            "body": body.display_name or "",
            "body_section": correspondence.body_section or "",
            "body_reference": correspondence.body_reference or "",
            "subject": correspondence.subject or "",
            "entity": correspondence.entity_id.name or "",
            "entity_en": correspondence.entity_id.name_en or "",
            "signatory": signatory.name or "",
            "signatory_title": signatory.title or "",
            "salutation": body.salutation or "",
            "today": fields.Date.to_string(fields.Date.context_today(self)),
        }

    def _substitute(self, text, values):
        """Replace only the documented placeholders.

        An unknown ``{something}`` is left exactly as written rather than raising
        or vanishing: a template containing a brace for some other reason must
        still print, and a typo must be visible on the draft where the clerk can
        see it, not swallowed.
        """
        if not text:
            return text

        def _one(match):
            key = match.group(1)
            if key in values:
                return str(values[key])
            return match.group(0)

        return _PLACEHOLDER_RE.sub(_one, text)

    def render_for(self, correspondence):
        """Return ``(subject, body_html)`` for this entry."""
        self.ensure_one()
        values = self._placeholder_values(correspondence)
        subject = self._substitute(self.subject_template or "", values)
        body = self._substitute(self.body_template or "", values)
        return subject, Markup(body) if body else Markup("")

    def action_preview_placeholders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "info",
                "sticky": False,
                "title": _("Placeholders"),
                "message": ", ".join("{%s}" % name for name in PLACEHOLDERS),
            },
        }
