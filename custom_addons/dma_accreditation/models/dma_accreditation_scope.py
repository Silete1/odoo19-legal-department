# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class DmaAccreditationScope(models.Model):
    """A demining activity a company may be accredited for (IMAS 07.30 scope)."""

    _name = "dma.accreditation.scope"
    _description = "Accreditation Scope"
    _order = "sequence, name, id"

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(
        help="Short internal code used to refer to the scope in the interface "
             "and in operational shorthand. The official letter and the "
             "certificate print the full name of the scope.",
    )
    sequence = fields.Integer(default=10)
    color = fields.Integer(string="Colour Index")
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

