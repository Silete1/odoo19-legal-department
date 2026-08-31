from odoo import fields, models


class LegalFee(models.Model):
    """Two stored related columns, so the fee book can be sliced.

    "What did we pay the Registrar this year" and "what does a company
    formation actually cost us" are the two questions a legal manager asks of
    the fee register, and both group by fields that live one join away on the
    case. A pivot view cannot follow that join, so the body and the procedure
    are denormalised here as stored related fields - written by the ORM
    whenever the case moves, never by hand, and costing two indexed columns.

    No behaviour changes and no access rule widens: the columns ride
    ``legal.fee``'s existing ACLs.
    """

    _inherit = "legal.fee"

    body_id = fields.Many2one(
        related="case_id.body_id",
        string="Body",
        store=True,
        index=True,
        readonly=True,
    )
    procedure_type_id = fields.Many2one(
        related="case_id.procedure_type_id",
        string="Procedure",
        store=True,
        index=True,
        readonly=True,
    )
