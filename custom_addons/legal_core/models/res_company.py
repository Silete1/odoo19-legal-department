from odoo import fields, models


class ResCompany(models.Model):
    """Company-level settings that every printed letter and every clock reads.

    The letterhead lines are three separate fields rather than one block because
    an Iraqi official letter prints them as a stack in a fixed order -
    جمهورية العراق, then the ministry or parent, then the company, then the
    department - and a template that has them separately can lay them out; a
    template handed one blob cannot.
    """

    _inherit = "res.company"

    legal_entity_id = fields.Many2one(
        "legal.entity",
        string="Default Legal Entity",
        help="Used as the default on new files and letters when the company has "
        "only one registered person, so the distinction never reaches the user.",
    )
    legal_letterhead_line1 = fields.Char(
        string="Letterhead Line 1", default="جمهورية العراق", translate=True
    )
    legal_letterhead_line2 = fields.Char(
        string="Letterhead Line 2", translate=True, help="The ministry or parent body."
    )
    legal_letterhead_line3 = fields.Char(
        string="Letterhead Line 3", translate=True, help="The company itself."
    )
    legal_letterhead_line4 = fields.Char(
        string="Letterhead Line 4", translate=True, help="The department, e.g. the Legal Department."
    )
    legal_letterhead_logo = fields.Binary(string="Letterhead Emblem", attachment=True)
    legal_numeral_system = fields.Selection(
        [("western", "Western digits (0-9)"), ("arabic", "Arabic-Indic digits (٠-٩)")],
        default="western",
        required=True,
        string="Numerals On Printed Letters",
        help="Iraqi government output is mixed. Western digits are the safer default "
        "because reference numbers are quoted back over the telephone.",
    )
    legal_show_hijri = fields.Boolean(
        string="Print Hijri Dates",
        help="Adds the Hijri date beside the Gregorian one on letters. The research "
        "found no rule requiring dual dating on Iraqi correspondence - the Registrar's "
        "own bulletin and the Iraqi Official Gazette use Gregorian alone - so this is off by default.",
    )
