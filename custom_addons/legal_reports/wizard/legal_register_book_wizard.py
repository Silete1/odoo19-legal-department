from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _baghdad_year():
    return datetime.now(pytz.timezone("Asia/Baghdad")).year


class LegalRegisterBookWizard(models.TransientModel):
    """طباعة دفتر السجل - pick the book and the year.

    The register's Print menu prints the current year; this wizard exists for
    the other question the department is actually asked - the auditor who
    wants 2024's book, bound, with its voided rows struck through. The year is
    an explicit choice rather than a context guess because the artifact is
    formal: a book printed for the wrong year is not a smaller mistake for
    having been convenient.
    """

    _name = "legal.register.book.wizard"
    _description = "Print A Register Book"

    register_id = fields.Many2one(
        "legal.register",
        string="Register",
        required=True,
        help="The bound book to print. A department usually keeps two - "
        "outgoing and incoming - and prints each on its own.",
    )
    year = fields.Integer(
        string="Year",
        required=True,
        default=_baghdad_year,
        help="The book restarts on 1 January, so a printed book is a year's "
        "book. Defaults to the current Baghdad year.",
    )

    @api.constrains("year")
    def _check_year(self):
        for wizard in self:
            if not 1950 <= wizard.year <= 2100:
                raise ValidationError(
                    _("The register book year must be between 1950 and 2100.")
                )

    def action_print(self):
        """طباعة الدفتر"""
        self.ensure_one()
        return self.env.ref("legal_reports.action_report_register_book").report_action(
            self.register_id, data={"year": self.year}
        )
