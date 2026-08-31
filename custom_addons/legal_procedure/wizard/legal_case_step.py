from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalCaseStepWizardLine(models.TransientModel):
    """One configured capture field, rendered as a row.

    Rows rather than a generated form. A dialog whose fields are built at runtime
    needs a custom renderer, a view cache to invalidate and a story about what
    happens when a configurer renames a field while somebody has the dialog open;
    a list of typed rows needs none of that, reads correctly in Arabic and in
    RTL, and costs nothing to translate.

    The value is stored as text and converted on the way out, because the point
    of a capture field is that it is a fact about *one counter* - if it needed a
    real typed column, it should have been a real column, and the reserved-word
    check on ``legal.procedure.field`` says so.
    """

    _name = "legal.case.step.wizard.line"
    _description = "Step Dialog Line"
    _order = "sequence, id"

    wizard_id = fields.Many2one(
        "legal.case.step.wizard", required=True, ondelete="cascade"
    )
    field_id = fields.Many2one(
        "legal.procedure.field", string="Field", required=True, ondelete="cascade"
    )
    label = fields.Char(related="field_id.label", readonly=True)
    field_type = fields.Selection(related="field_id.field_type", readonly=True)
    placeholder = fields.Char(related="field_id.placeholder", readonly=True)
    help_text = fields.Char(related="field_id.help_text", readonly=True)
    required = fields.Boolean(related="field_id.required", readonly=True)
    sequence = fields.Integer(related="field_id.sequence", readonly=True)
    value = fields.Char(string="Answer")


class LegalCaseStepWizard(models.TransientModel):
    """The step dialog: the instruction, then the fields, then the move.

    Written in that order deliberately. ``clerk_instruction`` is shown *above*
    the fields because it is the sentence that tells somebody standing at a
    counter what good looks like - how many photocopies, which floor, who to ask
    for - and an instruction printed under the form is an instruction read after
    the mistake.
    """

    _name = "legal.case.step.wizard"
    _description = "Step Dialog"

    case_id = fields.Many2one(
        "legal.case", string="File", required=True, ondelete="cascade", readonly=True
    )
    step_id = fields.Many2one(
        "legal.procedure.step", related="case_id.step_id", readonly=True
    )
    clerk_instruction = fields.Html(related="step_id.clerk_instruction", readonly=True)
    desk_hint = fields.Char(related="step_id.desk_hint", readonly=True)
    # Stored, precomputed, editable. A wizard's lines have to be stored: the
    # client creates the transient record and *then* presses the button, so a
    # non-stored one2many would throw away everything the clerk typed between
    # those two calls and silently re-read the old answers.
    line_ids = fields.One2many(
        "legal.case.step.wizard.line",
        "wizard_id",
        string="Answers",
        compute="_compute_line_ids",
        store=True,
        readonly=False,
        precompute=True,
    )
    blocker_summary = fields.Char(related="case_id.blocker_summary", readonly=True)
    ready_to_advance = fields.Boolean(related="case_id.ready_to_advance", readonly=True)
    note = fields.Text(string="Remark", help="Recorded on the trail with the move.")

    @api.depends("case_id")
    def _compute_line_ids(self):
        for wizard in self:
            captured = wizard.case_id.capture_values or {}
            wizard.line_ids = [
                fields.Command.create(
                    {
                        "field_id": capture.id,
                        "value": captured.get(capture.code) or "",
                    }
                )
                for capture in wizard.case_id.step_id.capture_field_ids.sorted("sequence")
            ]

    def _store_values(self):
        self.ensure_one()
        captured = dict(self.case_id.capture_values or {})
        for line in self.line_ids:
            if line.required and not (line.value or "").strip():
                raise UserError(
                    _("“%s” has to be answered before the file can move.", line.label)
                )
            captured[line.field_id.code] = line.value or ""
        self.case_id.capture_values = captured
        return captured

    def action_save(self):
        """Record the answers without moving the file.

        Kept separate from the advance because half a walk is spent recording
        what happened at a counter that did not finish, and a dialog that only
        saves when it advances teaches people to advance before they should.
        """
        self.ensure_one()
        self._store_values()
        if self.note:
            self.case_id._log("check", self.note, closes_step=False)
        return {"type": "ir.actions.act_window_close"}

    def action_save_and_advance(self):
        self.ensure_one()
        self._store_values()
        if self.note:
            self.case_id._log("check", self.note, closes_step=False)
        self.case_id.action_advance()
        return {"type": "ir.actions.act_window_close"}
