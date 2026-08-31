import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .legal_constants import RESERVED_FIELD_CODES, reserved_code_message

CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class LegalProcedureField(models.Model):
    """A fact captured at one step, and nowhere else - حقول الخطوة.

    Iraqi counters ask for one-off facts constantly: the plot number the civil
    defence inspector wants, the name of the officer who took the file, the
    colour of the folder the archive insists on. Adding a column to
    ``legal.case`` for each of those would make the model unreadable within a
    year, so they are rows here and their values live in a per-case payload.

    **The reserved-word constraint is the important half of this model.** A
    capture field is the right home for a fact that matters at one counter and
    nowhere else. It is exactly the wrong home for a fact the whole department
    reports on - a fee, a receipt number, an expiry date, the number we quoted
    in our letter. Those recur at every body, they are what a manager asks for
    in aggregate, and buried in a payload no ``_read_group`` can ever reach
    them. The engine therefore refuses the name and says which real column the
    configurer wanted, because a configurer who is told 'that name is taken'
    just types ``fee_amount`` and the problem is worse.
    """

    _name = "legal.procedure.field"
    _description = "Step Capture Field"
    _order = "step_id, sequence, id"

    label = fields.Char(
        required=True,
        translate=True,
        help="What the clerk is asked, in their own words.",
    )
    code = fields.Char(
        required=True,
        help="Stable key the value is stored under. Lower case, no spaces.",
    )
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Step",
        required=True,
        ondelete="cascade",
        index=True,
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        related="step_id.procedure_type_id",
        store=True,
        index=True,
    )
    field_type = fields.Selection(
        [
            ("char", "Text"),
            ("text", "Long Text"),
            ("integer", "Whole Number"),
            ("float", "Number"),
            ("date", "Date"),
            ("datetime", "Date & Time"),
            ("boolean", "Yes / No"),
            ("selection", "Choice"),
        ],
        string="Type",
        default="char",
        required=True,
    )
    selection_values = fields.Char(
        help="Comma separated choices, used only when the type is a choice.",
    )
    required = fields.Boolean(
        help="A required capture field blocks the advance until it is answered, "
        "the same way a missing document does.",
    )
    placeholder = fields.Char(
        translate=True,
        help="An example of a good answer. Worth more than any help text on a "
        "form somebody is filling in at a counter.",
    )
    help_text = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _code_step_uniq = models.Constraint(
        "UNIQUE(code, step_id)",
        "A capture field code must be unique within its step.",
    )

    @api.depends("label", "step_id")
    def _compute_display_name(self):
        for capture in self:
            capture.display_name = capture.label or capture.code or ""

    @api.constrains("code")
    def _check_code_is_not_reserved(self):
        """Refuse a name that hides a department-wide fact inside one step."""
        for capture in self:
            code = (capture.code or "").strip().lower()
            if not CODE_PATTERN.match(code):
                raise ValidationError(
                    _(
                        "“%s” is not a usable key. Use lower-case letters, digits and "
                        "underscores, starting with a letter.",
                        capture.code,
                    )
                )
            if code in RESERVED_FIELD_CODES:
                raise ValidationError(reserved_code_message(self.env, code))

    @api.constrains("field_type", "selection_values")
    def _check_selection_values(self):
        for capture in self:
            if capture.field_type == "selection" and not (capture.selection_values or "").strip():
                raise ValidationError(
                    _("“%s” is a choice field, so it needs some choices.", capture.label)
                )

    @api.onchange("label")
    def _onchange_label_suggests_code(self):
        """Offer a key so the common case needs no thought, without ever
        overwriting one the configurer has already typed."""
        for capture in self:
            if capture.code or not capture.label:
                continue
            suggestion = re.sub(r"[^a-z0-9]+", "_", capture.label.lower()).strip("_")
            if suggestion and CODE_PATTERN.match(suggestion):
                capture.code = suggestion

    def _selection_options(self):
        self.ensure_one()
        return [value.strip() for value in (self.selection_values or "").split(",") if value.strip()]
