# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""What the Directorate expects of each kind of prerequisite document.

The checklist already knows *which* documents an applicant owes. This says what
kind of thing each of them is: whether it is a piece of evidence that expires,
how long before an expiry the Certifications Division wants to be warned, and
whether an expired copy should hold the office accreditation up.

Deliberately no default validity periods
----------------------------------------
How long a company registration certificate or an insurance policy stays valid
is a matter of Iraqi law and of the policy the issuer printed on it - not
something a software module may decide. So the module never assumes a duration:
it records the expiry date the officer reads off the document, and it warns.
``blocks_on_expiry`` is off everywhere by default for the same reason: turning
an expired document into a hard gate is a policy decision, and it is the
Accreditation Manager who takes it, in the configuration screen.
"""
from odoo import api, fields, models


class DmaDocumentType(models.Model):
    _inherit = "dma.document.type"

    code = fields.Char(
        string="Code", index="trigram", copy=False,
        help="Short technical key. Used to name the folder of this document "
             "inside a downloaded accreditation dossier, so the archive stays "
             "readable whatever the interface language.",
    )
    has_validity = fields.Boolean(
        string="Expires",
        help="This evidence carries an issue and an expiry date - an insurance "
             "policy or a registration certificate does, an organisational "
             "chart does not.",
    )
    expiry_warning_days = fields.Integer(
        string="Warn Before (days)", default=30,
        help="How long before the expiry date the document starts showing as "
             "expiring soon.",
    )
    blocks_on_expiry = fields.Boolean(
        string="Expiry Blocks Accreditation",
        help="An expired copy of this document counts as not accepted, so the "
             "office accreditation cannot be granted until it is replaced. Off "
             "by default: making an expiry a hard gate is a decision of the "
             "Directorate, not of the software.",
    )

    _unique_code = models.UniqueIndex(
        "(code) WHERE code IS NOT NULL",
        "Two document types cannot share the same code.",
    )
    _warning_days_positive = models.Constraint(
        "CHECK(expiry_warning_days >= 0)",
        "The warning period of a document type cannot be negative.",
    )

    @api.onchange("has_validity")
    def _onchange_has_validity(self):
        """A document that does not expire cannot block on an expiry."""
        for doc_type in self:
            if not doc_type.has_validity:
                doc_type.blocks_on_expiry = False

    def _dossier_folder(self):
        """A stable, filesystem-safe folder name for the dossier archive."""
        self.ensure_one()
        return self.code or ("type-%s" % self.id)
