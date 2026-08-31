from odoo import _, fields, models


class LegalRequestApprove(models.TransientModel):
    """The approval dialog - a decision with a reason, never a silent tick.

    An approver signs off the department's answer, and three people later ask
    what was decided: the requester who acts on it, the manager who is
    accountable for it, and the auditor. Recording the decision and its note is
    what lets each of them read the sign-off rather than infer it from a state
    change. The gate itself - approver or above - is enforced on the request, so
    the wizard only has to collect the words.
    """

    _name = "legal.request.approve"
    _description = "Approve A Legal Request"

    request_id = fields.Many2one(
        "legal.request",
        string="Request",
        required=True,
        ondelete="cascade",
        readonly=True,
    )
    decision = fields.Selection(
        [
            ("approved", "Approved"),
            ("approved_conditional", "Approved With Conditions"),
        ],
        string="Decision",
        default="approved",
        required=True,
    )
    note = fields.Text(
        string="Note",
        help="The conditions attached, or why the answer is signed as it stands. "
        "Required where the decision is conditional.",
    )

    def action_confirm(self):
        self.ensure_one()
        self.request_id._apply_approval(self.decision, self.note)
        return {"type": "ir.actions.act_window_close"}
