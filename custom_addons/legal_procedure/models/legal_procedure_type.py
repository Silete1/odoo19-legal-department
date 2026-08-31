import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.fields import Domain
from odoo.tools.safe_eval import safe_eval

from .legal_constants import CHANNEL_SELECTION

_logger = logging.getLogger(__name__)

#: The three-valued matrix that drives one shared form view. This is
#: ``approval.category``'s idiom, and it is deliberately unglamorous: a custom
#: renderer per procedure would look better and would cost a developer every
#: time a body wants one more field. Three enum values cost nothing, read
#: correctly in a list, and can be searched.
USAGE_SELECTION = [
    ("required", "Required"),
    ("optional", "Optional"),
    ("no", "Not Used"),
]


class LegalProcedureType(models.Model):
    """نوع المعاملة - the unit of configuration, and the only one.

    Everything that makes a filing at the Registrar different from a filing at
    the Tax Commission lives on rows hanging off this record: its phases, its
    steps, its counter walk, its capture fields, its document requirements, its
    fees, its service levels and its letter. Adding a procedure is therefore
    data entry, and a customer with a body nobody anticipated does not need a
    developer - which is the whole thesis of the module.

    **Versioning is not decoration.** Iraqi procedure changes by circular,
    occasionally with a fortnight's notice: Council of Ministers directive
    16180 of 1 April 2024 added the paid electricity and water bills to the
    Registrar's mandatory attachments overnight. A file opened in March under
    the old rules must keep printing the old fee and demanding the old
    attachments, or the department loses the ability to explain what it did and
    why. So a change is a *new version* - ``effective_from`` on the new record,
    ``effective_to`` and ``superseded_by_id`` on the old - and a live case holds
    a snapshot of the version it opened under. Editing a live type in place is
    exactly the failure this shape exists to prevent.
    """

    _name = "legal.procedure.type"
    _description = "Procedure Type"
    _inherit = ["mail.thread"]
    _order = "sequence, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram", tracking=True)
    code = fields.Char(
        required=True,
        help="Stable key used by content packs and by the file-number sequence, "
        "e.g. MOT-INCORP, GCT-CLEARANCE, PSSO-MONTHLY.",
    )
    body_id = fields.Many2one(
        "legal.gov.body",
        string="Body",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="The body this procedure is filed at. Its working calendar is what "
        "every target on every step is counted in.",
    )
    jurisdiction_id = fields.Many2one(
        "legal.jurisdiction",
        string="Jurisdiction",
        ondelete="restrict",
        index=True,
        help="The same obligation is a different procedure federally and in the "
        "Region - different deadline, different fee, sometimes the opposite order.",
    )

    # ------------------------------------------------------------------
    # Version, because a circular can land mid-file
    # ------------------------------------------------------------------
    version = fields.Char(
        default="1.0",
        required=True,
        tracking=True,
        help="Bumped when a circular changes the procedure. Never edit a live "
        "version in place - supersede it, so open files keep their own rules.",
    )
    effective_from = fields.Date(
        tracking=True,
        help="The date the circular introducing this version took effect.",
    )
    effective_to = fields.Date(
        tracking=True,
        help="Set when a later version supersedes this one. Files already open "
        "under it carry on unchanged.",
    )
    superseded_by_id = fields.Many2one(
        "legal.procedure.type",
        string="Superseded By",
        ondelete="set null",
        index=True,
    )
    supersedes_id = fields.Many2one(
        "legal.procedure.type", string="Supersedes", ondelete="set null", index=True
    )
    is_current = fields.Boolean(
        compute="_compute_is_current",
        store=True,
        index=True,
        help="The version a new file should open under.",
    )

    # ------------------------------------------------------------------
    # The graph
    # ------------------------------------------------------------------
    phase_ids = fields.One2many(
        "legal.procedure.phase", "procedure_type_id", string="Phases", copy=False
    )
    step_ids = fields.One2many(
        "legal.procedure.step", "procedure_type_id", string="Steps", copy=False
    )
    transition_ids = fields.One2many(
        "legal.procedure.transition", "procedure_type_id", string="Transitions", copy=False
    )
    field_ids = fields.One2many(
        "legal.procedure.field",
        "procedure_type_id",
        string="Capture Fields",
        readonly=True,
        help="Every capture field across every step, so a configurer can read the "
        "whole vocabulary of the procedure on one page instead of opening ten steps.",
    )
    requirement_ids = fields.One2many(
        "legal.doc.requirement", "procedure_type_id", string="Required Documents", copy=False
    )
    fee_rule_ids = fields.One2many(
        "legal.fee.rule", "procedure_type_id", string="Fee Schedule", copy=False
    )
    sla_rule_ids = fields.One2many(
        "legal.sla.rule", "procedure_type_id", string="Service Levels", copy=False
    )
    step_count = fields.Integer(compute="_compute_counts")
    requirement_count = fields.Integer(compute="_compute_counts")
    case_count = fields.Integer(compute="_compute_counts")

    # ------------------------------------------------------------------
    # What the procedure is for
    # ------------------------------------------------------------------
    subject_cardinality = fields.Selection(
        [
            ("none", "About The Company"),
            ("one", "About One Person"),
            ("many", "About Several People"),
        ],
        default="none",
        required=True,
        help="One entry-visa letter routinely covers eight experts on a numbered "
        "list, so the people are rows on the file rather than one field - and a "
        "procedure that is about the company has no such list at all.",
    )
    result_document_type_id = fields.Many2one(
        "legal.document.type",
        string="Produces",
        ondelete="restrict",
        index=True,
        help="What lands in the company register when this procedure succeeds. "
        "This is the edge that makes the prerequisite graph traversable: a blocked "
        "checklist line can offer 'start the procedure that produces this' instead "
        "of leaving the clerk to work out which counter issues it.",
    )
    renewal_of_type_id = fields.Many2one(
        "legal.procedure.type",
        string="Renews",
        ondelete="set null",
        help="Set on the renewal procedure of a licence, so the expiry ladder "
        "offers the renewal rather than the original first-issue procedure.",
    )

    # ------------------------------------------------------------------
    # Numbering
    # ------------------------------------------------------------------
    automated_sequence = fields.Boolean(
        string="Automatic Numbering",
        default=True,
        help="Off for a procedure whose number is dictated by the body - some "
        "counters hand you their own file number and the clerk must type it.",
    )
    sequence_code = fields.Char(
        string="Number Prefix",
        help="Prefix of the generated file number, e.g. MOT/%(range_year)s/.",
    )
    sequence_id = fields.Many2one(
        "ir.sequence", string="Number Sequence", ondelete="restrict", copy=False, readonly=True
    )

    # ------------------------------------------------------------------
    # Timings and channel
    # ------------------------------------------------------------------
    expected_duration_days = fields.Integer(
        string="Typical Duration (working days)",
        default=0,
        help="What the whole procedure really takes at that counter, not what the "
        "regulation says it should.",
    )
    lead_time_days = fields.Integer(
        string="Renewal Lead Time (days)",
        default=0,
        help="Copied onto the document this procedure produces, so the renewal "
        "board can say 'start now' rather than 'expires in sixty days'.",
    )
    channel = fields.Selection(
        CHANNEL_SELECTION,
        default="paper",
        required=True,
        help="Overrides the body: a ministry may take renewals online and "
        "everything else on paper.",
    )
    instruction = fields.Html(
        translate=True,
        help="The standing instruction for the whole procedure: which floor, how "
        "many photocopies, what to bring, who to ask for.",
    )

    # ------------------------------------------------------------------
    # The has_* matrix - one form view, no custom renderer
    # ------------------------------------------------------------------
    has_outgoing_letter = fields.Selection(
        USAGE_SELECTION, string="Outgoing Letter", default="required", required=True
    )
    has_incoming_reply = fields.Selection(
        USAGE_SELECTION,
        string="Written Reply",
        default="required",
        required=True,
        help="Some counters answer by handing back a stamped copy and never write.",
    )
    has_fee = fields.Selection(
        USAGE_SELECTION, string="Fees", default="optional", required=True
    )
    has_result_document = fields.Selection(
        USAGE_SELECTION, string="Resulting Document", default="optional", required=True
    )
    has_subjects = fields.Selection(
        USAGE_SELECTION, string="Named People", default="no", required=True
    )
    has_poa = fields.Selection(
        USAGE_SELECTION,
        string="Power Of Attorney",
        default="optional",
        required=True,
        help="Required where the counter will not deal with anyone who is not on "
        "the power of attorney - which is most counters, most of the time.",
    )
    requires_documents = fields.Selection(
        USAGE_SELECTION, string="Document Checklist", default="required", required=True
    )

    # ------------------------------------------------------------------
    # Provenance
    # ------------------------------------------------------------------
    legal_basis = fields.Char(translate=True)
    legal_basis_url = fields.Char()
    last_verified_on = fields.Date(
        help="When a human last read the circular. A shipped procedure nobody has "
        "re-read is a wasted trip waiting to happen.",
    )

    colour = fields.Integer(string="Colour")
    sequence = fields.Integer(default=10)
    company_id = fields.Many2one("res.company", string="Company", index=True)
    active = fields.Boolean(default=True)

    _code_version_company_uniq = models.Constraint(
        "UNIQUE(code, version, company_id)",
        "That procedure code already exists at that version for this company.",
    )

    # ==================================================================
    # Computes and constraints
    # ==================================================================
    @api.depends("superseded_by_id", "effective_to", "active")
    def _compute_is_current(self):
        today = fields.Date.context_today(self)
        for procedure in self:
            procedure.is_current = bool(
                procedure.active
                and not procedure.superseded_by_id
                and (not procedure.effective_to or procedure.effective_to >= today)
            )

    def _compute_counts(self):
        cases = dict(
            self.env["legal.case"]._read_group(
                [("procedure_type_id", "in", self.ids)],
                ["procedure_type_id"],
                ["__count"],
            )
        )
        for procedure in self:
            procedure.step_count = len(procedure.step_ids)
            procedure.requirement_count = len(procedure.requirement_ids)
            procedure.case_count = cases.get(procedure, 0)

    @api.depends("name", "version")
    def _compute_display_name(self):
        for procedure in self:
            name = procedure.name or ""
            procedure.display_name = f"{name} (v{procedure.version})" if procedure.version else name

    @api.constrains("effective_from", "effective_to")
    def _check_effective_window(self):
        for procedure in self:
            if (
                procedure.effective_from
                and procedure.effective_to
                and procedure.effective_to < procedure.effective_from
            ):
                raise ValidationError(
                    _("A procedure version cannot stop applying before it starts.")
                )

    @api.constrains("superseded_by_id")
    def _check_supersession_recursion(self):
        if self._has_cycle("superseded_by_id"):
            raise ValidationError(_("A procedure version cannot supersede itself."))

    # ==================================================================
    # Copying the graph, with its cross-references remapped
    # ==================================================================
    # Every one2many of the graph is copy=False and the copy is done by hand
    # below. That is not fussiness: Odoo copies a one2many line by line and
    # leaves the foreign keys *inside* those lines pointing at the originals, so
    # a naive duplicate produces a new procedure whose transitions lead into the
    # old procedure's steps. The constraint catches it, which is the good case;
    # the bad case is a version that quietly moves live files back onto the
    # version it was supposed to replace.

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default)
        for procedure, vals in zip(self, vals_list):
            vals.setdefault("version", "%s-copy" % (procedure.version or "1.0"))
            vals.setdefault("sequence_id", False)
        return vals_list

    def copy(self, default=None):
        copies = super().copy(default)
        for original, copied in zip(self, copies):
            original._copy_graph_into(copied)
        return copies

    def _copy_graph_into(self, target):
        """Clone phases, steps, transitions and rules, remapping as we go."""
        self.ensure_one()
        phase_map = {}
        for phase in self.phase_ids:
            phase_map[phase.id] = phase.copy({"procedure_type_id": target.id}).id

        step_map = {}
        for step in self.step_ids:
            step_map[step.id] = step.copy(
                {
                    "procedure_type_id": target.id,
                    "phase_id": phase_map.get(step.phase_id.id, False),
                    # Filled on the second pass: the step it returns to may not
                    # exist yet on this one.
                    "return_to_step_id": False,
                }
            ).id
        Step = self.env["legal.procedure.step"]
        for step in self.step_ids.filtered("return_to_step_id"):
            Step.browse(step_map[step.id]).return_to_step_id = step_map.get(
                step.return_to_step_id.id, False
            )

        for transition in self.transition_ids:
            transition.copy(
                {
                    "procedure_type_id": target.id,
                    "from_step_id": step_map.get(transition.from_step_id.id, False),
                    "to_step_id": step_map.get(transition.to_step_id.id, False),
                }
            )
        for requirement in self.requirement_ids:
            requirement.copy(
                {
                    "procedure_type_id": target.id,
                    "step_id": step_map.get(requirement.step_id.id, False),
                }
            )
        for rule in self.fee_rule_ids:
            rule.copy(
                {
                    "procedure_type_id": target.id,
                    "step_id": step_map.get(rule.step_id.id, False),
                }
            )
        for rule in self.sla_rule_ids:
            rule.copy(
                {
                    "procedure_type_id": target.id,
                    "step_id": step_map.get(rule.step_id.id, False),
                }
            )
        return target

    # ==================================================================
    # Numbering
    # ==================================================================
    def _ensure_sequence(self):
        """Create the file-number sequence on demand, per procedure.

        Deliberately lazy: a consultant sketching six procedure types should not
        leave six orphan sequences behind when they delete five of them.
        """
        self.ensure_one()
        if self.sequence_id or not self.automated_sequence:
            return self.sequence_id
        prefix = self.sequence_code or "%s/%%(range_year)s/" % (self.code or "LEGAL")
        sequence = self.env["ir.sequence"].sudo().create(
            {
                "name": _("File number - %s", self.name),
                "code": "legal.case.%s" % (self.code or self.id),
                "prefix": prefix,
                "padding": 4,
                "use_date_range": True,
                "company_id": self.company_id.id or False,
            }
        )
        self.sudo().sequence_id = sequence
        return sequence

    def _next_case_number(self):
        self.ensure_one()
        sequence = self._ensure_sequence()
        if not sequence:
            return False
        return sequence.next_by_id() or False

    # ==================================================================
    # The first step, and the synthesised linear advance
    # ==================================================================
    def _first_step(self):
        self.ensure_one()
        return self.step_ids.sorted(lambda step: (step.sequence, step.id))[:1]

    def _next_step_after(self, step):
        """The step the engine synthesises an advance to.

        A strictly linear procedure needs no transition rows at all: the next
        step is simply the next one in order. That is not a shortcut, it is the
        point - fifty rows saying "from 3 to 4, from 4 to 5" are fifty rows a
        consultant can get wrong, and they carry no information the ordering did
        not already carry.
        """
        self.ensure_one()
        ordered = self.step_ids.sorted(lambda candidate: (candidate.sequence, candidate.id))
        ids = ordered.ids
        if step.id not in ids:
            return self.env["legal.procedure.step"]
        position = ids.index(step.id)
        if position + 1 >= len(ids):
            return self.env["legal.procedure.step"]
        return ordered[position + 1]

    # ==================================================================
    # Validation - the loud kind
    # ==================================================================
    def _graph_problems(self):
        """Every fault in the graph, as a list of sentences a consultant can act on.

        Split out from :meth:`action_validate` so the case engine can refuse to
        open a file on a broken procedure using exactly the same reasoning that
        the configuration screen shows.
        """
        self.ensure_one()
        problems = []
        steps = self.step_ids.sorted(lambda step: (step.sequence, step.id))
        if not steps:
            return [
                _("“%s” has no steps, so a file opened under it would have nowhere to be.", self.name)
            ]

        first = steps[0]
        if first.kind == "terminal":
            problems.append(
                _(
                    "The first step “%s” is terminal - every file would close the moment it opened.",
                    first.name,
                )
            )

        # -- transitions that leave the procedure ------------------------
        for transition in self.transition_ids:
            for side, step in (
                (_("out of"), transition.from_step_id),
                (_("into"), transition.to_step_id),
            ):
                if step and step.procedure_type_id != self:
                    problems.append(
                        _(
                            "Transition “%(transition)s” leads %(side)s “%(step)s”, which belongs "
                            "to “%(other)s”. A file cannot leave its own procedure.",
                            transition=transition.name,
                            side=side,
                            step=step.display_name,
                            other=step.procedure_type_id.display_name,
                        )
                    )

        # -- reachability -------------------------------------------------
        outgoing = {}
        for transition in self.transition_ids:
            if transition.from_step_id and transition.to_step_id:
                outgoing.setdefault(transition.from_step_id.id, []).append(transition.to_step_id)

        reachable = {first.id}
        frontier = [first]
        while frontier:
            step = frontier.pop()
            successors = list(outgoing.get(step.id, []))
            if step.auto_next and step.kind != "terminal":
                successor = self._next_step_after(step)
                if successor:
                    successors.append(successor)
            if step.return_to_step_id:
                successors.append(step.return_to_step_id)
            for successor in successors:
                if successor.id not in reachable:
                    reachable.add(successor.id)
                    frontier.append(successor)

        for step in steps:
            if step.id not in reachable:
                problems.append(
                    _(
                        "Step “%s” can never be reached: nothing advances into it and no "
                        "transition targets it. Either let the step before it advance "
                        "automatically, or add the transition that leads there.",
                        step.name,
                    )
                )

        # -- dead ends ----------------------------------------------------
        for step in steps:
            if step.kind == "terminal":
                continue
            has_way_out = bool(outgoing.get(step.id)) or (
                step.auto_next and bool(self._next_step_after(step))
            )
            if not has_way_out:
                problems.append(
                    _(
                        "Step “%s” is not terminal but has no way out - a file that arrives "
                        "there is stuck for ever.",
                        step.name,
                    )
                )

        # -- conditions that can never be true -----------------------------
        # This is the worst of the faults, because the symptom is not an error.
        # It is a button that simply never appears, and nobody reports a button
        # they have never seen.
        case_model = self.env["legal.case"]
        for transition in self.transition_ids.filtered("condition_domain"):
            try:
                domain = Domain(safe_eval(transition.condition_domain, {"uid": self.env.uid}))
                domain.validate(case_model)
            except Exception as error:  # noqa: BLE001 - the message is the product
                problems.append(
                    _(
                        "The condition on “%(transition)s” is not a usable filter: %(error)s",
                        transition=transition.name,
                        error=error,
                    )
                )
                continue
            if domain.optimize(case_model).is_false():
                problems.append(
                    _(
                        "The condition on “%s” can never be true, so the button would never "
                        "appear and nobody would ever report it missing.",
                        transition.name,
                    )
                )

        # -- steps with no counter -----------------------------------------
        for step in steps.filtered(lambda candidate: not candidate.gov_body_id):
            problems.append(
                _("Step “%s” names no body. A step with no counter is hiding one.", step.name)
            )
        return problems

    def action_validate(self):
        """Walk the graph and refuse to stay quiet about a hole in it."""
        self.ensure_one()
        problems = self._graph_problems()
        if problems:
            raise UserError(
                _(
                    "“%(name)s” is not ready to run:\n\n%(problems)s",
                    name=self.display_name,
                    problems="\n".join("• %s" % problem for problem in problems),
                )
            )
        count = len(self.step_ids)
        self.message_post(
            body=_(
                "Procedure graph validated: %s step(s), every one reachable and every one "
                "with a way out.",
                count,
            )
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Procedure is runnable"),
                "message": _("%s step(s) checked, no unreachable or dead-end step.", count),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_new_version(self):
        """Supersede this version rather than editing it.

        The copy carries the graph; the original keeps its open files, its
        letters and its fee schedule exactly as they were on the day they were
        filed.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        new_version = self.copy(
            {
                "name": self.name,
                "version": "%s+" % (self.version or "1.0"),
                "effective_from": today,
                "effective_to": False,
                "supersedes_id": self.id,
                "superseded_by_id": False,
                "sequence_id": False,
            }
        )
        self.write({"effective_to": today, "superseded_by_id": new_version.id})
        self.message_post(body=_("Superseded by version %s.", new_version.version))
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.procedure.type",
            "res_id": new_version.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_cases(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Files"),
            "res_model": "legal.case",
            "view_mode": "kanban,list,form",
            "domain": [("procedure_type_id", "=", self.id)],
            "context": {"default_procedure_type_id": self.id},
        }
