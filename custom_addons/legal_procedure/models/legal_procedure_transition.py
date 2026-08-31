from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval


class LegalProcedureTransition(models.Model):
    """The interesting moves only - التحويلات.

    A linear walk needs none of these. The engine synthesises "next" from the
    step ordering, so a fourteen-step procedure that never branches is fourteen
    step rows and nothing else. Transitions exist for the moves that carry
    information the ordering cannot: the branch, the return for correction, the
    rejection, the referral to a second directorate.

    **The name is the button.** ``name`` is not a description of the move, it is
    the string the clerk presses - "تحويل المعاملة إلى دائرة الإقامة" - and it
    is translatable for exactly that reason. Naming these "approve" and "reject"
    and then rendering a generic label is how software ends up asking an Iraqi
    clerk to press "Approve" on a file being sent to the residency directorate.

    The four ``require_*`` flags are guards, not decoration. ``require_valid_poa``
    in particular must genuinely block: the counter will refuse a file presented
    by somebody who is not on the وكالة, so software that lets the move happen
    has only moved the failure to the pavement outside the ministry.
    """

    _name = "legal.procedure.transition"
    _description = "Procedure Transition"
    _order = "procedure_type_id, sequence, id"

    name = fields.Char(
        required=True,
        translate=True,
        help="The button the clerk presses, in their words: "
        "“تحويل المعاملة إلى دائرة الإقامة”, “إعادة للتصحيح”, “قبول مشروط”.",
    )
    code = fields.Char(help="Stable key, snapshotted onto the immutable log.")
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    from_step_id = fields.Many2one(
        "legal.procedure.step",
        string="From",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
    )
    to_step_id = fields.Many2one(
        "legal.procedure.step",
        string="To",
        required=True,
        ondelete="cascade",
        index=True,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
    )
    group_ids = fields.Many2many(
        "res.groups",
        string="Who May Press It",
        help="Leave empty to let anyone who can edit the file press it. A move "
        "that commits the company - signing, submitting, withdrawing - should "
        "name the desk that owns the decision.",
    )
    condition_domain = fields.Char(
        string="Only When",
        help="A filter evaluated against the file itself, so “an MoI approval is "
        "needed when any founder is foreign” is configuration rather than a "
        "Python branch nobody outside the vendor can change.",
    )
    require_reason = fields.Boolean(
        help="Forces a written reason. Always set on a return or a rejection: the "
        "reason is what the next round is corrected against.",
    )
    require_valid_poa = fields.Boolean(
        string="Needs A Valid Power Of Attorney",
        help="Blocks the move outright when no وكالة on the file is in force for "
        "this body. The counter will refuse it, so pretending otherwise only moves "
        "the failure to the pavement outside the ministry.",
    )
    require_documents = fields.Boolean(
        string="Needs The Checklist Complete",
        help="Blocks while any blocking document line is unsatisfied.",
    )
    require_fees_paid = fields.Boolean(
        string="Needs The Fees Paid",
        help="Blocks while any fee due at or before this step is unpaid.",
    )
    is_return = fields.Boolean(
        string="Sends It Back",
        help="Marks the move as a return rather than a step forward. A return "
        "opens a new round, pauses the service-level clock and marks the previous "
        "round's approvals as superseded instead of deleting them.",
    )
    # A transition deliberately carries no outcome of its own. The verdict on a
    # file is a property of the step it lands on - ``legal.case.outcome`` is a
    # stored related field - so recording it twice would create two answers to
    # "was this granted", and they would eventually disagree. A move that
    # concludes something targets a terminal step that says so.
    sequence = fields.Integer(default=10, help="Left to right order of the buttons.")
    colour = fields.Integer(string="Colour")
    note = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    @api.depends("name")
    def _compute_display_name(self):
        for transition in self:
            transition.display_name = transition.name or ""

    @api.constrains("from_step_id", "to_step_id", "procedure_type_id")
    def _check_steps_belong_to_procedure(self):
        for transition in self:
            for step in (transition.from_step_id, transition.to_step_id):
                if step and step.procedure_type_id != transition.procedure_type_id:
                    raise ValidationError(
                        _(
                            "“%(transition)s” points at “%(step)s”, which belongs to another "
                            "procedure. A file cannot leave its own state machine.",
                            transition=transition.name,
                            step=step.display_name,
                        )
                    )
            if transition.from_step_id == transition.to_step_id:
                raise ValidationError(
                    _("“%s” leads back to the step it starts from.", transition.name)
                )

    @api.constrains("condition_domain")
    def _check_condition_domain(self):
        """Refuse a condition that can never be true.

        This is the fault worth catching hardest, because it has no symptom. An
        always-false condition does not raise, it does not log, and it does not
        show up in a test: the button simply never appears, and a clerk does not
        report a button they have never seen.
        """
        case_model = self.env["legal.case"]
        for transition in self.filtered("condition_domain"):
            try:
                domain = Domain(safe_eval(transition.condition_domain, {"uid": self.env.uid}))
                domain.validate(case_model)
            except ValidationError:
                raise
            except Exception as error:  # noqa: BLE001 - the message is the product
                raise ValidationError(
                    _(
                        "The condition on “%(transition)s” is not a usable filter: %(error)s",
                        transition=transition.name,
                        error=error,
                    )
                ) from error
            if domain.optimize(case_model).is_false():
                raise ValidationError(
                    _(
                        "The condition on “%s” can never be true, so this button would never "
                        "appear on any file. Nobody reports a button they have never seen, so "
                        "it is refused here instead.",
                        transition.name,
                    )
                )

    def _matches(self, case):
        """Does this transition's condition hold for that file?

        Evaluated with :meth:`filtered_domain` rather than a search, so an
        unsaved file in a form still gets the right buttons.
        """
        self.ensure_one()
        if not self.condition_domain:
            return True
        try:
            domain = safe_eval(self.condition_domain, {"uid": self.env.uid})
            return bool(case.filtered_domain(domain))
        except Exception:  # noqa: BLE001 - a broken condition hides the button, never breaks the form
            return False

    def action_fire_on_case(self):
        """Fire this move on the file the embedded list was opened from.

        The file arrives through the field's own context rather than through
        ``active_id``: the button is pressed inside an x2many on the case form,
        where ``active_id`` may still be the action's rather than the record's.
        Reading a named key instead makes the failure loud if the view is ever
        wired up wrongly, rather than quietly firing the move on the wrong file.
        """
        self.ensure_one()
        case_id = self.env.context.get("legal_case_id")
        if not case_id:
            raise UserError(
                _(
                    "This move has to be made from the file itself - open “%s” and press "
                    "it there.",
                    self.display_name,
                )
            )
        case = self.env["legal.case"].browse(case_id)
        return case.action_fire_transition(self.id)
