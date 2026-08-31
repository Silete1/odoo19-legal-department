import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.legal_core.models.legal_engine import engine_guard, in_engine

from .legal_constants import SLA_STATE_SELECTION, WORKFLOW_OWNED_FIELDS

_logger = logging.getLogger(__name__)


class LegalCase(models.Model):
    """المعاملة - the file, and the only transactional model in the engine.

    There is **no Selection state field anywhere on this model**. ``step_id`` is
    a foreign key into ``legal.procedure.step``, tracked, grouped with
    ``group_expand`` so an empty step still draws its kanban column, and fed to
    ``mail.tracking.duration.mixin`` so the time spent in each step is measured
    without a single extra timestamp. That is the whole architecture in one
    sentence: the states of an Iraqi procedure are rows a consultant types, not
    a Python enum a vendor ships.

    Three consequences are worth stating, because each of them is a decision
    somebody will otherwise try to undo.

    **The advance is synthesised.** A strictly linear procedure - and most are,
    right up until something goes wrong - needs zero transition rows: the engine
    moves to the next step by ordering. Transitions exist for the moves that
    carry real information, and a consultant who has to type fifty rows of
    "from 3 to 4" will eventually type one of them wrong.

    **Returns increment a round; they never delete anything.** A file sent back
    for correction opens round 2, the service-level clock pauses, and round 1's
    approvals are marked superseded rather than removed. An Iraqi file is
    routinely returned twice before it is granted, and a system that erases the
    earlier rounds cannot answer the only question that matters afterwards: what
    did they object to, and did we fix it.

    **``step_id`` is engine-owned and the write override says so out loud.**
    ``readonly=True`` is a client hint; it stops nothing arriving over RPC, and a
    clickable statusbar is a way to teleport a file past its own approvals. So
    :meth:`write` refuses the workflow-owned fields outright unless the engine
    itself is the caller.
    """

    _name = "legal.case"
    _description = "Legal Case"
    # ``mail.thread`` is deliberately not named here: ``mail.tracking.duration.mixin``
    # already inherits it, and listing it first makes the linearisation
    # impossible - the mixin's own base would have to come before it. This is the
    # order crm.lead and project.task use, for the same reason.
    _inherit = ["mail.activity.mixin", "mail.tracking.duration.mixin"]
    _order = "priority desc, sla_due_on asc, id desc"
    _rec_names_search = ["name", "reference_index"]
    _track_duration_field = "step_id"

    name = fields.Char(
        string="File Number",
        required=True,
        copy=False,
        readonly=True,
        index="trigram",
        default=lambda self: _("New"),
        help="Taken from the procedure's own sequence, or typed by the clerk where "
        "the body dictates the number.",
    )
    procedure_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Procedure",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
    )
    procedure_version = fields.Char(
        readonly=True,
        copy=False,
        help="The version the file opened under, snapshotted. A circular that "
        "changes the procedure next week must not silently change what this file "
        "was required to do.",
    )
    subject = fields.Char(
        string="Subject (الموضوع)",
        translate=True,
        help="What the file is about, in the words that will print on the letter.",
    )

    # ------------------------------------------------------------------
    # Where the file is
    # ------------------------------------------------------------------
    step_id = fields.Many2one(
        "legal.procedure.step",
        string="Step",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
        group_expand="_read_group_step_ids",
        compute="_compute_step_id",
        store=True,
        readonly=False,
        precompute=True,
        copy=False,
        domain="[('procedure_type_id', '=', procedure_type_id)]",
    )
    phase_id = fields.Many2one(
        "legal.procedure.phase",
        string="Phase",
        related="step_id.phase_id",
        store=True,
        index=True,
    )
    kind = fields.Selection(
        string="Sitting With",
        related="step_id.kind",
        store=True,
        index=True,
        help="On our desk or theirs. Stored and indexed because it is the question "
        "a legal department is asked hourly, and no board should have to join a "
        "configuration table to answer it.",
    )
    outcome = fields.Selection(
        related="step_id.outcome",
        store=True,
        index=True,
        tracking=True,
    )
    is_closed = fields.Boolean(
        compute="_compute_is_closed", store=True, index=True, string="Closed"
    )
    round = fields.Integer(
        string="Round",
        default=1,
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        help="Incremented every time the body sends the file back. Round 2 is not "
        "a failure to record - it is the norm, and it is what the correction is "
        "measured against.",
    )

    # ------------------------------------------------------------------
    # Who and where
    # ------------------------------------------------------------------
    body_id = fields.Many2one(
        "legal.gov.body",
        string="Body",
        compute="_compute_body_id",
        store=True,
        readonly=False,
        precompute=True,
        index=True,
        ondelete="restrict",
        help="The body the file belongs to. Read by the record rule that scopes a "
        "follow-up officer to the counters they actually deal with.",
    )
    current_body_id = fields.Many2one(
        "legal.gov.body",
        string="At Counter",
        related="step_id.gov_body_id",
        store=True,
        index=True,
        help="Where the file physically is right now, which on a long walk is "
        "rarely the same body the procedure belongs to.",
    )
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction",
        string="Jurisdiction",
        related="procedure_type_id.jurisdiction_id",
        store=True,
        index=True,
    )
    entity_id = fields.Many2one(
        "legal.entity",
        string="For",
        required=True,
        ondelete="restrict",
        index=True,
        default=lambda self: self.env.company.legal_entity_id,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsible",
        tracking=True,
        index=True,
        default=lambda self: self.env.user,
    )
    runner_partner_id = fields.Many2one(
        "res.partner",
        string="Walking It Today",
        index=True,
        help="Who is carrying this file around the ministry today. Deliberately "
        "not the same question as who signed a particular letter, and not the "
        "same as who is responsible for the outcome: on the morning of a "
        "twenty-two counter walk it is the only question anybody is asking.",
    )
    pending_group_id = fields.Many2one(
        "res.groups",
        string="Waiting On",
        related="step_id.responsible_group_id",
        store=True,
        index=True,
    )
    poa_id = fields.Many2one(
        "legal.poa",
        string="Power Of Attorney",
        ondelete="restrict",
        index=True,
        help="The وكالة the runner is presenting. The counter checks the name on "
        "it against the card in their hand, so a file with the wrong one is a "
        "wasted morning.",
    )

    # ------------------------------------------------------------------
    # The has_* matrix, read through onto the file
    # ------------------------------------------------------------------
    # These four exist so that ONE form view serves every procedure. The matrix
    # lives on the type - required / optional / not used - and the view reads it
    # through the file to decide what to show and what to insist on. That is the
    # approval.category idiom: unglamorous, but a custom renderer per procedure
    # would cost a developer every time a body wants one more field, and this
    # costs four related columns.
    subject_usage = fields.Selection(
        string="People Are", related="procedure_type_id.has_subjects", readonly=True
    )
    fee_usage = fields.Selection(
        string="Fees Are", related="procedure_type_id.has_fee", readonly=True
    )
    poa_usage = fields.Selection(
        string="The وكالة Is", related="procedure_type_id.has_poa", readonly=True
    )
    letter_usage = fields.Selection(
        string="A Letter Is", related="procedure_type_id.has_outgoing_letter", readonly=True
    )
    step_instruction = fields.Html(
        related="step_id.clerk_instruction",
        readonly=True,
        string="What To Do Here",
    )

    # ------------------------------------------------------------------
    # Contents
    # ------------------------------------------------------------------
    subject_ids = fields.One2many(
        "legal.case.subject", "case_id", string="People", copy=True
    )
    subject_count = fields.Integer(compute="_compute_counts")
    document_ids = fields.One2many(
        "legal.case.document", "case_id", string="Checklist", copy=False
    )
    check_ids = fields.One2many(
        "legal.case.step.check", "case_id", string="Counter Walk", copy=False
    )
    fee_ids = fields.One2many("legal.fee", "case_id", string="Fees", copy=False)
    log_ids = fields.One2many("legal.action.log", "case_id", string="Trail", copy=False)
    escalation_ids = fields.One2many(
        "legal.sla.escalation", "case_id", string="Escalations", copy=False
    )
    capture_values = fields.Json(
        string="Captured Facts",
        copy=False,
        help="The per-step facts a configurer defined. Deliberately opaque: "
        "anything the department reports on in aggregate has a real column of its "
        "own, and the reserved-word check on the capture field enforces that.",
    )
    result_document_id = fields.Many2one(
        "legal.document",
        string="Produced",
        ondelete="set null",
        copy=False,
        index=True,
        help="What the procedure produced, filed in the company's permanent "
        "register rather than attached to this file alone.",
    )
    parent_case_id = fields.Many2one(
        "legal.case",
        string="Part Of",
        ondelete="set null",
        index=True,
        help="A prerequisite opened to unblock another file - the tax clearance a "
        "Registrar filing is waiting on.",
    )
    child_case_ids = fields.One2many(
        "legal.case", "parent_case_id", string="Prerequisites"
    )
    child_case_count = fields.Integer(compute="_compute_counts")
    document_count = fields.Integer(compute="_compute_counts")
    fee_total = fields.Monetary(compute="_compute_counts", currency_field="currency_id")
    fee_unpaid = fields.Monetary(compute="_compute_counts", currency_field="currency_id")
    contract_value = fields.Monetary(
        currency_field="currency_id",
        help="Used by percentage fee rules - a tender guarantee or a stamp duty on "
        "a contract value.",
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.ref("base.IQD", raise_if_not_found=False)
        or self.env.company.currency_id,
        required=True,
    )

    # ------------------------------------------------------------------
    # Clocks
    # ------------------------------------------------------------------
    date_open = fields.Datetime(
        string="Opened", default=fields.Datetime.now, required=True, index=True, copy=False
    )
    date_closed = fields.Datetime(string="Closed On", readonly=True, copy=False, index=True)
    date_deadline = fields.Date(
        string="Statutory Deadline",
        index=True,
        tracking=True,
        help="The date the law - not the counter - insists on. A tax return is due "
        "on a date whether or not the file is ready.",
    )
    stage_entered_on = fields.Datetime(
        string="On This Step Since",
        compute="_compute_stage_entered_on",
        store=True,
        index=True,
        readonly=True,
        help="Read off the immutable log rather than written by the workflow, so "
        "it can never drift away from what actually happened.",
    )
    #: Odoo's rotting feature is hard-wired to this exact field name: the
    #: duration mixin's ``_compute_rotting`` depends on it and refuses to load
    #: without it once the tracked model carries ``rotting_threshold_days``,
    #: which ``legal.procedure.step`` does. Rather than rename the honest field,
    #: this is a stored alias of it - so the kanban's rotting badge and the form's
    #: ``rotting_statusbar_duration`` widget work with no further wiring, and
    #: "how long has this been sitting here" still has exactly one answer.
    date_last_stage_update = fields.Datetime(
        string="Last Step Change",
        related="stage_entered_on",
        store=True,
        index=True,
    )
    sla_paused = fields.Boolean(
        readonly=True,
        copy=False,
        help="Set while a file is back with us for correction. The body cannot be "
        "held to a target during a round it did not cause.",
    )
    sla_due_on = fields.Datetime(
        string="Due On",
        compute="_compute_sla_deadlines",
        store=True,
        index=True,
        help="Deliberately does not read the clock, so it can be sorted on. The "
        "verdict is computed live; only the deadline is stored.",
    )
    sla_warn_on = fields.Datetime(compute="_compute_sla_deadlines", store=True)
    sla_escalate_on = fields.Datetime(compute="_compute_sla_deadlines", store=True)
    sla_state = fields.Selection(
        SLA_STATE_SELECTION,
        string="Service Level",
        compute="_compute_sla_state",
        search="_search_sla_state",
        help="Computed on read, never stored: a stored verdict is stale by the "
        "next midnight, and a badge that lies for a day is worse than no badge.",
    )
    our_days = fields.Float(
        string="On Our Desk (days)",
        compute="_compute_desk_days",
        help="How much of the elapsed time this department is answerable for. The "
        "only honest way to argue with a ministry about delay.",
    )
    their_days = fields.Float(string="With The Body (days)", compute="_compute_desk_days")

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------
    available_transition_ids = fields.Many2many(
        "legal.procedure.transition",
        string="Moves Available",
        compute="_compute_available_transitions",
        compute_sudo=False,
        depends_context=("uid",),
        help="Only the moves this user may actually make. Computed without sudo "
        "and per user on purpose: a clerk shown a button they cannot press has "
        "been told the system is broken.",
    )
    ready_to_advance = fields.Boolean(
        compute="_compute_readiness",
        store=True,
        index=True,
        help="Drives the enabled half of the button twins. The greyed twin is "
        "still shown, because a button that vanishes teaches nobody why.",
    )
    blocker_count = fields.Integer(compute="_compute_readiness", store=True)
    # Stored, because a manager filters and groups on "what is blocked" and a
    # search cannot run against a field computed on read. The *sentence* below is
    # deliberately NOT stored: it is composed with the reader's language, and a
    # stored translated string would be whichever language happened to compute it
    # first in that worker.
    blocker_summary = fields.Char(
        compute="_compute_blocker_summary",
        depends_context=("lang",),
        help="Why the file cannot move, in the words the clerk needs at the counter.",
    )

    # ------------------------------------------------------------------
    # Finding it again
    # ------------------------------------------------------------------
    reference_index = fields.Char(
        compute="_compute_reference_index",
        store=True,
        index="trigram",
        help="Every number this file is known by, in one searchable string. A "
        "clerk asked about “٤٥٦٧٢” does not know whether that is our outgoing "
        "number, their incoming number, the deed number or the receipt.",
    )

    # ------------------------------------------------------------------
    # Recurring obligations
    # ------------------------------------------------------------------
    schedule_id = fields.Many2one(
        "legal.obligation.schedule",
        string="Obligation",
        ondelete="set null",
        index=True,
    )
    period_key = fields.Char(
        index=True,
        copy=False,
        help="Which period this file discharges - 2026, 2026-03. Carried from the "
        "obligation instance so the two can never be matched up by date arithmetic.",
    )
    obligation_instance_id = fields.Many2one(
        "legal.obligation.instance", string="Period", ondelete="set null", index=True
    )

    confidential = fields.Boolean(
        tracking=True,
        help="Restricts the file to the legal manager and the officers of its "
        "body. Used for anything privileged, and for personal papers.",
    )
    priority = fields.Selection(
        [("0", "Normal"), ("1", "Urgent"), ("2", "Critical")],
        default="0",
        index=True,
        tracking=True,
    )
    colour = fields.Integer(string="Colour")
    note = fields.Html(translate=True)
    active = fields.Boolean(default=True)

    # ==================================================================
    # Kanban
    # ==================================================================
    def _read_group_step_ids(self, steps, domain):
        """Draw every step of the procedure, including the empty ones.

        A board that only shows the steps that happen to be occupied hides the
        shape of the procedure, and the column a clerk is looking for is
        precisely the one with nothing in it yet.
        """
        procedure_id = self.env.context.get("default_procedure_type_id")
        if not procedure_id:
            for condition in domain:
                if (
                    isinstance(condition, (list, tuple))
                    and len(condition) == 3
                    and condition[0] == "procedure_type_id"
                    and condition[1] in ("=", "in")
                ):
                    value = condition[2]
                    procedure_id = value[0] if isinstance(value, (list, tuple)) else value
                    break
        if not procedure_id:
            return steps
        return self.env["legal.procedure.step"].search(
            [("procedure_type_id", "=", procedure_id)],
            order="sequence, id",
        )

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends("procedure_type_id")
    def _compute_step_id(self):
        """Put a new file on the first step of its procedure.

        A stored editable compute rather than an onchange, so a file created over
        RPC - by the obligation cron, by an import, by a prerequisite being
        opened from a blocked checklist line - lands on the right step too.
        """
        for case in self:
            if case.step_id and case.step_id.procedure_type_id == case.procedure_type_id:
                continue
            case.step_id = case.procedure_type_id._first_step()

    @api.depends("procedure_type_id")
    def _compute_body_id(self):
        for case in self:
            if not case.body_id or case.body_id != case.procedure_type_id.body_id:
                case.body_id = case.procedure_type_id.body_id

    @api.depends("step_id.kind")
    def _compute_is_closed(self):
        for case in self:
            case.is_closed = case.step_id.kind == "terminal"

    @api.depends("log_ids.logged_on", "log_ids.closes_step", "date_open")
    def _compute_stage_entered_on(self):
        """When the file arrived where it is now, read off the trail.

        A stored computed field rather than a timestamp the workflow methods
        write by hand: the log is the single source of truth, the ORM keeps this
        column in step with it, it can never drift, and an upgrade backfills
        every historical file for free.

        Entries that record something happening while the file stays put - a fee
        paid, a note taken, a document uploaded - are not closures and correctly
        leave the clock alone.
        """
        for case in self:
            closures = case.log_ids.filtered("closes_step").sorted("logged_on")
            case.stage_entered_on = closures[-1].logged_on if closures else case.date_open

    @api.depends(
        "step_id",
        "stage_entered_on",
        "procedure_type_id",
        "company_id",
        "sla_paused",
    )
    def _compute_sla_deadlines(self):
        """Plan the deadline through the *body's* calendar, not the company's.

        A target counted in calendar days cries wolf every Friday and goes
        berserk over Eid al-Adha. Counting in the working days of the counter the
        file is actually sitting at is the difference between a chase list people
        act on and one they learn to close without reading.
        """
        rule_model = self.env["legal.sla.rule"]
        for case in self:
            case.sla_due_on = False
            case.sla_warn_on = False
            case.sla_escalate_on = False
            if not case.step_id or case.step_id.kind == "terminal" or case.sla_paused:
                continue
            rule = rule_model._rule_for(case.procedure_type_id, case.step_id, case.company_id)
            target = rule.target_days if rule else case.step_id.target_days
            if not target:
                continue
            start = case.stage_entered_on or case.date_open or fields.Datetime.now()
            body = case.step_id.gov_body_id or case.body_id
            due = body._plan_days(target, start) if body else start + timedelta(days=target)
            if not due:
                continue
            case.sla_due_on = due
            warning = rule.warning_days if rule else 0
            escalation = rule.escalation_days if rule else 0
            case.sla_warn_on = (
                body._plan_days(max(target - warning, 0) or 1, start)
                if (body and warning)
                else due
            )
            case.sla_escalate_on = (
                body._plan_days(escalation, due)
                if (body and escalation)
                else due
            )

    @api.depends(
        "sla_due_on",
        "sla_warn_on",
        "sla_escalate_on",
        "sla_paused",
        "step_id",
        "escalation_ids.is_open",
    )
    def _compute_sla_state(self):
        now = fields.Datetime.now()
        for case in self:
            if case.sla_paused:
                case.sla_state = "paused"
            elif not case.sla_due_on:
                case.sla_state = "not_applicable"
            elif case.escalation_ids.filtered("is_open"):
                case.sla_state = "escalated"
            elif now >= case.sla_due_on:
                case.sla_state = "overdue"
            elif case.sla_warn_on and now >= case.sla_warn_on:
                case.sla_state = "warning"
            else:
                case.sla_state = "on_track"

    def _search_sla_state(self, operator, value):
        """Let a board filter on the verdict without storing it.

        Every branch below translates into a bound on the *stored* deadline
        columns, so the filter stays on an index and cannot disagree with the
        badge the row draws.
        """
        if operator not in ("in", "not in", "=", "!="):
            raise UserError(_("A service level can only be filtered by equality."))
        # Odoo 19 normalises ``=`` into ``in`` and hands the value over as an
        # OrderedSet, not a list. Treating anything iterable-but-not-a-string as
        # a collection is the only version of this that survives both the
        # hand-written domain in a filter and the optimised one from the client.
        if isinstance(value, str) or not hasattr(value, "__iter__"):
            values = [value]
        else:
            values = list(value)
        now = fields.Datetime.now()
        domains = {
            "paused": [("sla_paused", "=", True)],
            "not_applicable": [("sla_paused", "=", False), ("sla_due_on", "=", False)],
            "escalated": [("escalation_ids", "any", [("is_open", "=", True)])],
            "overdue": [
                ("sla_paused", "=", False),
                ("sla_due_on", "<=", now),
                ("escalation_ids", "not any", [("is_open", "=", True)]),
            ],
            "warning": [
                ("sla_paused", "=", False),
                ("sla_warn_on", "<=", now),
                ("sla_due_on", ">", now),
            ],
            "on_track": [
                ("sla_paused", "=", False),
                ("sla_due_on", ">", now),
                ("sla_warn_on", ">", now),
            ],
        }
        selected = []
        for state in values:
            if state in domains:
                selected.append(domains[state])
        if not selected:
            return [("id", "=", False)]
        domain = selected[0]
        for extra in selected[1:]:
            domain = ["|"] + domain + extra
        if operator in ("not in", "!="):
            return ["!"] + domain
        return domain

    def _compute_desk_days(self):
        """Split the elapsed time into ours and theirs, from the trail.

        Computed from the immutable log rather than from tracking values,
        because the log is what the department will be asked to produce when it
        argues with a ministry about who caused the delay - and the argument is
        only winnable with a number.
        """
        now = fields.Datetime.now()
        for case in self:
            ours = theirs = 0.0
            closures = case.log_ids.filtered("closes_step").sorted("logged_on")
            for index, entry in enumerate(closures):
                step = entry.to_step_id
                started = entry.logged_on
                ended = closures[index + 1].logged_on if index + 1 < len(closures) else now
                if not (step and started and ended):
                    continue
                elapsed = (ended - started).total_seconds() / 86400.0
                if step.kind == "at_body":
                    theirs += elapsed
                elif step.kind == "internal":
                    ours += elapsed
            case.our_days = round(ours, 2)
            case.their_days = round(theirs, 2)

    @api.depends(
        "name",
        "subject",
        "subject_ids.document_number",
        "result_document_id.number",
        "poa_id.number",
        "fee_ids.receipt_number",
    )
    def _compute_reference_index(self):
        """Every number the file is known by, in one searchable string.

        A clerk handed a scrap of paper with "٤٥٦٧٢" on it does not know whether
        that is our outgoing number, their incoming number, the deed number or a
        receipt - and asking them to pick the right search field first is asking
        them to know the answer before they look for it.
        """
        for case in self:
            case.reference_index = " ".join(
                part for part in case._reference_index_parts() if part
            )

    def _reference_index_parts(self):
        """The parts of the search index.

        A hook rather than an inline list, because ``legal_correspondence`` adds
        the outgoing and incoming register numbers to it and neither module
        should have to know the other's field names.
        """
        self.ensure_one()
        parts = [self.name or "", self.subject or ""]
        parts += [subject.document_number or "" for subject in self.subject_ids]
        parts.append(self.result_document_id.number or "")
        parts.append(self.poa_id.number or "")
        parts += [fee.receipt_number or "" for fee in self.fee_ids]
        return parts

    @api.depends(
        "subject_ids",
        "document_ids",
        "child_case_ids",
        "fee_ids.amount",
        "fee_ids.state",
    )
    def _compute_counts(self):
        for case in self:
            case.subject_count = len(case.subject_ids)
            case.document_count = len(case.document_ids)
            case.child_case_count = len(case.child_case_ids)
            case.fee_total = sum(case.fee_ids.mapped("amount"))
            case.fee_unpaid = sum(
                fee.amount for fee in case.fee_ids if fee.state != "paid"
            )

    @api.depends_context("uid")
    @api.depends("step_id", "procedure_type_id")
    def _compute_available_transitions(self):
        """Only the moves this user may actually make.

        Computed without ``sudo`` and per user on purpose. A clerk shown a button
        they cannot press has been told the software is broken, and will stop
        trusting the buttons that do work; a clerk shown only their own moves has
        been told what their job is.
        """
        user_groups = self.env.user.all_group_ids
        for case in self:
            transitions = case.procedure_type_id.transition_ids.filtered(
                lambda transition: transition.from_step_id == case.step_id
                and transition.active
            )
            allowed = transitions.filtered(
                lambda transition: (
                    not transition.group_ids or (transition.group_ids & user_groups)
                )
                and transition._matches(case)
            )
            case.available_transition_ids = allowed.sorted("sequence")

    @api.depends(
        "step_id",
        "document_ids.line_status",
        "document_ids.is_blocking",
        "fee_ids.state",
        "check_ids.done",
        "poa_id",
        "capture_values",
    )
    def _compute_readiness(self):
        for case in self:
            blockers = case._blockers()
            case.blocker_count = len(blockers)
            case.ready_to_advance = not blockers

    @api.depends(
        "step_id",
        "document_ids.line_status",
        "document_ids.is_blocking",
        "fee_ids.state",
        "check_ids.done",
        "poa_id",
        "capture_values",
    )
    def _compute_blocker_summary(self):
        for case in self:
            blockers = case._blockers()
            if not blockers:
                case.blocker_summary = ""
            elif len(blockers) == 1:
                case.blocker_summary = blockers[0]
            else:
                case.blocker_summary = _(
                    "%(first)s (and %(others)s more)",
                    first=blockers[0],
                    others=len(blockers) - 1,
                )

    # ==================================================================
    # The single definition of "blocked"
    # ==================================================================
    def _blockers(self, transition=None):
        """Every reason this file cannot move, in one place.

        The gate, the readiness meter, the phase rail and the desk row all call
        this. They cannot disagree about what "ready" means because there is only
        one method that decides, and it returns sentences rather than booleans so
        that whichever surface shows the answer shows the *same* answer.
        """
        self.ensure_one()
        reasons = []

        blocking_documents = self.document_ids.filtered(
            lambda line: line.is_blocking and not line._is_satisfied()
        )
        if transition is None or transition.require_documents:
            for line in blocking_documents:
                reasons.append(line._blocking_reason())

        unpaid = self.fee_ids.filtered(
            lambda fee: fee.state != "paid"
            and not fee.is_optional
            and (not fee.step_id or fee.step_id.sequence <= self.step_id.sequence)
        )
        if unpaid and (transition is None or transition.require_fees_paid):
            reasons.append(
                _(
                    "%(count)s fee(s) still unpaid at this point in the walk.",
                    count=len(unpaid),
                )
            )

        outstanding = self.check_ids.filtered(
            lambda check: check.step_id == self.step_id and check.is_required and not check.done
        )
        if outstanding:
            reasons.append(
                _(
                    "Counter check “%s” has not been done.",
                    outstanding[0].name,
                )
            )

        needs_poa = (transition and transition.require_valid_poa) or (
            transition is None and self.procedure_type_id.has_poa == "required"
        )
        if needs_poa:
            body = self.step_id.gov_body_id or self.body_id
            if not self.poa_id:
                reasons.append(
                    _(
                        "No وكالة is attached, and %s will not deal with anybody who is "
                        "not named on one.",
                        body.display_name or _("the counter"),
                    )
                )
            else:
                reason = self.poa_id._blocking_reason(body=body)
                if reason:
                    reasons.append(reason)

        for capture in self.step_id.capture_field_ids.filtered("required"):
            if not (self.capture_values or {}).get(capture.code):
                reasons.append(_("“%s” has not been recorded.", capture.label))

        for subject in self.subject_ids:
            reason = subject._blocking_reason()
            if reason:
                reasons.append(reason)

        return reasons

    # ==================================================================
    # Create - the file is opened, not merely inserted
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            procedure = self.env["legal.procedure.type"].browse(vals.get("procedure_type_id"))
            if not procedure:
                continue
            if not procedure.step_ids:
                raise UserError(
                    _(
                        "“%s” has no steps configured, so a file opened under it would "
                        "have nowhere to be. Add its steps first.",
                        procedure.display_name,
                    )
                )
            vals.setdefault("procedure_version", procedure.version)
            if not vals.get("name") or vals.get("name") == _("New"):
                vals["name"] = procedure._next_case_number() or _("New")
        cases = super().create(vals_list)
        for case in cases:
            case._log(
                "open",
                _("File opened under %s.", case.procedure_type_id.display_name),
                to_step=case.step_id,
            )
            case._sync_document_lines()
            case._sync_step_checks()
            case._sync_fees()
        return cases

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default)
        for vals in vals_list:
            vals.setdefault("name", _("New"))
        return vals_list

    # ==================================================================
    # The write override - readonly is a hint, this is a rule
    # ==================================================================
    def write(self, vals):
        """Refuse an RPC write to anything the engine owns.

        ``readonly=True`` on ``step_id`` stops the field being typed into a form
        and stops nothing else: a crafted ``write`` over RPC, or a statusbar
        somebody made clickable in a studio view, moves the file wherever it
        likes and skips every guard, every log entry and every approval on the
        way. So the rule lives here, where it cannot be bypassed by a client.
        """
        if not in_engine():
            forbidden = sorted(set(WORKFLOW_OWNED_FIELDS).intersection(vals))
            # ``procedure_type_id`` is chosen once, at intake. Changing it later
            # relocates ``step_id`` (the procedures do not share steps) with no
            # log entry - a second door into the same forgery the field guard
            # above closes - so it is locked once the file exists.
            if "procedure_type_id" in vals and any(
                record.procedure_type_id
                and record.procedure_type_id.id != vals["procedure_type_id"]
                for record in self
            ):
                forbidden.append("procedure_type_id")
            if forbidden:
                raise UserError(
                    _(
                        "A file is moved by the buttons on it, never by writing to it. "
                        "%(fields)s belong to the procedure engine, which records who "
                        "moved the file, why, and what it was blocked on at the time.",
                        fields=", ".join(forbidden),
                    )
                )
        cases = super().write(vals)
        if "step_id" in vals or "procedure_type_id" in vals:
            self._sync_document_lines()
            self._sync_step_checks()
            self._sync_fees()
        return cases

    # ==================================================================
    # The engine
    # ==================================================================
    def _engine_write(self, vals):
        """The one path allowed to write the engine-owned fields.

        Private (leading underscore) so it is unreachable over RPC, and it
        carries no client-forgeable signal: the trusted marker is a process-local
        set inside :func:`engine_guard`, never a context key a payload can spoof.
        """
        with engine_guard():
            return self.write(vals)

    def _log(self, action, description, to_step=None, from_step=None, transition=None,
             reason=None, closes_step=True):
        self.ensure_one()
        return self.env["legal.action.log"].sudo().create(
            {
                "case_id": self.id,
                "action": action,
                "description": description,
                "reason": reason,
                "from_step_id": from_step.id if from_step else False,
                "to_step_id": to_step.id if to_step else False,
                "transition_id": transition.id if transition else False,
                "closes_step": closes_step,
                "round": self.round,
                "user_id": self.env.uid,
            }
        )

    def _move_to(self, step, action, description, transition=None, reason=None):
        """Every move in the product goes through here.

        Centralised so that the log entry, the checklist refresh, the counter
        walk and the resulting document can never be forgotten by whichever
        button happened to be pressed.
        """
        self.ensure_one()
        previous = self.step_id
        self._engine_write({"step_id": step.id, "sla_paused": False})
        self._log(
            action,
            description,
            to_step=step,
            from_step=previous,
            transition=transition,
            reason=reason,
        )
        if step.kind == "terminal":
            self._engine_write({"date_closed": fields.Datetime.now()})
            self._close_open_escalations()
            if step.outcome in ("granted", "granted_conditional"):
                self._produce_result_document()
        return True

    def action_advance(self):
        """The synthesised linear advance.

        No transition row is consulted and none is needed: the next step is the
        next one in order. This is the button a clerk presses forty times a week,
        and it exists precisely so that a consultant configuring a fourteen-step
        walk does not have to type thirteen transition rows whose only content is
        the ordering they have already given.
        """
        for case in self:
            if case.step_id.kind == "terminal":
                raise UserError(
                    _("“%s” is closed. Re-open it before moving it again.", case.display_name)
                )
            blockers = case._blockers()
            if blockers:
                raise UserError(
                    _(
                        "“%(case)s” cannot move yet:\n\n%(reasons)s",
                        case=case.display_name,
                        reasons="\n".join("• %s" % reason for reason in blockers),
                    )
                )
            if not case.step_id.auto_next:
                raise UserError(
                    _(
                        "“%s” does not advance on its own - it has explicit moves, and one "
                        "of them has to be chosen.",
                        case.step_id.name,
                    )
                )
            following = case.procedure_type_id._next_step_after(case.step_id)
            if not following:
                raise UserError(
                    _(
                        "“%s” is the last step of the procedure but is not marked as closing "
                        "it. The procedure needs a terminal step.",
                        case.step_id.name,
                    )
                )
            case._move_to(
                following,
                "advance",
                _("Advanced to %s.", following.name),
            )
        return True

    def action_fire_transition(self, transition_id):
        """Make one of the explicit moves, with its guards evaluated.

        The guards are checked here rather than in the button because the button
        is a client, and a client is a suggestion. ``require_valid_poa`` in
        particular blocks outright: the counter will refuse a file presented by
        somebody who is not on the وكالة, so letting the move happen has not
        prevented the failure, only moved it to the pavement outside the ministry.
        """
        self.ensure_one()
        transition = self.env["legal.procedure.transition"].browse(int(transition_id))
        if transition not in self.available_transition_ids:
            raise UserError(
                _(
                    "“%s” is not a move that can be made from where this file is, or not "
                    "one this user may make.",
                    transition.display_name,
                )
            )
        if transition.require_reason:
            return {
                "type": "ir.actions.act_window",
                "name": transition.name,
                "res_model": "legal.case.return",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_case_id": self.id,
                    "default_transition_id": transition.id,
                },
            }
        return self._fire(transition)

    def _fire(self, transition, reason=None):
        self.ensure_one()
        blockers = self._blockers(transition=transition)
        if blockers:
            raise UserError(
                _(
                    "“%(move)s” is blocked:\n\n%(reasons)s",
                    move=transition.name,
                    reasons="\n".join("• %s" % blocker for blocker in blockers),
                )
            )
        if transition.is_return:
            return self._return_for_correction(
                transition.to_step_id, reason or "", transition=transition
            )
        self._move_to(
            transition.to_step_id,
            "transition",
            transition.name,
            transition=transition,
            reason=reason,
        )
        return True

    def action_return_for_correction(self):
        """Open the dialog that demands a reason. There is no version that does not."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Return For Correction"),
            "res_model": "legal.case.return",
            "view_mode": "form",
            "target": "new",
            "context": {"default_case_id": self.id},
        }

    def _return_for_correction(self, step, reason, transition=None):
        """Open a new round.

        Three things happen together and none of them is optional. The round
        increments, because an Iraqi file is routinely returned twice before it
        is granted and "which round is this" is the first question anybody asks.
        The service-level clock pauses, because the body cannot be held to a
        target during a round it did not cause. And the previous round's
        approvals are marked **superseded rather than deleted**, because the only
        question worth asking afterwards is what they objected to and whether it
        was fixed - and a system that erases the earlier rounds cannot answer it.
        """
        self.ensure_one()
        if not (reason or "").strip():
            raise UserError(
                _(
                    "A return needs a reason. It is what the next round is corrected "
                    "against, and without it the clerk redoing the file is guessing."
                )
            )
        target = step or self.step_id.return_to_step_id or self.procedure_type_id._first_step()
        previous = self.step_id
        self._engine_write(
            {
                "step_id": target.id,
                "round": self.round + 1,
                "sla_paused": True,
            }
        )
        self._log(
            "return",
            _("Returned for correction to %s.", target.name),
            to_step=target,
            from_step=previous,
            transition=transition,
            reason=reason,
        )
        self.document_ids._supersede_for_new_round(self.round)
        self.check_ids.filtered(lambda check: check.step_id == previous).write(
            {"superseded": True}
        )
        self._close_open_escalations()
        self.message_post(
            body=_(
                "Returned for correction (round %(round)s): %(reason)s",
                round=self.round,
                reason=reason,
            )
        )
        return True

    def action_reopen(self):
        """Put a closed file back on the walk.

        Not an edit of the closing entry - a new entry, and a new round. A file
        that was closed and re-opened is a fact about the department, and hiding
        it makes every closure statistic optimistic.
        """
        for case in self:
            if case.step_id.kind != "terminal":
                raise UserError(_("“%s” is not closed.", case.display_name))
            target = case.procedure_type_id._first_step()
            case._engine_write(
                {"date_closed": False, "round": case.round + 1, "sla_paused": False}
            )
            case._move_to(target, "reopen", _("Re-opened at %s.", target.name))
        return True

    # ==================================================================
    # Instantiation of the configured lines
    # ==================================================================
    def _sync_document_lines(self):
        """Grow the checklist as the file reaches the steps that demand things.

        Lines are added, never removed: a requirement that stops applying because
        somebody edited the file is still a line the clerk saw and acted on, and
        deleting it would erase the upload attached to it.
        """
        Line = self.env["legal.case.document"].sudo()
        for case in self:
            requirements = case.procedure_type_id.requirement_ids.filtered(
                lambda requirement: requirement.active
                and (
                    not requirement.step_id
                    or requirement.step_id.sequence <= case.step_id.sequence
                )
                and requirement._applies_to(case)
            )
            existing = {
                (line.requirement_id.id, line.subject_id.id or False)
                for line in case.document_ids
            }
            values = []
            for requirement in requirements:
                # A per-subject requirement expands into one line per name on
                # the numbered ت list; everything else is a single line whose
                # subject is empty.
                subject_ids = case.subject_ids.ids if requirement.per_subject else [False]
                for subject_id in subject_ids:
                    if (requirement.id, subject_id) in existing:
                        continue
                    values.append(
                        {
                            "case_id": case.id,
                            "requirement_id": requirement.id,
                            "document_type_id": requirement.document_type_id.id,
                            "subject_id": subject_id,
                            "is_required": requirement.is_required,
                            "minimum_grade_id": requirement.minimum_grade_id.id,
                            "round": case.round,
                        }
                    )
            if values:
                Line.create(values)
        return True

    def _sync_step_checks(self):
        """Instantiate the counter walk when the file arrives at the step."""
        Check = self.env["legal.case.step.check"].sudo()
        for case in self:
            configured = case.step_id.check_ids.filtered("active")
            existing = {
                (check.check_id.id, check.round) for check in case.check_ids
            }
            values = [
                {
                    "case_id": case.id,
                    "check_id": check.id,
                    "step_id": case.step_id.id,
                    "name": check.name,
                    "counter": check.counter,
                    "check_kind": check.check_kind,
                    "produces_stamp": check.produces_stamp,
                    "is_required": check.is_required,
                    "sequence": check.sequence,
                    "round": case.round,
                }
                for check in configured
                if (check.id, case.round) not in existing
            ]
            if values:
                Check.create(values)
        return True

    def _sync_fees(self):
        """Raise the fees the walk has reached, once each."""
        Fee = self.env["legal.fee"].sudo()
        for case in self:
            rules = case.procedure_type_id.fee_rule_ids.filtered(
                lambda rule: rule.active
                and (not rule.step_id or rule.step_id.sequence <= case.step_id.sequence)
            )
            existing = set(case.fee_ids.mapped("rule_id").ids)
            values = [
                {
                    "case_id": case.id,
                    "rule_id": rule.id,
                    "name": rule.name,
                    "step_id": rule.step_id.id,
                    "amount": rule._amount_for(case),
                    "currency_id": rule.currency_id.id,
                    "is_stamp_duty": rule.is_stamp_duty,
                    "is_optional": rule.is_optional,
                }
                for rule in rules
                if rule.id not in existing
            ]
            if values:
                Fee.create(values)
        return True

    def _produce_result_document(self):
        """File what the procedure produced in the company's permanent register.

        In the register rather than on the file, because an expiring registration
        should raise one alert and not one per open case that happens to
        reference it - and because the next procedure that needs this document
        must find it without knowing which file produced it.
        """
        self.ensure_one()
        document_type = self.procedure_type_id.result_document_type_id
        if not document_type or self.result_document_id:
            return self.env["legal.document"]
        document = self.env["legal.document"].create(
            {
                "name": _("%(type)s - %(case)s", type=document_type.display_name, case=self.name),
                "document_type_id": document_type.id,
                "entity_id": self.entity_id.id,
                "issuing_body_id": self.body_id.id,
                "issue_date": fields.Date.context_today(self),
                "notice_days": document_type.notice_days,
                "renewal_lead_days": document_type.renewal_lead_days
                or self.procedure_type_id.lead_time_days,
                "company_id": self.company_id.id,
            }
        )
        document.expiry_date = document._compute_expiry_from_type()
        self._engine_write({"result_document_id": document.id})
        self._log(
            "document",
            _("Produced %s and filed it in the register.", document.display_name),
            closes_step=False,
        )
        return document

    def _close_open_escalations(self):
        self.escalation_ids.filtered("is_open").write(
            {"resolved_on": fields.Datetime.now()}
        )
        return True

    # ==================================================================
    # Buttons that open things
    # ==================================================================
    def action_open_step_dialog(self):
        """The step dialog: the instruction, then the fields, then the move."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.step_id.desk_title or self.step_id.name,
            "res_model": "legal.case.step.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_case_id": self.id},
        }

    def action_show_blockers(self):
        """The greyed twin of the advance button, and why it is a button at all.

        A control that vanishes when it cannot be used teaches nobody anything:
        the clerk concludes the software is broken, or that the move does not
        exist. So the blocked state is a button too, and pressing it says
        exactly what is in the way, in the order the counter will find it.
        """
        self.ensure_one()
        blockers = self._blockers()
        if not blockers:
            return self.action_advance()
        raise UserError(
            _(
                "“%(case)s” cannot move yet:\n\n%(reasons)s",
                case=self.display_name,
                reasons="\n".join("• %s" % blocker for blocker in blockers),
            )
        )

    def action_open_documents(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Checklist"),
            "res_model": "legal.case.document",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
            "context": {"default_case_id": self.id},
        }

    def action_open_log(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Trail"),
            "res_model": "legal.action.log",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
        }

    # ==================================================================
    # Constraints
    # ==================================================================
    @api.constrains("step_id", "procedure_type_id")
    def _check_step_belongs_to_procedure(self):
        for case in self:
            if case.step_id and case.step_id.procedure_type_id != case.procedure_type_id:
                raise ValidationError(
                    _(
                        "“%(case)s” is on a step that belongs to another procedure. Nothing "
                        "downstream can be trusted once that is true.",
                        case=case.display_name,
                    )
                )

    @api.constrains("parent_case_id")
    def _check_parent_recursion(self):
        if self._has_cycle("parent_case_id"):
            raise ValidationError(_("A file cannot be a prerequisite of itself."))

    @api.constrains("subject_ids", "procedure_type_id")
    def _check_subject_cardinality(self):
        for case in self:
            cardinality = case.procedure_type_id.subject_cardinality
            if cardinality == "none" and case.subject_ids:
                raise ValidationError(
                    _(
                        "“%s” is a procedure about the company, so it carries no list of "
                        "people.",
                        case.procedure_type_id.display_name,
                    )
                )
            if cardinality == "one" and len(case.subject_ids) > 1:
                raise ValidationError(
                    _(
                        "“%s” is about one person. Open a file each, or change the procedure "
                        "to cover several.",
                        case.procedure_type_id.display_name,
                    )
                )

    # ==================================================================
    # Scheduled jobs
    # ==================================================================
    @api.model
    def _cron_deadline_scan(self, limit=None):
        """Raise the escalations the clocks have earned, and close the stale ones.

        Safe to run as often as the department likes: every row it writes is
        keyed so a second pass over unchanged data writes nothing at all, and it
        walks the whole live caseload rather than a "first N" head that would
        never reach the tail.
        """
        Cron = self.env["ir.cron"]
        Escalation = self.env["legal.sla.escalation"].sudo()
        now = fields.Datetime.now()

        # An escalation on a step somebody has since dealt with is noise on a
        # manager's screen, so those are closed first and unconditionally.
        stale = Escalation.search([("resolved_on", "=", False)])
        for escalation in stale:
            if (
                escalation.case_id.step_id != escalation.step_id
                or escalation.case_id.round != escalation.round
                or escalation.case_id.is_closed
            ):
                escalation.action_resolve()

        live = self.sudo().search(
            [
                ("is_closed", "=", False),
                ("sla_paused", "=", False),
                ("sla_due_on", "!=", False),
                ("sla_due_on", "<=", now),
            ],
            order="sla_due_on asc, id asc",
            limit=limit,
        )
        under_cron = bool(self.env.context.get("cron_id"))
        if under_cron:
            Cron._commit_progress(remaining=len(live))

        raised = 0
        for index in range(len(live)):
            case = live[index]
            try:
                raised += case._raise_due_escalations(now=now)
            except Exception:  # noqa: BLE001 - one bad file must not stop the run
                _logger.exception("Legal deadline scan failed on %s", case.display_name)
            if under_cron and not Cron._commit_progress(processed=1):
                _logger.info(
                    "Legal deadline scan: out of time after %s of %s file(s)",
                    index + 1,
                    len(live),
                )
                break
        _logger.info(
            "Legal deadline scan: %s file(s) past target, %s escalation(s) raised",
            len(live),
            raised,
        )
        return True

    def _raise_due_escalations(self, now=None):
        """Idempotent by the unique index, not by a flag we remember to set."""
        self.ensure_one()
        now = now or fields.Datetime.now()
        Escalation = self.env["legal.sla.escalation"].sudo()
        rule = self.env["legal.sla.rule"]._rule_for(
            self.procedure_type_id, self.step_id, self.company_id
        )
        raised = 0
        levels = [("1", self.sla_due_on, _("Past its target at %s.", self.current_body_id.display_name))]
        if self.sla_escalate_on:
            levels.append(
                ("2", self.sla_escalate_on, _("Still not dealt with after the grace period."))
            )
        rotting = self.step_id.rotting_threshold_days
        if rotting and self.stage_entered_on:
            levels.append(
                (
                    "3",
                    self.stage_entered_on + timedelta(days=rotting),
                    _("Forgotten: %s days on the same step.", rotting),
                )
            )
        for level, moment, reason in levels:
            if not moment or now < moment:
                continue
            if Escalation.search_count(
                [
                    ("case_id", "=", self.id),
                    ("step_id", "=", self.step_id.id),
                    ("round", "=", self.round),
                    ("level", "=", level),
                ]
            ):
                continue
            Escalation.create(
                {
                    "case_id": self.id,
                    "step_id": self.step_id.id,
                    "step_code": self.step_id.code or "",
                    "round": self.round,
                    "level": level,
                    "reason": reason,
                    "due_on": self.sla_due_on,
                    "escalated_to_group_id": rule.escalate_to_group_id.id if rule else False,
                }
            )
            self._log("escalate", reason, closes_step=False)
            raised += 1
        return raised
