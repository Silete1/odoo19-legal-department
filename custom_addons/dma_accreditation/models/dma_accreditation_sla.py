# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Time control: how long a file has been where it is, and what to do about it.

The module already knows *what* status a request is in. This adds *how long*,
*against what target* and *who owes the next move* - and it derives all of it
from the immutable approval log rather than from a second, drifting set of
timestamps.

Why the approval log and nothing else
-------------------------------------
Every transition appends exactly one ``dma.approval.line`` carrying the step
that was *left* and the moment it was left, and ``dma_process_log`` marks the
entries that actually closed a step. So the moment a file arrived where it is
now is simply the date of the last entry that closed something - and the extra
entries the dual confirmation writes while the file stays put (Finance signs,
Operations signs) are not closures and correctly leave the clock alone.

``stage_entered_on`` is therefore a stored *computed* field rather than a
timestamp the workflow methods write by hand: the log is the single source of
truth, the ORM keeps the column in step with it, it can never drift, and an
upgrade backfills every historical file for free.
"""
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .dma_constants import (
    CLOSED_STATES,
    PAUSED_STATES,
    ROLE_SELECTION,
    SLA_STATE_SELECTION,
    SLA_TRACKED_STATES,
    role_label,
    state_label,
    worst_sla_state,
)

_logger = logging.getLogger(__name__)

#: Verdicts that mean somebody has to be told something.
ACTIONABLE_SLA_STATES = ("warning", "overdue", "escalated")

#: Icon per verdict. Colour is never the only carrier of the message: the badge
#: always ships the written verdict and one of these next to it.
SLA_STATE_ICON = {
    "on_track": "fa-clock-o",
    "warning": "fa-hourglass-half",
    "overdue": "fa-exclamation-triangle",
    "escalated": "fa-exclamation-circle",
    "paused": "fa-pause-circle",
    "not_applicable": "fa-minus-circle",
}


class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    # ==================================================================
    # Where the clock is
    # ==================================================================
    stage_entered_on = fields.Datetime(
        string="Step Entered On", compute="_compute_stage_entered_on", store=True,
        index=True, readonly=True,
        help="When the file reached the step it is on now. Read off the "
             "approval log, so it can never drift away from the workflow.",
    )
    stage_age_hours = fields.Float(
        string="Waiting (hours)", compute="_compute_stage_age",
        help="How long the file has been on its current step.",
    )
    stage_age_display = fields.Char(
        string="Waiting", compute="_compute_stage_age",
        # "2 day(s) 6 h" is a translated string, and a field that is not stored
        # is cached across environments: without this the Arabic reader gets
        # served whatever the English one computed first in the same worker.
        depends_context=("lang",),
    )

    # ==================================================================
    # The service level
    # ==================================================================
    sla_due_on = fields.Datetime(
        string="Due On", compute="_compute_sla_due_on", store=True, index=True,
        help="When the current step should have been dealt with. Empty when no "
             "service level covers the step.",
    )
    sla_target_days = fields.Float(
        string="Target (days)", compute="_compute_sla_due_on", store=True,
    )
    sla_state = fields.Selection(
        SLA_STATE_SELECTION, string="Service Level", compute="_compute_sla_live",
        search="_search_sla_state",
        help="On track, due soon, overdue or escalated - measured from the "
             "moment the file reached its current step.",
    )
    sla_overdue_hours = fields.Float(
        string="Overdue By (hours)", compute="_compute_sla_live",
    )
    sla_blocking_role = fields.Selection(
        ROLE_SELECTION, string="Waiting On", compute="_compute_sla_live",
        help="The department the file is actually waiting for. On the dual "
             "confirmation that is whichever of Finance and Operations has "
             "not signed - the later of the two, when neither has.",
    )
    # Technical payload of the SLA badge, exactly like ``progress_payload``:
    # every label is translated server side, so the widget stays a renderer.
    sla_payload = fields.Json(
        string="Service Level Badge", compute="_compute_sla_live",
        depends_context=("lang",),
    )

    # ==================================================================
    # Escalation
    # ==================================================================
    escalation_ids = fields.One2many(
        "dma.sla.escalation", "request_id", string="Escalations", readonly=True,
    )
    open_escalation_count = fields.Integer(
        string="Open Escalations", compute="_compute_escalation_state", store=True,
    )
    escalation_level = fields.Selection(
        [("1", "Department Warning"), ("2", "Escalated to the Accreditation Manager")],
        string="Escalation Level", compute="_compute_escalation_state", store=True,
        index=True,
    )

    # ==================================================================
    # Parallel dual confirmation - two clocks on one step
    # ==================================================================
    dual_confirm_started_on = fields.Datetime(
        string="Dual Confirmation Started", compute="_compute_dual_confirm_timing",
        store=True,
        help="When the file reached the parallel confirmation step. Kept after "
             "the file moves on, because both departmental clocks are measured "
             "from it.",
    )
    dual_confirm_first_on = fields.Datetime(
        string="First Confirmation", compute="_compute_dual_confirm_timing", store=True,
    )
    dual_confirm_second_on = fields.Datetime(
        string="Second Confirmation", compute="_compute_dual_confirm_timing", store=True,
    )
    dual_confirm_hours = fields.Float(
        string="Dual Confirmation (hours)", compute="_compute_dual_confirm_timing",
        store=True,
        help="From the moment the file reached the dual confirmation to the "
             "second of the two signatures.",
    )
    finance_pending_hours = fields.Float(
        string="Finance Pending (hours)", compute="_compute_dual_confirm_pending",
    )
    operations_pending_hours = fields.Float(
        string="Operations Pending (hours)", compute="_compute_dual_confirm_pending",
    )

    # ==================================================================
    # Computes
    # ==================================================================
    @api.depends(
        "create_date", "approval_line_ids.date", "approval_line_ids.is_transition",
    )
    def _compute_stage_entered_on(self):
        """The file arrived here exactly when the previous step was closed."""
        for request in self:
            closed = [
                line for line in request._ordered_approval_lines() if line.is_transition
            ]
            request.stage_entered_on = closed[-1].date if closed else request.create_date

    def _ordered_approval_lines(self):
        """The approval log of one file, oldest first, ties broken by id."""
        self.ensure_one()
        epoch = fields.Datetime.to_datetime("1970-01-01 00:00:00")
        return self.approval_line_ids.sorted(
            lambda line: (line.date or epoch, line.id)
        )

    def _process_visits(self):
        """The canonical process history of one file: one entry per *visit*.

        This is the module's single narrative of "where was this file, when,
        and for how long", and it is nothing more than a reading of the
        approval log: every entry that closed a step is one completed visit,
        and the step the file is on now is the visit left open at the end.

        A file that was returned and came round again therefore yields *two*
        visits to the same step, which is exactly what makes the rework
        figures of the performance screen true.

        :return: ``[{step, entered_on, left_on, hours, open, decision, role,
                  user_id, user}]`` in chronological order. The last entry is
                  always the open one.
        """
        self.ensure_one()
        visits = [{
            "step": line.step,
            "entered_on": line.entered_on,
            "left_on": line.date,
            "hours": line.duration_hours,
            "open": False,
            "decision": line.decision,
            "role": line.role,
            "user_id": line.user_id.id,
            "user": line.user_id.display_name,
        } for line in self._ordered_approval_lines() if line.is_transition]
        visits.append({
            "step": self.state,
            "entered_on": visits[-1]["left_on"] if visits else self.create_date,
            "left_on": False,
            "hours": self.stage_age_hours,
            "open": True,
            "decision": False,
            "role": self.pending_group or False,
            "user_id": False,
            "user": False,
        })
        return visits

    @api.depends("stage_entered_on", "state")
    def _compute_stage_age(self):
        now = fields.Datetime.now()
        for request in self:
            if not request.stage_entered_on or request.state in CLOSED_STATES:
                request.stage_age_hours = 0.0
                request.stage_age_display = ""
                continue
            hours = (now - request.stage_entered_on).total_seconds() / 3600.0
            request.stage_age_hours = max(hours, 0.0)
            request.stage_age_display = request._format_hours(hours)

    @api.depends(
        "state", "stage_entered_on", "active", "company_id",
        "finance_confirmed_sop_fee", "operations_confirmed_sop",
    )
    def _compute_sla_due_on(self):
        """The deadline itself, which does not move with the wall clock.

        Stored, so a manager can sort a list by "most overdue" and the search
        view can filter on a due date without the server evaluating every file
        in Python. Only :meth:`_compute_sla_live` reads the clock.
        """
        for request in self:
            targets = request._sla_targets()
            if not targets:
                request.sla_due_on = False
                request.sla_target_days = 0.0
                continue
            # The file is late as soon as the *first* of its obligations is,
            # so the deadline of the record is the earliest of them.
            _role, rule, due = min(targets, key=lambda item: item[2])
            request.sla_due_on = due
            request.sla_target_days = rule.target_days

    @api.depends(
        "state", "stage_entered_on", "active", "escalation_level", "company_id",
        "finance_confirmed_sop_fee", "operations_confirmed_sop",
    )
    def _compute_sla_live(self):
        """Everything that depends on "now", and therefore is never stored.

        The dependencies below only say when the answer must be thrown away
        *within* a transaction; the wall clock is read afresh on every compute,
        which is what keeps a list of files honest as the day goes on.
        """
        now = fields.Datetime.now()
        rtl = self.env["res.lang"]._lang_get(
            self.env.lang or "en_US"
        ).direction == "rtl"
        for request in self:
            verdict = request._sla_verdict(now=now)
            request.sla_state = verdict["state"]
            request.sla_overdue_hours = verdict["overdue_hours"]
            request.sla_blocking_role = verdict["role"] or False
            request.sla_payload = request._sla_badge_payload(verdict, rtl=rtl)

    @api.depends("escalation_ids.is_open", "escalation_ids.level")
    def _compute_escalation_state(self):
        for request in self:
            openings = request.escalation_ids.filtered("is_open")
            request.open_escalation_count = len(openings)
            levels = openings.mapped("level")
            request.escalation_level = max(levels) if levels else False

    @api.depends(
        "state", "stage_entered_on",
        "finance_confirmed_on", "operations_confirmed_on",
        "approval_line_ids.step", "approval_line_ids.date",
    )
    def _compute_dual_confirm_timing(self):
        for request in self:
            started = request._dual_confirm_started_on()
            request.dual_confirm_started_on = started
            stamps = sorted(
                stamp for stamp in
                (request.finance_confirmed_on, request.operations_confirmed_on)
                if stamp
            )
            request.dual_confirm_first_on = stamps[0] if stamps else False
            second = stamps[1] if len(stamps) == 2 else False
            request.dual_confirm_second_on = second
            if second and started:
                request.dual_confirm_hours = max(
                    (second - started).total_seconds() / 3600.0, 0.0,
                )
            else:
                request.dual_confirm_hours = 0.0

    @api.depends(
        "state", "dual_confirm_started_on",
        "finance_confirmed_on", "operations_confirmed_on",
    )
    def _compute_dual_confirm_pending(self):
        """How long each of the two parties has been sitting on the file."""
        now = fields.Datetime.now()
        for request in self:
            start = request.dual_confirm_started_on
            for field_name, signed_on in (
                ("finance_pending_hours", request.finance_confirmed_on),
                ("operations_pending_hours", request.operations_confirmed_on),
            ):
                end = signed_on or (now if request.state == "dual_confirm" else False)
                request[field_name] = max(
                    (end - start).total_seconds() / 3600.0, 0.0,
                ) if (start and end) else 0.0

    # ==================================================================
    # The engine
    # ==================================================================
    def _dual_confirm_started_on(self):
        """When the file reached the parallel confirmation, latest visit.

        The stage clock moves on with the file, so once the dual confirmation
        is behind it the moment has to be read back out of the process history.
        A file that was returned and came round a second time reports its
        latest visit - the one its two signatures actually belong to.
        """
        self.ensure_one()
        for visit in reversed(self._process_visits()):
            if visit["step"] == "dual_confirm":
                return visit["entered_on"]
        return False

    def _sla_targets(self):
        """``[(role, rule, due_on)]`` for every obligation still open.

        One entry per department that still owes a move. The dual confirmation
        is the only step that yields two of them.
        """
        self.ensure_one()
        if not self.active or self.state in CLOSED_STATES or self.state in PAUSED_STATES:
            return []
        if not self.stage_entered_on:
            return []
        rules = self.env["dma.sla.rule"]._rule_map(self.company_id.id)
        targets = []
        for role in self._pending_roles():
            rule = rules.get((self.state, role))
            if not rule:
                continue
            targets.append((
                role, rule,
                self.stage_entered_on + timedelta(days=rule.target_days),
            ))
        return targets

    def _sla_verdict(self, now=None):
        """The full live answer for one file.

        Returns the verdict, the deadline, how late it is, the department that
        is holding it up and the per-department detail the dual confirmation
        needs.
        """
        self.ensure_one()
        now = now or fields.Datetime.now()
        empty = {
            "state": "not_applicable", "due_on": False, "overdue_hours": 0.0,
            "role": False, "rule": self.env["dma.sla.rule"], "parties": [],
        }
        if not self.active or self.state in CLOSED_STATES:
            return empty
        if self.state in PAUSED_STATES:
            return dict(empty, state="paused")
        targets = self._sla_targets()
        if not targets:
            return empty

        parties = []
        for role, rule, due in targets:
            warn_at = due - timedelta(days=rule.warning_days)
            escalate_at = due + timedelta(days=rule.escalation_days)
            if now < warn_at:
                state = "on_track"
            elif now < due:
                state = "warning"
            elif now < escalate_at:
                state = "overdue"
            else:
                state = "escalated"
            parties.append({
                "role": role,
                "rule": rule,
                "due_on": due,
                "state": state,
                "overdue_hours": max((now - due).total_seconds() / 3600.0, 0.0),
            })

        overall = worst_sla_state([party["state"] for party in parties])
        # Whoever is worst off, and among equals whoever was due first.
        blocking = min(
            (party for party in parties if party["state"] == overall),
            key=lambda party: party["due_on"],
        )
        return {
            "state": overall,
            "due_on": min(party["due_on"] for party in parties),
            "overdue_hours": blocking["overdue_hours"],
            "role": blocking["role"],
            "rule": blocking["rule"],
            "parties": parties,
        }

    # ==================================================================
    # Search
    # ==================================================================
    def _search_sla_state(self, operator, value):
        """Filter on a verdict that is recomputed from the clock on every read.

        Evaluated in Python over the *candidates* rather than translated into
        one enormous domain: the inputs are all stored, indexed columns, the
        candidate set is the live caseload of a directorate, and a hand rolled
        SQL translation of six thresholds times a configurable rule table is
        exactly the kind of thing that quietly stops matching the compute.
        """
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(self.env._("Unsupported operator on the Service Level filter."))
        wanted = set(value) if operator in ("in", "not in") else {value}
        wanted = {item for item in wanted if item}
        negative = operator in ("!=", "not in")
        if not wanted:
            return [("id", "in" if negative else "not in", [])]

        # Every verdict other than "no service level" can only be reached by a
        # live file, which keeps the candidate set to the open caseload.
        live_only = "not_applicable" not in wanted
        domain = [("state", "in", list(SLA_TRACKED_STATES))] if live_only else []
        candidates = self.sudo().with_context(active_test=live_only).search(domain)
        now = fields.Datetime.now()
        matching = [
            request.id for request in candidates
            if request._sla_verdict(now=now)["state"] in wanted
        ]
        return [("id", "not in" if negative else "in", matching)]

    # ==================================================================
    # Presentation helpers
    # ==================================================================
    def _format_hours(self, hours):
        """A waiting time a human reads at a glance, in the reader's language.

        Days and hours rather than "63.4h": an accreditation is a paper process
        measured in working days, and the module already speaks of files in
        "day(s)" on the dashboard.
        """
        hours = max(float(hours or 0.0), 0.0)
        if hours < 1:
            # Rounded, not floored to one: a step that took no measurable time
            # took no measurable time, and saying "1 min" invents a minute.
            return self.env._("%s min", int(round(hours * 60)))
        if hours < 24:
            return self.env._("%s hour(s)", int(hours))
        days = int(hours // 24)
        rest = int(hours - days * 24)
        if not rest:
            return self.env._("%s day(s)", days)
        return self.env._("%(days)s day(s) %(hours)s h", days=days, hours=rest)

    def _sla_state_labels(self):
        """``verdict key -> translated label``.

        Read off the field rather than off the Python constant: a selection
        label is translated as a selection value, and ``env._("Paused")`` -
        which looks up a *code* string - would quietly find nothing and hand
        an Arabic reader the English word.
        """
        return dict(self._fields["sla_state"]._description_selection(self.env))

    def _sla_badge_payload(self, verdict, rtl=False):
        """Everything the SLA badge draws, translated server side."""
        self.ensure_one()
        state = verdict["state"]
        labels = self._sla_state_labels()
        payload = {
            "rtl": rtl,
            "state": state,
            # Never colour alone: the badge always carries the written verdict
            # and an icon next to the hue.
            "state_label": labels.get(state, state),
            "icon": SLA_STATE_ICON.get(state, "fa-clock-o"),
            "age": self.stage_age_display or "",
            "age_label": (
                self.env._("Waiting %s", self.stage_age_display)
                if self.stage_age_display else ""
            ),
            "role": role_label(self.env, verdict["role"]) if verdict["role"] else "",
            "role_key": verdict["role"] or "",
            "waiting_on": (
                self.env._("Waiting on %s", role_label(self.env, verdict["role"]))
                if verdict["role"] else ""
            ),
            "due_label": "",
            "overdue_label": "",
            "target_label": "",
            "escalation_label": "",
            "parties": [],
        }
        if state in ("not_applicable", "paused"):
            payload["due_label"] = (
                self.env._("The file is with the applicant; the clock is paused.")
                if state == "paused"
                else self.env._("No service level is defined for this step.")
            )
            return payload

        due = verdict["due_on"]
        payload["target_label"] = self.env._(
            "Target %s", self._format_hours(verdict["rule"].target_days * 24),
        )
        if state in ("overdue", "escalated"):
            payload["overdue_label"] = self.env._(
                "%s overdue", self._format_hours(verdict["overdue_hours"]),
            )
            payload["due_label"] = self.env._(
                "Was due %s", fields.Datetime.to_string(due),
            )
        else:
            remaining = max((due - fields.Datetime.now()).total_seconds() / 3600.0, 0.0)
            payload["due_label"] = self.env._("Due in %s", self._format_hours(remaining))
        if self.escalation_level:
            payload["escalation_label"] = (
                self.env._("Escalated to the Accreditation Manager")
                if self.escalation_level == "2"
                else self.env._("Department warned")
            )
        # The dual confirmation is the one step a single badge cannot describe:
        # two departments, two clocks, and the reader needs to know which of
        # them is the problem.
        if len(verdict["parties"]) > 1:
            payload["parties"] = [{
                "role": role_label(self.env, party["role"]),
                "role_key": party["role"],
                "state": party["state"],
                "state_label": labels.get(party["state"], party["state"]),
                "icon": SLA_STATE_ICON.get(party["state"], "fa-clock-o"),
            } for party in verdict["parties"]]
        return payload

    # ==================================================================
    # Reminders and escalation
    # ==================================================================
    def _sla_reminder_users(self, verdict):
        """Who hears about it: the blocked department, plus the manager once escalated."""
        self.ensure_one()
        users = self.env["res.users"]
        for party in verdict["parties"]:
            if party["state"] in ACTIONABLE_SLA_STATES:
                users |= self._responsible_users(party["role"])
        if verdict["state"] == "escalated":
            users |= self._responsible_users("manager")
        return users

    def _sla_activity_note(self, verdict):
        self.ensure_one()
        if verdict["overdue_hours"]:
            detail = self.env._(
                "It is %(late)s past its target and is waiting on %(role)s.",
                late=self._format_hours(verdict["overdue_hours"]),
                role=role_label(self.env, verdict["role"]),
            )
        else:
            detail = self.env._(
                "It is due on %(due)s and is waiting on %(role)s.",
                due=fields.Datetime.to_string(verdict["due_on"]),
                role=role_label(self.env, verdict["role"]),
            )
        return self.env._(
            "%(ref)s (%(partner)s) has been on “%(step)s” for %(age)s. %(detail)s",
            ref=self.name,
            partner=self.partner_id.display_name,
            step=state_label(self.env, self.state),
            age=self.stage_age_display or "",
            detail=detail,
        )

    def _sla_sync_activities(self, verdict):
        """Put exactly one accreditation-deadline to-do per responsible user.

        Idempotent by construction: the to-do is looked up by (record, type,
        assignee) and *updated* when it already exists. The scheduled job may
        therefore run every ten minutes without an officer ever collecting a
        second copy of the same reminder.
        """
        self.ensure_one()
        activity_type = self.env.ref(
            "dma_accreditation.mail_activity_type_sla", raise_if_not_found=False,
        )
        users = self._sla_reminder_users(verdict)
        if not users or not activity_type:
            return self.env["mail.activity"]

        deadline = fields.Date.to_date(verdict["due_on"]) or fields.Date.context_today(self)
        Activity = self.env["mail.activity"].sudo()
        existing = Activity.search([
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
            ("activity_type_id", "=", activity_type.id),
        ])
        by_user = {activity.user_id.id: activity for activity in existing}
        touched = Activity
        for user in users:
            # The summary and the note of an activity are *stored* text, so
            # they are composed once, in the language of the officer who will
            # read them - the scheduled job itself runs in the language of the
            # system user, which is nobody's.
            localised = self.sudo().with_context(lang=user.lang or self.env.lang)
            summary = localised.env._(
                "%(verdict)s: %(step)s",
                verdict=localised._sla_state_labels().get(verdict["state"], ""),
                step=state_label(localised.env, localised.state),
            )
            note = localised._sla_activity_note(verdict)
            activity = by_user.get(user.id)
            if activity:
                # Only ever rewrite what actually changed, so a run that finds
                # nothing new writes nothing at all.
                changes = {
                    key: value for key, value in
                    (("summary", summary), ("note", note), ("date_deadline", deadline))
                    if activity[key] != value
                }
                if changes:
                    activity.write(changes)
                touched |= activity
                continue
            touched |= localised.activity_schedule(
                act_type_xmlid="dma_accreditation.mail_activity_type_sla",
                date_deadline=deadline,
                summary=summary,
                note=note,
                user_id=user.id,
            )
        return touched

    def _sla_raise_escalations(self, verdict):
        """Record the overrun once per level, per visit to the step."""
        self.ensure_one()
        if verdict["state"] not in ("overdue", "escalated"):
            return self.env["dma.sla.escalation"]
        levels = ["1"] if verdict["state"] == "overdue" else ["1", "2"]
        Escalation = self.env["dma.sla.escalation"].sudo()
        existing = set(Escalation.search([
            ("request_id", "=", self.id),
            ("state", "=", self.state),
            ("role", "=", verdict["role"]),
            ("stage_entered_on", "=", self.stage_entered_on),
        ]).mapped("level"))
        raised = Escalation
        for level in levels:
            if level in existing:
                continue
            raised |= Escalation.create({
                "request_id": self.id,
                "state": self.state,
                "role": verdict["role"],
                "level": level,
                "stage_entered_on": self.stage_entered_on,
                "due_on": verdict["due_on"],
                "overdue_hours": verdict["overdue_hours"],
                "reason": self.env._(
                    "“%(step)s” is %(late)s past its %(target)s target "
                    "with %(role)s.",
                    step=state_label(self.env, self.state),
                    late=self._format_hours(verdict["overdue_hours"]),
                    target=self._format_hours(verdict["rule"].target_days * 24),
                    role=role_label(self.env, verdict["role"]),
                ),
            })
        # One line per level, naming the level: two identical sentences in a
        # row read as a duplicate, and the reader cannot tell that the second
        # one is the moment it reached the manager.
        levels = dict(
            Escalation._fields["level"]._description_selection(self.env)
        )
        for escalation in raised:
            self.message_post(body=self.env._(
                "%(level)s - %(reason)s",
                level=levels.get(escalation.level, ""),
                reason=escalation.reason,
            ))
        return raised

    def _sla_resolve_stale_escalations(self):
        """Close the escalations of steps the file has since left."""
        stale = self.env["dma.sla.escalation"].sudo().search([
            ("request_id", "in", self.ids),
            ("resolved_on", "=", False),
        ])
        entries = {
            request.id: (request.state, request.stage_entered_on) for request in self
        }
        closing = stale.filtered(
            lambda escalation: entries.get(escalation.request_id.id)
            != (escalation.state, escalation.stage_entered_on)
        )
        if closing:
            closing.with_context(dma_sla_engine=True).write({
                "resolved_on": fields.Datetime.now(),
            })
        return closing

    # ==================================================================
    # Scheduled job
    # ==================================================================
    @api.model
    def _cron_sla_review(self, limit=None):
        """Re-arm reminders, raise escalations and close what is settled.

        Safe to run as often as the Directorate likes: every record it writes
        is keyed so a second run over unchanged data writes nothing at all, and
        it never touches a closed or archived file.

        The whole live caseload is walked, oldest arrival first, and progress is
        committed to the scheduler after every file. That is Odoo 19's own
        batching idiom, and it is what keeps a long run correct: a plain "first
        N per run" cap would keep re-examining the same head of the queue and
        never reach the tail, because a file the job has already dealt with
        looks exactly like one it has not.
        """
        engine = self.sudo()
        # An escalation on a step somebody has meanwhile dealt with is noise on
        # a manager's screen, so those are closed first and unconditionally.
        open_escalations = self.env["dma.sla.escalation"].sudo().search([
            ("resolved_on", "=", False),
        ])
        resolved = open_escalations.request_id._sla_resolve_stale_escalations()

        live = engine.search(
            [("state", "in", list(SLA_TRACKED_STATES))],
            order="stage_entered_on asc, id asc",
            limit=limit,
        )
        Cron = self.env["ir.cron"]
        # Progress is reported to the scheduler only when the scheduler is the
        # caller: ``_commit_progress`` commits, and a commit inside a test
        # would break the transaction the test is rolling back.
        under_cron = bool(self.env.context.get("cron_id"))
        if under_cron:
            Cron._commit_progress(remaining=len(live))

        now = fields.Datetime.now()
        checked = reminded = escalated = 0
        for request in live:
            # One at a time: committing invalidates the cache, so prefetching
            # the rest of the batch after every commit would undo the point.
            request = request[0]
            try:
                verdict = request._sla_verdict(now=now)
                if verdict["state"] in ACTIONABLE_SLA_STATES:
                    if request._sla_sync_activities(verdict):
                        reminded += 1
                    if request._sla_raise_escalations(verdict):
                        escalated += 1
            except Exception:  # noqa: BLE001 - one bad file must not stop the run
                _logger.exception(
                    "DMA service level review failed on %s", request.display_name,
                )
            checked += 1
            if under_cron and not Cron._commit_progress(processed=1):
                # Out of runtime. The scheduler re-runs the job straight away
                # and it picks up where it left off.
                _logger.info(
                    "DMA service level review: out of time after %s of %s file(s)",
                    checked, len(live),
                )
                break
        _logger.info(
            "DMA service level review: %s file(s) checked, %s reminded, %s escalated, "
            "%s escalation(s) closed", checked, reminded, escalated, len(resolved),
        )
        return True

    # ==================================================================
    # Keeping the stored deadline honest when the configuration changes
    # ==================================================================
    @api.model
    def _sla_recompute_open_requests(self):
        """Recompute the stored deadlines after the service levels were edited.

        ``sla_due_on`` cannot declare a dependency on ``dma.sla.rule`` - there
        is no field path from a request to the rule table - so the rule model
        calls this instead. Only live files are touched; a decided one has no
        deadline to move.
        """
        live = self.sudo().search([("state", "in", list(SLA_TRACKED_STATES))])
        live.modified(["stage_entered_on"])
        return len(live)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_open_escalations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Escalations"),
            "res_model": "dma.sla.escalation",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
            "context": {"create": False},
        }
