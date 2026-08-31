from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .legal_constants import OUTCOME_SELECTION, STEP_KIND_SELECTION


class LegalProcedureStep(models.Model):
    """The state machine, as data - الخطوة.

    ``legal.case.step_id`` is a foreign key into this table and there is no
    Selection state field anywhere on the case. That single decision is what
    makes a new ministry a configuration job: the states of a procedure are rows
    a consultant types, tracked by ``mail.tracking.duration.mixin`` so the time
    spent in each is measured for free, and grouped in the kanban by
    ``group_expand`` so an empty step still draws its column.

    **Every step names a body, and the field is required.** It is tempting to
    let an internal preparation step have no counter, but in practice a step
    with no body is always hiding one: "prepare the file" means the legal
    department, "get the manager's signature" means the company, and "pay" means
    a bank. Forcing the answer is what lets the desk panel, the SLA calendar and
    the "who are we waiting for" column work with no special cases.

    **The four desk strings** are the reason a new body can get a working desk
    panel with no JavaScript at all. ``desk_title``, ``desk_hint``,
    ``desk_empty`` and ``desk_note_template`` are what the panel prints, so
    adding the Directorate of Civil Defence to the product is four sentences and
    a step row rather than a component.
    """

    _name = "legal.procedure.step"
    _description = "Procedure Step"
    _order = "procedure_type_id, sequence, id"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(
        help="Stable key, snapshotted onto the immutable log so the trail survives "
        "the step being renamed or deleted.",
    )
    sequence = fields.Integer(
        default=10,
        help="Order of the walk. A strictly linear procedure needs nothing else: "
        "the engine synthesises each advance from this ordering.",
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="cascade",
        index=True,
    )
    phase_id = fields.Many2one(
        "legal.procedure.phase",
        string="Phase",
        ondelete="set null",
        index=True,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
    )
    gov_body_id = fields.Many2one(
        "legal.gov.body",
        string="Body",
        required=True,
        ondelete="restrict",
        index=True,
        help="Which counter this step happens at. Required: a step with no body "
        "is hiding one, and every clock in the product counts in the body's own "
        "working days.",
    )
    kind = fields.Selection(
        STEP_KIND_SELECTION,
        default="internal",
        required=True,
        index=True,
        help="Is the file on our desk or theirs? Stored on the case as well, "
        "because it is the question a legal department is asked hourly and no "
        "board should have to join a configuration table to answer it.",
    )
    outcome = fields.Selection(
        OUTCOME_SELECTION,
        default="none",
        required=True,
        help="What arriving at this step means. Iraqi bodies return files and "
        "grant conditionally far more often than they refuse, so a system with "
        "only granted and rejected forces a clerk to record a return as a "
        "rejection - which then poisons every statistic the department is judged on.",
    )
    responsible_group_id = fields.Many2one(
        "res.groups",
        string="Owned By",
        ondelete="restrict",
        help="Which desk owes the next move while the file sits here.",
    )

    # ------------------------------------------------------------------
    # Clocks
    # ------------------------------------------------------------------
    target_days = fields.Integer(
        string="Target (working days)",
        default=0,
        help="Counted in the body's own calendar, so a target does not cry wolf "
        "every Friday and Saturday.",
    )
    rotting_threshold_days = fields.Integer(
        string="Goes Stale After (days)",
        default=0,
        help="Past this, the file is not merely late - it has been forgotten. The "
        "distinction matters because the remedy differs: a late file needs "
        "chasing, a forgotten one needs re-opening.",
    )

    # ------------------------------------------------------------------
    # What the clerk sees and does here
    # ------------------------------------------------------------------
    clerk_instruction = fields.Html(
        translate=True,
        help="Shown above the capture fields in the step dialog. This is where "
        "'take four photocopies and ask for Abu Ahmed on the second floor' lives.",
    )
    capture_field_ids = fields.One2many(
        "legal.procedure.field", "step_id", string="Capture Fields", copy=True
    )
    check_ids = fields.One2many(
        "legal.procedure.step.check", "step_id", string="Counter Walk", copy=True
    )
    check_count = fields.Integer(compute="_compute_check_count")
    requirement_ids = fields.One2many(
        "legal.doc.requirement", "step_id", string="Documents Demanded Here"
    )
    fee_rule_ids = fields.One2many("legal.fee.rule", "step_id", string="Fees Due Here")

    requires_letter = fields.Boolean(
        string="Needs An Official Letter",
        help="A step that cannot be taken without a signed and stamped كتاب رسمي.",
    )
    auto_next = fields.Boolean(
        string="Advance Automatically",
        default=True,
        help="When set, the engine synthesises the move to the next step in order, "
        "so a linear procedure needs no transition rows at all. Clear it on a step "
        "whose only ways out are explicit branches.",
    )
    return_to_step_id = fields.Many2one(
        "legal.procedure.step",
        string="Returns To",
        ondelete="set null",
        domain="[('procedure_type_id', '=', procedure_type_id), ('id', '!=', id)]",
        help="Where a file goes when this step sends it back for correction. "
        "Usually the step that prepared what the counter rejected.",
    )

    # ------------------------------------------------------------------
    # The four desk strings - a working panel with zero JavaScript
    # ------------------------------------------------------------------
    desk_title = fields.Char(
        translate=True,
        help="The heading of the desk panel: what the person sitting here is doing.",
    )
    desk_hint = fields.Char(
        translate=True,
        help="One line under the heading telling them what good looks like.",
    )
    desk_empty = fields.Char(
        translate=True,
        help="What the panel says when there is nothing here - the most read "
        "string in any queue, and the one most often left as 'No records'.",
    )
    desk_note_template = fields.Char(
        translate=True,
        help="The sentence pre-filled into the contact note when a call is logged "
        "from this step, e.g. 'راجعنا الشعبة وأفادوا بأن المعاملة قيد التدقيق'.",
    )

    colour = fields.Integer(string="Colour")
    fold = fields.Boolean(
        string="Folded In Kanban",
        help="Terminal steps are folded so a board of live files is not half "
        "closed columns.",
    )
    active = fields.Boolean(default=True)

    _code_type_uniq = models.Constraint(
        "UNIQUE(code, procedure_type_id)",
        "A step code must be unique within its procedure.",
    )

    def _compute_check_count(self):
        for step in self:
            step.check_count = len(step.check_ids)

    @api.depends("name", "procedure_type_id")
    def _compute_display_name(self):
        for step in self:
            step.display_name = step.name or ""

    @api.constrains("phase_id", "return_to_step_id")
    def _check_same_procedure(self):
        """Nothing on a step may point outside its own procedure.

        A phase or a return target from another procedure sends a live file into
        a state machine it does not belong to, and every count on both procedures
        is then wrong in a way no report will flag.
        """
        for step in self:
            if step.phase_id and step.phase_id.procedure_type_id != step.procedure_type_id:
                raise ValidationError(
                    _(
                        "The phase “%(phase)s” belongs to a different procedure than the "
                        "step “%(step)s”.",
                        phase=step.phase_id.name,
                        step=step.name,
                    )
                )
            if (
                step.return_to_step_id
                and step.return_to_step_id.procedure_type_id != step.procedure_type_id
            ):
                raise ValidationError(
                    _(
                        "“%(step)s” cannot return a file to “%(target)s”, which belongs to "
                        "another procedure.",
                        step=step.name,
                        target=step.return_to_step_id.name,
                    )
                )

    @api.constrains("kind", "outcome")
    def _check_outcome_is_terminal(self):
        """Only a terminal step may declare an outcome.

        An outcome on a step in the middle of the walk would make ``legal.case``
        report a file as granted while it is still queueing at a counter, and the
        related stored column on the case makes that lie searchable.
        """
        for step in self:
            if step.outcome != "none" and step.kind != "terminal":
                raise ValidationError(
                    _(
                        "“%s” is not a closing step, so it cannot declare an outcome. A file "
                        "in the middle of the walk has not been granted or refused anything yet.",
                        step.name,
                    )
                )


