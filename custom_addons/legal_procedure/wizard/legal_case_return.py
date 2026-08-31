from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalCaseReturn(models.TransientModel):
    """The dialog that will not let a file be sent back without a reason.

    There is no version of this action that skips the reason, and the wizard
    exists precisely to make that true in the interface as well as in the engine.
    A returned Iraqi file is the norm rather than the exception - twice before a
    grant is unremarkable - and the only question anybody asks afterwards is what
    the counter objected to and whether it was fixed. A return recorded as a bare
    state change answers neither.
    """

    _name = "legal.case.return"
    _description = "Return A File For Correction"

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", readonly=True
    )
    transition_id = fields.Many2one(
        "legal.procedure.transition", string="Move", ondelete="cascade", readonly=True
    )
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Send Back To",
        required=True,
        ondelete="cascade",
        domain="[('procedure_type_id', '=', procedure_type_id)]",
        compute="_compute_step_id",
        store=True,
        readonly=False,
        precompute=True,
        help="Usually the step that prepared whatever the counter refused.",
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type", related="case_id.procedure_type_id", readonly=True
    )
    # Required in the view, checked in :meth:`action_confirm`, and deliberately
    # NOT required on the column. A database NOT NULL produces "reason is
    # required", which tells a clerk nothing; the check below tells them what the
    # reason is for, which is the difference between a field they fill in and a
    # field they fill in with a full stop.
    reason = fields.Text(
        help="What the counter said, in their words. This is what the next round "
        "is corrected against, so “rejected” is not an answer.",
    )
    document_line_ids = fields.Many2many(
        "legal.case.document",
        string="Documents They Refused",
        domain="[('case_id', '=', case_id)]",
        help="Ticking the lines the counter refused saves the clerk redoing the "
        "whole checklist, and records which requirement actually failed.",
    )

    @api.depends("case_id", "transition_id")
    def _compute_step_id(self):
        for wizard in self:
            wizard.step_id = (
                wizard.transition_id.to_step_id
                or wizard.case_id.step_id.return_to_step_id
                or wizard.case_id.procedure_type_id._first_step()
            )

    def action_confirm(self):
        self.ensure_one()
        if not (self.reason or "").strip():
            raise UserError(
                _(
                    "A return needs a reason. Without it the clerk redoing the file is "
                    "guessing at what the counter wanted."
                )
            )
        if self.document_line_ids:
            self.document_line_ids.write(
                {"rejected": True, "rejection_reason": self.reason, "accepted": False}
            )
        # A transition can demand a reason without being a return - a
        # conditional grant, a withdrawal, a referral all want one. Treating
        # every reasoned move as a return would open a round the file never had.
        if self.transition_id and not self.transition_id.is_return:
            self.case_id._fire(self.transition_id, reason=self.reason)
        else:
            self.case_id._return_for_correction(
                self.step_id, self.reason, transition=self.transition_id
            )
        return {"type": "ir.actions.act_window_close"}
