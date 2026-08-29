# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class DmaDocumentType(models.Model):
    """A prerequisite document type of the office accreditation checklist.

    The seeded records mirror the application documents listed by IMAS 07.30 /
    TNMA 07.30/01 (the "prerequisites", الأوليات).
    """

    _name = "dma.document.type"
    _description = "Accreditation Document Type"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True, index="trigram")
    sequence = fields.Integer(default=10)
    required_default = fields.Boolean(
        string="Required by Default",
        default=True,
        help="New requests get this document flagged as mandatory for the "
             "office accreditation checklist.",
    )
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