class LegalProcedureStepCheck(models.Model):
    """One counter, one stamp, one window - الختم / التأييد.

    A براءة ذمة walk is twenty-two counters inside what the department calls a
    single step, and a civil-defence كشف موقعي is one visit with a fixed list of
    things the inspector signs off. Modelling those as twenty-two steps would
    bury the shape of the procedure; modelling them as free text would make
    "which counter are we stuck at" unanswerable.

    So they are ordered rows under one step, each naming the stamp it produces
    and the window that produces it. That is what turns "the file is at the
    Tax Commission" into "the file is at window 7 waiting for ختم الحجوزات
    الضريبية, and the man who stamps it is back on Sunday".
    """

    _name = "legal.procedure.step.check"
    _description = "Counter Check"
    _order = "step_id, sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Step",
        required=True,
        ondelete="cascade",
        index=True,
    )
    check_kind = fields.Selection(
        [
            ("stamp", "Stamp / Endorsement"),
            ("pay_fee", "Payment"),
            ("inspection", "Inspection"),
            ("collect", "Collection"),
            ("verify", "Verification"),
        ],
        default="stamp",
        required=True,
        help="The shape of what happens at the window, so the desk row can show "
        "the right control - a stamp is ticked, a payment needs a receipt number.",
    )
    produces_stamp = fields.Char(
        string="Stamp Produced",
        translate=True,
        help="The endorsement itself, in the words the counter uses: "
        "ختم الحجوزات الضريبية، تأييد عدم الممانعة.",
    )
    counter = fields.Char(
        string="Window",
        translate=True,
        help="Which window, which floor. The single most useful string in the "
        "product on the morning of the walk.",
    )
    note = fields.Text(translate=True)
    is_required = fields.Boolean(
        default=True,
        help="An optional check is one the counter sometimes waives. It still "
        "belongs on the list so the clerk knows to ask.",
    )
    active = fields.Boolean(default=True)

    @api.depends("name", "counter")
    def _compute_display_name(self):
        for check in self:
            check.display_name = (
                _("%(name)s (%(counter)s)", name=check.name, counter=check.counter)
                if check.counter
                else (check.name or "")
            )
