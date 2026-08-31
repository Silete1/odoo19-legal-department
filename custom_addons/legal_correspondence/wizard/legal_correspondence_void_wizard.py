from odoo import _, fields, models
from odoo.exceptions import UserError


class LegalCorrespondenceVoidWizard(models.TransientModel):
    """إلغاء القيد - strike the line across the page, and say why.

    The number is never released and never reused. A voided entry keeps its
    place in the book exactly as a clerk keeps the page: the line is drawn, ملغى
    is written beside it, and the next letter takes the next number. That is the
    only way the register can later answer the one question it exists to answer -
    "there is no 148 in your book, what happened to it?".

    The reason is mandatory for the same reason. Somebody will ask, years from
    now, and "voided by admin on 3 March" answers nothing.
    """

    _name = "legal.correspondence.void.wizard"
    _description = "Void A Register Entry"

    correspondence_id = fields.Many2one(
        "legal.correspondence", string="Entry", required=True, readonly=True
    )
    our_number = fields.Char(related="correspondence_id.our_number", readonly=True)
    subject = fields.Char(related="correspondence_id.subject", readonly=True)
    reason = fields.Text(
        string="سبب الإلغاء - Reason",
        required=True,
        help="What went wrong: wrong body, duplicate of an earlier number, the "
        "letter was never sent, the counter refused it at the window.",
    )
    replacement_id = fields.Many2one(
        "legal.correspondence",
        string="Replaced By",
        help="Optional. The entry that was issued in its place, so the trail "
        "leads somewhere instead of stopping at a struck-through line.",
    )

    def action_void(self):
        """تأكيد الإلغاء"""
        self.ensure_one()
        if not self.env.user.has_group("legal_core.group_legal_officer"):
            raise UserError(
                _(
                    "Striking a numbered entry out of the register is reserved for "
                    "the follow-up officer and above. The clerk who typed a wrong "
                    "entry asks their officer to void it."
                )
            )
        entry = self.correspondence_id
        if entry.state == "void":
            raise UserError(_("That entry is already void."))
        reason = (self.reason or "").strip()
        entry.write({"state": "void", "void_reason": reason})
        body = _("Voided: %s", reason)
        if self.replacement_id:
            body = _(
                "Voided: %(reason)s. Replaced by %(replacement)s.",
                reason=reason,
                replacement=self.replacement_id.display_name,
            )
        entry.message_post(body=body)
        return {"type": "ir.actions.act_window_close"}
