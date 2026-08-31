from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LegalProcedurePhase(models.Model):
    """The four to six coarse phases a file passes through - المراحل.

    Steps are the state machine; phases are what a human can hold in their head.
    A براءة ذمة walk is twenty-two counters, and no manager wants a rail with
    twenty-two segments on it: they want to know whether the file is being
    prepared, sitting at the body, being decided or finished, and that is four
    segments regardless of how many counters sit underneath.

    Phases are per procedure rather than global because the coarse shape genuinely
    differs: a tax clearance has a long *with the body* phase and no decision to
    speak of, while a capital increase is almost entirely preparation and then one
    ratification. A shared global list would force both into the same rail and the
    rail would stop meaning anything.

    ``kind`` exists so the visual rail can colour a phase without reading its
    name. It is a closed alphabet of shapes, not a list of things in the world,
    which is why a Selection is legitimate here.
    """

    _name = "legal.procedure.phase"
    _description = "Procedure Phase"
    _order = "procedure_type_id, sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help="Stable key used by content packs, e.g. PREP, SUBMIT, WAIT.")
    sequence = fields.Integer(default=10)
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    kind = fields.Selection(
        [
            ("prepare", "Preparing"),
            ("submit", "Submitting"),
            ("with_body", "With The Body"),
            ("decide", "Being Decided"),
            ("close", "Closing"),
        ],
        default="prepare",
        required=True,
        help="The shape of the phase, so the rail can colour it without reading "
        "its name. Not the name of anything in the world - that is what the "
        "phase's own name is for.",
    )
    step_ids = fields.One2many("legal.procedure.step", "phase_id", string="Steps")
    step_count = fields.Integer(compute="_compute_step_count")
    colour = fields.Integer(string="Colour")

    _code_type_uniq = models.Constraint(
        "UNIQUE(code, procedure_type_id)",
        "A phase code must be unique within its procedure.",
    )

    def _compute_step_count(self):
        for phase in self:
            phase.step_count = len(phase.step_ids)

    @api.depends("name", "procedure_type_id")
    def _compute_display_name(self):
        for phase in self:
            phase.display_name = phase.name or ""

    @api.constrains("step_ids")
    def _check_steps_belong_to_procedure(self):
        """A phase may only hold steps of its own procedure.

        Left unchecked, a step dragged onto the wrong phase makes the rail show a
        file as being in a phase that its procedure does not have, and the
        segment count stops matching the segments drawn.
        """
        for phase in self:
            stray = phase.step_ids.filtered(
                lambda step: step.procedure_type_id != phase.procedure_type_id
            )
            if stray:
                raise ValidationError(
                    _(
                        "Step “%(step)s” belongs to a different procedure, so it cannot sit "
                        "in the phase “%(phase)s”.",
                        step=stray[0].display_name,
                        phase=phase.name,
                    )
                )
