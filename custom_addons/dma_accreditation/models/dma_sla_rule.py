# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Configurable service levels for the steps of the accreditation process.

One row per (step, responsible role). Everything the engine needs to answer
"is this file late?" is here, and nothing else: the Directorate sets three
durations per step and is done. Deliberately *not* seeded with legal deadlines
- the shipped rows are starting values the Accreditation Manager is expected to
replace with whatever the Directorate's own service charter says.
"""
from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, ValidationError

from .dma_constants import (
    ROLE_SELECTION,
    SLA_TRACKED_STATES,
    STATE_PENDING_ROLE,
    STATE_SELECTION,
    role_label,
    state_label,
)

#: A step is only worth a service level if the Directorate is the one holding
#: the file at that point.
SLA_STATE_SELECTION_FIELD = [
    (key, label) for key, label in STATE_SELECTION if key in SLA_TRACKED_STATES
]


class DmaSlaRule(models.Model):
    """Target, warning and escalation delays of one workflow step."""

    _name = "dma.sla.rule"
    _description = "Accreditation Service Level"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    state = fields.Selection(
        SLA_STATE_SELECTION_FIELD, string="Step", required=True, index=True,
        help="Workflow step this service level applies to.",
    )
    role = fields.Selection(
        ROLE_SELECTION, string="Responsible Role", required=True, index=True,
        help="Department expected to act. The dual confirmation is the one step "
             "with two of them at the same time, so it carries one row per party.",
    )
    target_days = fields.Float(
        string="Target (days)", required=True, default=3.0,
        help="How long the step may take, counted from the moment the file "
             "reached it. 0.5 is half a day.",
    )
    warning_days = fields.Float(
        string="Warn Before (days)", default=1.0,
        help="How long before the target the file starts showing as due soon.",
    )
    escalation_days = fields.Float(
        string="Escalate After (days)", default=2.0,
        help="How long after the target the file is escalated to the "
             "Accreditation Manager. Zero escalates as soon as it is overdue.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Company", index=True,
        default=lambda self: self.env.company,
        help="Leave empty to apply the rule to every company.",
    )
    note = fields.Text(
        string="Note",
        help="Why this delay: the article of the service charter, the committee "
             "calendar, whatever the Directorate wants on the record.",
    )

    # A step/role pair can only carry one live service level; two would make
    # "the" deadline of a file ambiguous.
    # COALESCE, because the directorate wide rows carry a NULL company and SQL
    # considers two NULLs different: a plain UNIQUE would happily let the same
    # step be defined twice.
    _unique_step_role = models.UniqueIndex(
        "(state, role, COALESCE(company_id, 0))",
        "A service level already exists for this step and department.",
    )
    _target_positive = models.Constraint(
        "CHECK(target_days > 0)",
        "The target of a service level must be greater than zero.",
    )
    _warning_positive = models.Constraint(
        "CHECK(warning_days >= 0 AND escalation_days >= 0)",
        "The warning and escalation delays of a service level cannot be negative.",
    )

    @api.depends("state", "role")
    def _compute_display_name(self):
        for rule in self:
            rule.display_name = "%s / %s" % (
                state_label(self.env, rule.state) if rule.state else "",
                role_label(self.env, rule.role) if rule.role else "",
            )

    @api.constrains("warning_days", "target_days")
    def _check_warning_within_target(self):
        for rule in self:
            if rule.warning_days > rule.target_days:
                raise ValidationError(self.env._(
                    "The warning of “%s” starts before the file even reaches the "
                    "step: it cannot be longer than the target itself.",
                    rule.display_name,
                ))

    @api.onchange("state")
    def _onchange_state(self):
        """Propose the department that owns the step."""
        for rule in self:
            if rule.state and not rule.role:
                rule.role = STATE_PENDING_ROLE.get(rule.state) or False

    # ------------------------------------------------------------------
    # Access - the Accreditation Manager owns the configuration
    # ------------------------------------------------------------------
    def _check_manager(self):
        """Guard the configuration server side.

        ``ir.model.access`` already keeps everybody else out, but the rules
        decide when a department is publicly late, so the guard is repeated
        here the way the rest of the module repeats its role checks: the view
        level ``groups=`` is only cosmetic.
        """
        if self.env.su or self.env.user.has_group("dma_accreditation.group_dma_manager"):
            return
        raise AccessError(self.env._(
            "Only the Accreditation Manager can change the service levels."
        ))

    def _propagate_to_open_requests(self):
        """Move the deadlines of the live caseload with the rule that changed.

        ``dma.accreditation.request.sla_due_on`` is stored so it can be sorted
        and filtered on, but there is no field path from a request to this
        table, so the ORM cannot know a rule change invalidates it. This closes
        that loop explicitly - only over open files, since a decided one has no
        deadline left to move.
        """
        self._invalidate_rule_cache()
        return self.env["dma.accreditation.request"]._sla_recompute_open_requests()

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        rules = super().create(vals_list)
        rules._propagate_to_open_requests()
        return rules

    def write(self, vals):
        self._check_manager()
        result = super().write(vals)
        self._propagate_to_open_requests()
        return result

    def unlink(self):
        self._check_manager()
        # Read the affected caseload before the rows go, then recompute after.
        result = super().unlink()
        self._invalidate_rule_cache()
        self.env["dma.accreditation.request"]._sla_recompute_open_requests()
        return result

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache("company_id")
    def _rule_id_map(self, company_id=False):
        """``(state, role)`` -> rule id, cached for the whole registry.

        The service level of a step is read once per file the engine looks at,
        and the engine looks at the whole live caseload on every cron run and
        on every filtered list. Without this cache that is one query per file;
        with it, it is one query per configuration change. The cache is dropped
        by :meth:`_invalidate_rule_cache` whenever a rule moves.
        """
        domain = (
            ["|", ("company_id", "=", company_id), ("company_id", "=", False)]
            if company_id else [("company_id", "=", False)]
        )
        rules = self.sudo().search(domain, order="company_id desc, sequence, id")
        mapping = {}
        for rule in rules:
            # Company specific first, so a directorate wide default never wins
            # over a company that has set its own.
            mapping.setdefault((rule.state, rule.role), rule.id)
        return mapping

    @api.model
    def _rule_map(self, company_id=False):
        """``(state, role)`` -> rule record, browsed in one go."""
        mapping = self._rule_id_map(company_id)
        if not mapping:
            return {}
        # One browse of the whole set: reading ``target_days`` on the first
        # rule prefetches every other rule in the same query.
        rules = self.sudo().browse(set(mapping.values()))
        by_id = {rule.id: rule for rule in rules}
        return {key: by_id[rule_id] for key, rule_id in mapping.items() if rule_id in by_id}

    @api.model
    def _invalidate_rule_cache(self):
        self.env.registry.clear_cache()
