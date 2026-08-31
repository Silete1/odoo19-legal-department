"""The server half of مكتبي / My Office.

The screen asks one question - *what requires my action now* - and the answer
has to be composed on the server, in one round trip, for three reasons that
have nothing to do with performance.

**The queue crosses eight registers.** A legal department's day is not a
``legal.case`` list. It is a government file waiting on a step, a departmental
request waiting on a response, a contract in internal approval, an opinion in
review, a lawsuit with a hearing on Sunday, an incoming letter nobody has
registered, a statutory obligation whose period closes on Thursday and a
commercial registration certificate that expires in three weeks. Only one
place in the stack can read all eight through the reader's own record rules
and merge them into one ordering, and it is here.

**"Mine" is a server question.** Ownership in this suite is sometimes a
``user_id`` and sometimes a *desk*: ``legal.case.pending_group_id`` names the
group whose members may make the next move, which is how a clerk covering for
a colleague sees the queue without anybody reassigning sixty records. A
browser cannot evaluate that, and a browser that guesses produces a queue the
server would not agree with.

**The reason belongs to the domain, not to the widget.** Every row carries a
``reason`` composed here - "ينقص مستند مصدق", "تجاوز موعد الرد بـ ٤ أيام",
"بانتظار توقيعك" - because *why this is on your desk* is the single most
useful column on the screen and it is knowable only from the record.

Everything the payload offers is built through the ORM **as the reader**, so
the record rules and the read-only auditor ACLs apply untouched; nothing here
uses ``sudo()``.
"""

import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: How far ahead the agenda looks. Three weeks is the horizon a legal
#: department actually plans over: a hearing is set a fortnight out, a
#: statutory filing window is a month, and anything past that is a report.
AGENDA_HORIZON_DAYS = 21

#: The queue is a working list, not an archive. Beyond this the reader is
#: better served by the filtered list view the "open all" control leads to.
QUEUE_LIMIT = 40

#: Rows per secondary tab. Secondary information is context, and context that
#: needs scrolling has stopped being context.
SECONDARY_LIMIT = 8

#: Sort buckets. A row's bucket dominates its priority and its priority
#: dominates its date, so an overdue normal file still outranks a critical one
#: that is not yet due - which is the order a legal office actually works in.
BUCKET_OVERDUE = 0
BUCKET_TODAY = 1
BUCKET_SOON = 2
BUCKET_LATER = 3
BUCKET_UNDATED = 4


class LegalOffice(models.AbstractModel):
    """The payload behind the ``legal_office`` client action.

    Inherits :class:`legal.dashboard` prototypally for its helper layer - the
    soft-model lookups, the degrading search/count, the numeral rendering, the
    working-day arithmetic and the drill-through builders. Those helpers were
    written for the older desk and are correct; duplicating them here to avoid
    an inheritance line would mean two implementations of "which digits does
    this company use" that could disagree.
    """

    _name = "legal.office"
    _inherit = "legal.dashboard"
    _description = "My Office Workspace"

    # ==================================================================
    # ENTRY POINT
    # ==================================================================
    @api.model
    def get_office_data(self):
        """One call, one screen.

        Ordered so that a failure late in the composition still leaves the
        reader with the parts that matter most: the role and the queue are
        built first, and every optional region records its own absence in
        ``degraded`` rather than raising.
        """
        degraded = []
        role = self._office_role()
        today = fields.Date.context_today(self)

        queue = self._office_queue(role, degraded)
        return {
            "rtl": self._rtl(),
            "numerals": self._numerals(),
            "role": role,
            "header": self._office_header(role, today),
            "signals": self._office_signals(role, today, degraded),
            "queue": queue,
            "agenda": self._office_agenda(role, today, degraded),
            "secondary": self._office_secondary(role, today, degraded),
            "create": self._office_create(role),
            "degraded": degraded,
        }

    # ==================================================================
    # ROLE
    # ==================================================================
    def _office_role(self):
        """The reader's seat, named once.

        ``_role_brief`` already resolves the five-rung ladder from group
        membership; this adds the single ``key`` the whole screen switches on,
        so that neither the templates nor the collectors below re-derive the
        role from four booleans and reach a different answer.
        """
        brief = dict(self._role_brief())
        if brief["is_auditor"]:
            key = "auditor"
        elif brief["is_manager"]:
            key = "manager"
        elif brief["is_approver"]:
            key = "approver"
        elif brief["is_officer"]:
            key = "officer"
        else:
            key = "clerk"
        brief["key"] = key
        brief["read_only"] = not brief["can_write"]
        return brief

    def _office_header(self, role, today):
        """Context, and nothing that is not context.

        No hero, no welcome, no giant figure. The header answers "whose desk is
        this, and what is today", because those two facts change what the rest
        of the screen means and neither one is worth a card.
        """
        user = self.env.user
        lang = self.env["res.lang"]._lang_get(self.env.lang)
        try:
            date_label = today.strftime(lang.date_format)
        except Exception:  # noqa: BLE001 - a malformed lang format is not fatal
            date_label = fields.Date.to_string(today)
        return {
            "title": self.env._("My Desk"),
            "user_name": user.name,
            "role_label": role["label"],
            # The header date is read, not quoted, so it follows the company
            # numeral setting like the rest of the prose on the screen.
            "date_label": self._digits(date_label),
            "day_label": self._weekday_label(today),
            "avatar": f"/web/image/res.users/{user.id}/avatar_128",
            "company": self.env.company.display_name,
        }

    def _weekday_label(self, day):
        names = [
            self.env._("Monday"), self.env._("Tuesday"), self.env._("Wednesday"),
            self.env._("Thursday"), self.env._("Friday"), self.env._("Saturday"),
            self.env._("Sunday"),
        ]
        return names[day.weekday()]

    # ==================================================================
    # THE ATTENTION STRIP
    # ==================================================================
    def _office_signals(self, role, today, degraded):
        """Three to five indicators, each one a filtered list behind a number.

        Not KPIs. A KPI is a figure you watch; these are queues you empty, and
        the difference shows in what happens when you click one. Every signal
        here opens the exact records it counted - never a chart, never a
        summary - and a signal that cannot open its records is not shown.

        The set is chosen per role because "needs attention" means different
        things at different desks, and a screen that shows the clerk the
        approver's backlog has taught them to ignore the strip by Wednesday.
        """
        builders = {
            "clerk": self._signals_clerk,
            "officer": self._signals_officer,
            "approver": self._signals_approver,
            "manager": self._signals_manager,
            "auditor": self._signals_auditor,
        }
        try:
            items = builders[role["key"]](today)
        except Exception:  # noqa: BLE001
            _logger.warning("legal.office could not build the attention strip",
                            exc_info=True)
            degraded.append(self.env._("The attention indicators could not be computed."))
            items = []
        return {
            "title": self.env._("Needs attention"),
            "items": [item for item in items if item],
        }

    def _signal(self, key, label, count, tone, icon, action, hint=""):
        """One indicator, or nothing at all.

        A ``None`` count means the reader may not ask that model - the entry
        disappears rather than reporting a confident zero it has not earned.
        """
        if count is None:
            return None
        return {
            "key": key,
            "label": label,
            "count": count,
            "count_label": self._digits(count),
            "tone": tone if count else "neutral",
            "icon": icon,
            "action": action if count else False,
            "hint": hint,
        }

    def _signals_clerk(self, today):
        """Intake. The clerk owns the door, so the strip is about the door."""
        Corr = self._model("legal.correspondence")
        Request = self._model("legal.request")
        Case = self._model("legal.case")
        Doc = self._model("legal.document")
        unregistered = [("state", "=", "draft")]
        unlinked = [("state", "=", "registered"), ("direction", "=", "in"),
                    ("case_id", "=", False), ("is_contact_note", "=", False)]
        unassigned = [("state", "in", ("received", "triage")),
                      ("assigned_officer_id", "=", False)]
        blocked = [("is_closed", "=", False), ("blocker_count", ">", 0)]
        expiring = [("state", "=", "active"), ("expiry_date", "!=", False),
                    ("expiry_date", "<=", today + timedelta(days=30))]
        return [
            self._signal(
                "unregistered", self.env._("Awaiting registration"),
                self._optional_count(Corr, unregistered), "critical", "fa-inbox",
                self._open_action("legal.correspondence",
                                  self.env._("Awaiting registration"), unregistered),
                self.env._("Drafted but not yet given a register number."),
            ),
            self._signal(
                "unlinked", self.env._("Not on a file"),
                self._optional_count(Corr, unlinked), "warning", "fa-unlink",
                self._open_action("legal.correspondence",
                                  self.env._("Not on a file"), unlinked),
                self.env._("Registered incoming letters with no matter attached."),
            ),
            self._signal(
                "unassigned", self.env._("No officer named"),
                self._optional_count(Request, unassigned), "warning", "fa-user-o",
                self._open_action("legal.request",
                                  self.env._("No officer named"), unassigned),
                self.env._("Requests that have arrived and nobody owns."),
            ),
            self._signal(
                "blocked", self.env._("Missing documents"),
                self._optional_count(Case, blocked), "warning", "fa-file-o",
                self._open_action("legal.case",
                                  self.env._("Missing documents"), blocked),
                self.env._("Files that cannot move until a paper is produced."),
            ),
            self._signal(
                "renewals", self.env._("Renewals within 30 days"),
                self._optional_count(Doc, expiring), "warning", "fa-refresh",
                self._open_action("legal.document",
                                  self.env._("Renewals within 30 days"), expiring),
                self.env._("Company papers whose validity ends soon."),
            ),
        ]

    def _signals_officer(self, today):
        """Follow-up. Two clocks - ours and theirs - and the blocked middle."""
        Deadline = self._model("legal.deadline")
        Case = self._model("legal.case")
        Corr = self._model("legal.correspondence")
        mine = [("user_id", "=", self.env.uid)]
        overdue = mine + [("state", "=", "overdue")]
        today_due = mine + [("date_due", "=", today)]
        week = mine + [("date_due", ">", today),
                       ("date_due", "<=", today + timedelta(days=7))]
        at_body = self._my_turn_domain(Case) + [("is_closed", "=", False),
                                                ("kind", "=", "at_body")]
        blocked = self._my_turn_domain(Case) + [("is_closed", "=", False),
                                                ("blocker_count", ">", 0)]
        no_reply = [("reply_expected", "=", True), ("state", "=", "registered"),
                    ("reply_due_on", "<", today), ("user_id", "=", self.env.uid)]
        return [
            self._signal(
                "overdue", self.env._("Overdue"),
                self._optional_count(Deadline, overdue), "critical", "fa-exclamation-triangle",
                self._open_action("legal.deadline", self.env._("Overdue"), overdue,
                                  views=[[False, "list"], [False, "calendar"]]),
                self.env._("Every clock of yours whose date has passed."),
            ),
            self._signal(
                "today", self.env._("Due today"),
                self._optional_count(Deadline, today_due), "warning", "fa-calendar-check-o",
                self._open_action("legal.deadline", self.env._("Due today"), today_due,
                                  views=[[False, "list"], [False, "calendar"]]),
            ),
            self._signal(
                "week", self.env._("Within seven days"),
                self._optional_count(Deadline, week), "waiting", "fa-calendar-o",
                self._open_action("legal.deadline", self.env._("Within seven days"), week,
                                  views=[[False, "list"], [False, "calendar"]]),
            ),
            self._signal(
                "at_body", self.env._("With the body"),
                self._optional_count(Case, at_body), "waiting", "fa-institution",
                self._open_action("legal.case", self.env._("With the body"), at_body),
                self.env._("Our clock is stopped; theirs is running."),
            ),
            self._signal(
                "no_reply", self.env._("Reply overdue"),
                self._optional_count(Corr, no_reply), "critical", "fa-reply",
                self._open_action("legal.correspondence",
                                  self.env._("Reply overdue"), no_reply),
                self.env._("We wrote, the answer date has passed, chase it."),
            ),
        ]

    def _signals_approver(self, today):
        """The signature desk. Everything here is somebody else waiting on you."""
        Case = self._model("legal.case")
        Request = self._model("legal.request")
        Contract = self._model("legal.contract")
        Opinion = self._model("legal.opinion")
        signature = self._signature_queue_domain(Case)
        requests = [("state", "=", "ready_for_approval")]
        contracts = [("state", "in", ("internal_approval", "to_sign"))]
        opinions = [("state", "in", ("review", "approval"))]
        returned = [("state", "in", ("assigned", "in_progress")),
                    ("return_reason", "!=", False),
                    ("assigned_officer_id", "=", self.env.uid)]
        return [
            self._signal(
                "signature", self.env._("Awaiting your signature"),
                self._optional_count(Case, signature), "critical", "fa-pencil-square-o",
                self._open_action("legal.case",
                                  self.env._("Awaiting your signature"), signature),
                self.env._("Files whose closing move is yours to make."),
            ),
            self._signal(
                "requests", self.env._("Requests to decide"),
                self._optional_count(Request, requests), "warning", "fa-gavel",
                self._open_action("legal.request",
                                  self.env._("Requests to decide"), requests),
            ),
            self._signal(
                "contracts", self.env._("Contracts to sign off"),
                self._optional_count(Contract, contracts), "warning", "fa-file-text-o",
                self._open_action("legal.contract",
                                  self.env._("Contracts to sign off"), contracts),
            ),
            self._signal(
                "opinions", self.env._("Opinions to review"),
                self._optional_count(Opinion, opinions), "waiting", "fa-balance-scale",
                self._open_action("legal.opinion",
                                  self.env._("Opinions to review"), opinions),
            ),
            self._signal(
                "returned", self.env._("Returned to you"),
                self._optional_count(Request, returned), "waiting", "fa-undo",
                self._open_action("legal.request", self.env._("Returned to you"), returned),
            ),
        ]

    def _signals_manager(self, today):
        """The room, not the desk. Every figure is something only you can unblock."""
        Deadline = self._model("legal.deadline")
        Case = self._model("legal.case")
        Request = self._model("legal.request")
        Lawsuit = self._model("legal.lawsuit")
        Contract = self._model("legal.contract")
        overdue = [("state", "=", "overdue")]
        unowned = ["|", ("user_id", "=", False), ("user_id", "=", None)]
        unassigned_case = [("is_closed", "=", False), ("user_id", "=", False)]
        unassigned_req = [("state", "in", ("received", "triage")),
                          ("assigned_officer_id", "=", False)]
        risk = [("is_closed", "=", False), ("risk", "in", ("high", "critical"))]
        expiring = [("is_closed", "=", False), ("expiry_date", "!=", False),
                    ("expiry_date", "<=", today + timedelta(days=60))]
        del unowned  # kept for the reader: the deadline board has no owner filter here
        return [
            self._signal(
                "overdue", self.env._("Overdue in the department"),
                self._optional_count(Deadline, overdue), "critical", "fa-exclamation-triangle",
                self._open_action("legal.deadline",
                                  self.env._("Overdue in the department"), overdue,
                                  views=[[False, "list"], [False, "calendar"]]),
                self.env._("Every clock in Legal Affairs whose date has passed."),
            ),
            self._signal(
                "unassigned", self.env._("Nobody owns it"),
                self._optional_count(Case, unassigned_case), "critical", "fa-user-o",
                self._open_action("legal.case", self.env._("Nobody owns it"),
                                  unassigned_case),
                self.env._("Open files with no named officer."),
            ),
            self._signal(
                "intake", self.env._("Unassigned requests"),
                self._optional_count(Request, unassigned_req), "warning", "fa-inbox",
                self._open_action("legal.request",
                                  self.env._("Unassigned requests"), unassigned_req),
            ),
            self._signal(
                "risk", self.env._("High-risk litigation"),
                self._optional_count(Lawsuit, risk), "warning", "fa-balance-scale",
                self._open_action("legal.lawsuit",
                                  self.env._("High-risk litigation"), risk),
            ),
            self._signal(
                "expiring", self.env._("Contracts ending in 60 days"),
                self._optional_count(Contract, expiring), "waiting", "fa-hourglass-end",
                self._open_action("legal.contract",
                                  self.env._("Contracts ending in 60 days"), expiring),
            ),
        ]

    def _signals_auditor(self, today):
        """Oversight, and not one control that changes anything.

        The counts are the same facts the manager sees; what is withheld is
        every affordance that would write. The auditor's drill-through opens a
        list the ACLs already make read-only, so the read-only guarantee is the
        server's, not the template's.
        """
        Deadline = self._model("legal.deadline")
        Log = self._model("legal.action.log")
        Case = self._model("legal.case")
        Corr = self._model("legal.correspondence")
        overdue = [("state", "=", "overdue")]
        week_log = [("create_date", ">=", fields.Datetime.to_string(
            fields.Datetime.now() - timedelta(days=7)))]
        open_cases = [("is_closed", "=", False)]
        voided = [("state", "=", "void")]
        return [
            self._signal(
                "overdue", self.env._("Overdue in the department"),
                self._optional_count(Deadline, overdue), "critical", "fa-exclamation-triangle",
                self._open_action("legal.deadline",
                                  self.env._("Overdue in the department"), overdue,
                                  views=[[False, "list"], [False, "calendar"]]),
            ),
            self._signal(
                "open", self.env._("Open files"),
                self._optional_count(Case, open_cases), "waiting", "fa-folder-open-o",
                self._open_action("legal.case", self.env._("Open files"), open_cases),
            ),
            self._signal(
                "trail", self.env._("Actions this week"),
                self._optional_count(Log, week_log), "neutral", "fa-history",
                self._open_action("legal.action.log",
                                  self.env._("Actions this week"), week_log),
                self.env._("Every recorded move, immutable."),
            ),
            self._signal(
                "void", self.env._("Voided register entries"),
                self._optional_count(Corr, voided), "warning", "fa-ban",
                self._open_action("legal.correspondence",
                                  self.env._("Voided register entries"), voided),
                self.env._("Nothing is deleted; a cancellation is a state."),
            ),
        ]

    # ==================================================================
    # THE WORK QUEUE - the centre of the screen
    # ==================================================================
    def _office_queue(self, role, degraded):
        """One list, eight registers, ordered by when it hurts.

        Each collector below returns rows already carrying their reason and
        their date; the merge is a single sort on ``(bucket, -priority, date,
        -age)``. That ordering is the argument of the whole screen: an overdue
        ordinary matter outranks a critical one that is not yet due, because
        the first is already costing the company something and the second is
        not.
        """
        collectors = self._queue_plan(role["key"])
        rows, scopes = [], []
        for spec in collectors:
            try:
                found = spec["build"]()
            except Exception:  # noqa: BLE001
                _logger.warning("legal.office queue source %s failed", spec["key"],
                                exc_info=True)
                degraded.append(self.env._(
                    "The %(source)s part of your queue is unavailable.",
                    source=spec["label"]))
                continue
            if found is None:
                continue
            rows.extend(found)
            if found:
                scopes.append({"key": spec["key"], "label": spec["label"],
                               "count": len(found),
                               "count_label": self._digits(len(found)),
                               "icon": spec["icon"]})
        rows.sort(key=lambda row: (row["bucket"], -row["priority"],
                                   row["sort_date"] or "9999-12-31", -row["age_days"]))
        total = len(rows)
        rows = rows[:QUEUE_LIMIT]
        for index, row in enumerate(rows):
            row["index"] = index
        titles = {
            "clerk": self.env._("Arriving and to register"),
            "officer": self.env._("Needs action from me"),
            "approver": self.env._("Awaiting my decision"),
            "manager": self.env._("Needs a decision from me"),
            "auditor": self.env._("The department's live work"),
        }
        hints = {
            "clerk": self.env._("What came through the door and has not been placed yet."),
            "officer": self.env._("Every register you own, in the order the clock bites."),
            "approver": self.env._("Somebody is waiting on your word for each of these."),
            "manager": self.env._("Unowned, overdue or risky work that only you can move."),
            "auditor": self.env._("Read-only. Open any row to inspect its trail."),
        }
        return {
            "title": titles[role["key"]],
            "hint": hints[role["key"]],
            "scopes": ([{"key": "all", "label": self.env._("All"), "count": total,
                         "count_label": self._digits(total), "icon": "fa-list"}] + scopes)
                      if len(scopes) > 1 else [],
            "rows": rows,
            "total": total,
            "shown": len(rows),
            "truncated": total > len(rows),
            "more_label": self.env._("%(n)s more", n=self._digits(max(total - len(rows), 0))),
            "empty": self._queue_empty(role),
        }

    def _queue_empty(self, role):
        """An empty queue is good news and should read as good news.

        Not a 300px illustration in the middle of the working area - one line
        that says the desk is clear and one that says what would put something
        on it, so a new reader does not wonder whether the screen is broken.
        """
        messages = {
            "clerk": (self.env._("Nothing is waiting to be registered."),
                      self.env._("A letter appears here the moment it is drafted or arrives unplaced.")),
            "officer": (self.env._("Your desk is clear."),
                        self.env._("A matter appears here when it reaches a step you own or a date you hold.")),
            "approver": (self.env._("Nothing is waiting on your signature."),
                         self.env._("A file appears here when it stands at a step whose closing move is yours.")),
            "manager": (self.env._("Nothing needs your intervention."),
                        self.env._("Unowned, overdue and high-risk work is routed here automatically.")),
            "auditor": (self.env._("No live work to inspect."),
                        self.env._("Open matters and recent moves appear here as they happen.")),
        }
        title, hint = messages[role["key"]]
        return {"title": title, "hint": hint}

    def _queue_plan(self, key):
        """Which registers feed which desk, and in what character.

        This table *is* the role differentiation. The five desks do not read
        the same list with different numbers on it; they read different lists,
        because a clerk who has never advanced a step should not be shown a
        signature queue and a manager should not be shown the fifty files that
        are quietly proceeding exactly as they should.
        """
        plans = {
            "clerk": [
                ("correspondence", self._queue_correspondence_intake),
                ("request", self._queue_requests_intake),
                ("case", self._queue_cases_blocked),
                ("document", self._queue_documents_renewal),
            ],
            "officer": [
                ("case", self._queue_cases_mine),
                ("request", self._queue_requests_mine),
                ("opinion", self._queue_opinions_mine),
                ("lawsuit", self._queue_lawsuits_mine),
                ("contract", self._queue_contracts_mine),
                ("correspondence", self._queue_correspondence_chase),
                ("obligation", self._queue_obligations_mine),
            ],
            "approver": [
                ("case", self._queue_cases_signature),
                ("request", self._queue_requests_approval),
                ("contract", self._queue_contracts_approval),
                ("opinion", self._queue_opinions_approval),
            ],
            "manager": [
                ("case", self._queue_cases_manager),
                ("request", self._queue_requests_manager),
                ("lawsuit", self._queue_lawsuits_manager),
                ("contract", self._queue_contracts_manager),
                ("obligation", self._queue_obligations_manager),
            ],
            "auditor": [
                ("case", self._queue_cases_oversight),
                ("request", self._queue_requests_oversight),
                ("contract", self._queue_contracts_oversight),
            ],
        }
        meta = {
            "case": (self.env._("Government files"), "fa-folder-open-o"),
            "request": (self.env._("Requests"), "fa-inbox"),
            "contract": (self.env._("Contracts"), "fa-file-text-o"),
            "opinion": (self.env._("Opinions"), "fa-balance-scale"),
            "lawsuit": (self.env._("Litigation"), "fa-gavel"),
            "correspondence": (self.env._("Correspondence"), "fa-envelope-o"),
            "obligation": (self.env._("Obligations"), "fa-calendar-check-o"),
            "document": (self.env._("Documents"), "fa-id-card-o"),
        }
        plan = []
        for key_, build in plans[key]:
            label, icon = meta[key_]
            plan.append({"key": key_, "label": label, "icon": icon, "build": build})
        return plan

    # ------------------------------------------------------------------
    # The row
    # ------------------------------------------------------------------
    def _queue_row(self, record, *, kind, reference, subject, state_label,
                   state_tone="neutral", reason="", reason_tone="neutral",
                   due=None, priority=0, owner="", since=None):
        """One work row, with everything the reader needs to triage it unopened.

        Six facts and no more: what kind of thing it is, its reference, its
        subject, where it stands, when it bites, and *why it is here*. A
        seventh column is a column somebody stops reading.
        """
        today = fields.Date.context_today(self)
        due_date = fields.Date.to_date(due) if due else None
        bucket, due_label, due_tone = self._due_shape(due_date, today)
        age_days = 0
        if since:
            try:
                age_days = (today - fields.Date.to_date(since)).days
            except Exception:  # noqa: BLE001
                age_days = 0
        meta = self._queue_plan_meta(kind)
        return {
            "id": f"{record._name}:{record.id}",
            "model": record._name,
            "res_id": record.id,
            "kind": kind,
            "kind_label": meta[0],
            "icon": meta[1],
            "reference": reference or "",
            "subject": subject or "",
            "state_label": state_label or "",
            "state_tone": state_tone,
            "reason": reason or "",
            "reason_tone": reason_tone,
            "due_label": due_label,
            "due_tone": due_tone,
            "priority": int(priority or 0),
            "owner": owner or "",
            "age_days": age_days,
            "age_label": self._digits(age_days) if age_days else "",
            "bucket": bucket,
            "sort_date": fields.Date.to_string(due_date) if due_date else None,
            "open": self._open_record(record._name, record.id),
        }

    def _queue_plan_meta(self, kind):
        labels = {
            "case": (self.env._("File"), "fa-folder-open-o"),
            "request": (self.env._("Request"), "fa-inbox"),
            "contract": (self.env._("Contract"), "fa-file-text-o"),
            "opinion": (self.env._("Opinion"), "fa-balance-scale"),
            "lawsuit": (self.env._("Lawsuit"), "fa-gavel"),
            "correspondence": (self.env._("Letter"), "fa-envelope-o"),
            "obligation": (self.env._("Obligation"), "fa-calendar-check-o"),
            "document": (self.env._("Document"), "fa-id-card-o"),
        }
        return labels.get(kind, (kind, "fa-circle-o"))

    def _due_shape(self, due_date, today):
        """The date, said the way an office says it.

        "متأخر ٣ أيام" and "اليوم" are what people act on; an ISO date is what
        they have to subtract from today's date in their head first. The bucket
        that comes back with the label is what the sort uses, so the wording
        and the ordering can never disagree.
        """
        if not due_date:
            return BUCKET_UNDATED, "", "neutral"
        delta = (due_date - today).days
        if delta < 0:
            return (BUCKET_OVERDUE,
                    self.env._("%(n)s day(s) late", n=self._digits(-delta)),
                    "critical")
        if delta == 0:
            return BUCKET_TODAY, self.env._("Today"), "critical"
        if delta == 1:
            return BUCKET_SOON, self.env._("Tomorrow"), "warning"
        if delta <= 7:
            return (BUCKET_SOON,
                    self.env._("in %(n)s days", n=self._digits(delta)), "warning")
        # A far date is shown as a date, and a date is never run through the
        # numeral converter: the suite's own rule is that anything quoted over
        # the telephone or typed into a search box stays in Western figures.
        return BUCKET_LATER, fields.Date.to_string(due_date), "neutral"

    # ------------------------------------------------------------------
    # Collectors - legal.case
    # ------------------------------------------------------------------
    def _queue_cases_mine(self):
        """Files standing on a step this reader may move.

        ``kind != at_body`` is the whole filter: a file lodged at the Tax
        Commission is not work, it is waiting, and it belongs in the secondary
        strip rather than in a list titled "needs action from me". Putting it
        here is how a queue of nine real items becomes a queue of forty that
        nobody triages.
        """
        Case = self._model("legal.case")
        if Case is None:
            return []
        domain = self._my_turn_domain(Case) + [("is_closed", "=", False),
                                               ("kind", "!=", "at_body")]
        records = self._safe_search(Case, domain, order="sla_due_on asc, id desc",
                                    limit=QUEUE_LIMIT)
        return [self._case_row(record) for record in records]

    def _queue_cases_signature(self):
        Case = self._model("legal.case")
        if Case is None:
            return []
        records = self._safe_search(Case, self._signature_queue_domain(Case),
                                    order="sla_due_on asc, id desc", limit=QUEUE_LIMIT)
        return [self._case_row(record, reason=self.env._("The closing move is yours."),
                               reason_tone="critical") for record in records]

    def _queue_cases_blocked(self):
        """The clerk's slice: files stopped for want of a paper."""
        Case = self._model("legal.case")
        if Case is None:
            return []
        domain = [("is_closed", "=", False), ("blocker_count", ">", 0)]
        records = self._safe_search(Case, domain, order="write_date desc",
                                    limit=QUEUE_LIMIT)
        return [self._case_row(record) for record in records]

    def _queue_cases_manager(self):
        """Only what a manager can personally unblock: unowned, or breached."""
        Case = self._model("legal.case")
        if Case is None:
            return []
        # "overdue" and "escalated" are the two breached values in
        # SLA_STATE_SELECTION. An earlier draft named "breached"/"late", which
        # match nothing, so this queue quietly only ever found unowned files.
        domain = ["&", ("is_closed", "=", False),
                  "|", ("user_id", "=", False),
                  ("sla_state", "in", ("overdue", "escalated"))]
        records = self._safe_search(Case, domain, order="sla_due_on asc, id desc",
                                    limit=QUEUE_LIMIT)
        rows = []
        for record in records:
            reason = (self.env._("No officer is named on it.") if not record.user_id
                      else self.env._("The service level has been breached."))
            rows.append(self._case_row(record, reason=reason, reason_tone="critical"))
        return rows

    def _queue_cases_oversight(self):
        Case = self._model("legal.case")
        if Case is None:
            return []
        records = self._safe_search(Case, [("is_closed", "=", False)],
                                    order="write_date desc", limit=QUEUE_LIMIT)
        return [self._case_row(record) for record in records]

    def _case_row(self, record, reason=None, reason_tone=None):
        """A file, and why it is stuck.

        The reason is read off the engine rather than guessed: the case model
        already computes ``blocker_summary`` for the missing-document case and
        ``ready_to_advance`` for the opposite, so the row says what the record
        knows instead of restating its state in different words.
        """
        if reason is None:
            if record.blocker_count:
                reason = record.blocker_summary or self.env._("A required document is missing.")
                reason_tone = "critical"
            elif record.ready_to_advance:
                reason = self.env._("Ready for its next step.")
                reason_tone = "calm"
            else:
                reason = ""
                reason_tone = "neutral"
        due = record.sla_due_on and fields.Date.to_date(record.sla_due_on) or None
        return self._queue_row(
            record, kind="case",
            reference=record.name,
            subject=record.subject or record.display_name,
            state_label=record.step_id.display_name if record.step_id else "",
            state_tone="waiting" if record.kind == "at_body" else "neutral",
            reason=reason, reason_tone=reason_tone or "neutral",
            due=due,
            priority=2 if record.priority in ("1", 1, True) else 0,
            owner=record.user_id.display_name if record.user_id else "",
            since=record.date_open,
        )

    # ------------------------------------------------------------------
    # Collectors - legal.request
    # ------------------------------------------------------------------
    def _queue_requests_mine(self):
        Request = self._model("legal.request")
        if Request is None:
            return []
        domain = [("assigned_officer_id", "=", self.env.uid),
                  ("state", "in", ("assigned", "in_progress", "waiting_requester"))]
        records = self._safe_search(Request, domain,
                                    order="target_response_date asc, id desc",
                                    limit=QUEUE_LIMIT)
        return [self._request_row(record) for record in records]

    def _queue_requests_intake(self):
        Request = self._model("legal.request")
        if Request is None:
            return []
        domain = ["|", ("state", "in", ("draft", "received")),
                  "&", ("state", "=", "triage"), ("assigned_officer_id", "=", False)]
        records = self._safe_search(Request, domain, order="request_date asc, id desc",
                                    limit=QUEUE_LIMIT)
        return [self._request_row(record,
                                  reason=self.env._("Arrived and not yet routed."),
                                  reason_tone="warning") for record in records]

    def _queue_requests_approval(self):
        Request = self._model("legal.request")
        if Request is None:
            return []
        records = self._safe_search(Request, [("state", "=", "ready_for_approval")],
                                    order="target_response_date asc, id desc",
                                    limit=QUEUE_LIMIT)
        return [self._request_row(record,
                                  reason=self.env._("A decision is required from you."),
                                  reason_tone="critical") for record in records]

    def _queue_requests_manager(self):
        Request = self._model("legal.request")
        if Request is None:
            return []
        domain = ["|",
                  "&", ("state", "in", ("received", "triage")),
                  ("assigned_officer_id", "=", False),
                  "&", ("is_overdue", "=", True),
                  ("state", "not in", ("closed", "cancelled", "approved"))]
        records = self._safe_search(Request, domain,
                                    order="target_response_date asc, id desc",
                                    limit=QUEUE_LIMIT)
        rows = []
        for record in records:
            reason = (self.env._("Nobody is assigned to it.")
                      if not record.assigned_officer_id
                      else self.env._("Past its response date."))
            rows.append(self._request_row(record, reason=reason, reason_tone="critical"))
        return rows

    def _queue_requests_oversight(self):
        Request = self._model("legal.request")
        if Request is None:
            return []
        domain = [("state", "not in", ("closed", "cancelled"))]
        records = self._safe_search(Request, domain, order="write_date desc",
                                    limit=QUEUE_LIMIT)
        return [self._request_row(record) for record in records]

    def _request_row(self, record, reason=None, reason_tone=None):
        if reason is None:
            if record.is_overdue:
                reason = self.env._("Past its response date.")
                reason_tone = "critical"
            elif record.return_reason and record.state in ("assigned", "in_progress"):
                reason = self.env._("Returned for correction: %(why)s",
                                    why=(record.return_reason or "")[:90])
                reason_tone = "warning"
            else:
                reason = record.requesting_department or ""
                reason_tone = "neutral"
        return self._queue_row(
            record, kind="request",
            reference=record.reference or "",
            subject=record.subject or record.display_name,
            state_label=self._selection_label(record, "state"),
            state_tone=self._request_state_tone(record.state),
            reason=reason, reason_tone=reason_tone or "neutral",
            due=record.target_response_date,
            priority={"low": 0, "normal": 0, "high": 1, "urgent": 2}.get(record.urgency, 0),
            owner=record.assigned_officer_id.display_name if record.assigned_officer_id else "",
            since=record.request_date,
        )

    def _request_state_tone(self, state):
        if state in ("waiting_requester", "waiting_external"):
            return "waiting"
        if state == "ready_for_approval":
            return "warning"
        if state in ("approved", "closed"):
            return "calm"
        return "neutral"

    # ------------------------------------------------------------------
    # Collectors - legal.contract
    # ------------------------------------------------------------------
    def _queue_contracts_mine(self):
        Contract = self._model("legal.contract")
        if Contract is None:
            return []
        domain = ["&", ("state", "in", ("received", "legal_review", "negotiation")),
                  "|", ("legal_officer_id", "=", self.env.uid),
                  ("internal_owner_id", "=", self.env.uid)]
        records = self._safe_search(Contract, domain, order="write_date desc",
                                    limit=QUEUE_LIMIT)
        return [self._contract_row(record) for record in records]

    def _queue_contracts_approval(self):
        Contract = self._model("legal.contract")
        if Contract is None:
            return []
        records = self._safe_search(Contract,
                                    [("state", "in", ("internal_approval", "to_sign"))],
                                    order="write_date desc", limit=QUEUE_LIMIT)
        return [self._contract_row(record,
                                   reason=self.env._("Waiting on internal sign-off."),
                                   reason_tone="critical") for record in records]

    def _queue_contracts_manager(self):
        Contract = self._model("legal.contract")
        if Contract is None:
            return []
        today = fields.Date.context_today(self)
        domain = ["&", ("is_closed", "=", False),
                  "|", ("risk", "in", ("high", "critical")),
                  "&", ("expiry_date", "!=", False),
                  ("expiry_date", "<=", today + timedelta(days=60))]
        records = self._safe_search(Contract, domain, order="expiry_date asc, id desc",
                                    limit=QUEUE_LIMIT)
        rows = []
        for record in records:
            reason = (self.env._("High risk, and still live.")
                      if record.risk in ("high", "critical")
                      else self.env._("Ends within sixty days; decide on renewal."))
            rows.append(self._contract_row(record, reason=reason, reason_tone="warning"))
        return rows

    def _queue_contracts_oversight(self):
        Contract = self._model("legal.contract")
        if Contract is None:
            return []
        records = self._safe_search(Contract, [("is_closed", "=", False)],
                                    order="write_date desc", limit=QUEUE_LIMIT)
        return [self._contract_row(record) for record in records]

    def _contract_row(self, record, reason=None, reason_tone=None):
        if reason is None:
            if record.obligation_overdue_count:
                reason = self.env._("%(n)s obligation(s) overdue.",
                                    n=self._digits(record.obligation_overdue_count))
                reason_tone = "critical"
            else:
                reason = record.counterparty_id.display_name if record.counterparty_id else ""
                reason_tone = "neutral"
        return self._queue_row(
            record, kind="contract",
            reference=record.name or "",
            subject=record.title or record.display_name,
            state_label=self._selection_label(record, "state"),
            state_tone="waiting" if record.state == "counterparty_review" else "neutral",
            reason=reason, reason_tone=reason_tone or "neutral",
            due=record.expiry_date,
            priority=2 if record.risk in ("high", "critical") else 0,
            owner=record.legal_officer_id.display_name if record.legal_officer_id else "",
            since=record.effective_date,
        )

    # ------------------------------------------------------------------
    # Collectors - legal.opinion
    # ------------------------------------------------------------------
    def _queue_opinions_mine(self):
        Opinion = self._model("legal.opinion")
        if Opinion is None:
            return []
        domain = [("legal_officer_id", "=", self.env.uid),
                  ("state", "in", ("assigned", "drafting"))]
        records = self._safe_search(Opinion, domain, order="due_date asc, id desc",
                                    limit=QUEUE_LIMIT)
        return [self._opinion_row(record) for record in records]

    def _queue_opinions_approval(self):
        Opinion = self._model("legal.opinion")
        if Opinion is None:
            return []
        records = self._safe_search(Opinion, [("state", "in", ("review", "approval"))],
                                    order="due_date asc, id desc", limit=QUEUE_LIMIT)
        return [self._opinion_row(record,
                                  reason=self.env._("Waiting on your review."),
                                  reason_tone="critical") for record in records]

    def _opinion_row(self, record, reason=None, reason_tone=None):
        if reason is None:
            if record.is_overdue:
                reason = self.env._("Past its due date.")
                reason_tone = "critical"
            else:
                reason = record.requesting_department or ""
                reason_tone = "neutral"
        return self._queue_row(
            record, kind="opinion",
            reference=record.name or "",
            subject=record.subject or record.display_name,
            state_label=self._selection_label(record, "state"),
            state_tone="warning" if record.state in ("review", "approval") else "neutral",
            reason=reason, reason_tone=reason_tone or "neutral",
            due=record.due_date,
            priority=0,
            owner=record.legal_officer_id.display_name if record.legal_officer_id else "",
        )

    # ------------------------------------------------------------------
    # Collectors - legal.lawsuit
    # ------------------------------------------------------------------
    def _queue_lawsuits_mine(self):
        """Litigation only enters the queue when it has a date or a window.

        A lawsuit sitting in "in progress" with the next hearing six weeks out
        is not work today, and a queue that says otherwise is one a litigator
        learns to scroll past.
        """
        Lawsuit = self._model("legal.lawsuit")
        if Lawsuit is None:
            return []
        today = fields.Date.context_today(self)
        horizon = fields.Datetime.to_string(
            fields.Datetime.now() + timedelta(days=AGENDA_HORIZON_DAYS))
        domain = ["&", ("lawyer_id", "=", self.env.uid), "&", ("is_closed", "=", False),
                  "|", ("appeal_window_open", "=", True),
                  "|", "&", ("next_hearing_date", "!=", False),
                  ("next_hearing_date", "<=", horizon),
                  "&", ("next_deadline", "!=", False),
                  ("next_deadline", "<=", today + timedelta(days=AGENDA_HORIZON_DAYS))]
        records = self._safe_search(Lawsuit, domain, order="next_deadline asc, id desc",
                                    limit=QUEUE_LIMIT)
        return [self._lawsuit_row(record) for record in records]

    def _queue_lawsuits_manager(self):
        Lawsuit = self._model("legal.lawsuit")
        if Lawsuit is None:
            return []
        domain = ["&", ("is_closed", "=", False),
                  "|", ("risk", "in", ("high", "critical")), ("lawyer_id", "=", False)]
        records = self._safe_search(Lawsuit, domain, order="next_deadline asc, id desc",
                                    limit=QUEUE_LIMIT)
        rows = []
        for record in records:
            reason = (self.env._("No lawyer is named on it.") if not record.lawyer_id
                      else self.env._("High-risk exposure."))
            rows.append(self._lawsuit_row(record, reason=reason, reason_tone="critical"))
        return rows

    def _lawsuit_row(self, record, reason=None, reason_tone=None):
        if reason is None:
            if record.appeal_window_open:
                reason = self.env._("The appeal window is open.")
                reason_tone = "critical"
            elif record.next_hearing_date:
                reason = self.env._("Next hearing: %(when)s",
                                    when=self._digits(str(record.next_hearing_date)[:16]))
                reason_tone = "warning"
            else:
                reason = record.latest_development or ""
                reason_tone = "neutral"
        due = record.next_deadline
        if not due and record.next_hearing_date:
            due = fields.Date.to_date(record.next_hearing_date)
        return self._queue_row(
            record, kind="lawsuit",
            reference=record.reference or "",
            subject=record.title or record.display_name,
            state_label=self._selection_label(record, "state"),
            state_tone="warning" if record.state in ("judgment", "appeal") else "neutral",
            reason=reason, reason_tone=reason_tone or "neutral",
            due=due,
            priority=2 if record.risk in ("high", "critical") else 0,
            owner=record.lawyer_id.display_name if record.lawyer_id else "",
            since=record.date_filed,
        )

    # ------------------------------------------------------------------
    # Collectors - legal.correspondence
    # ------------------------------------------------------------------
    def _queue_correspondence_intake(self):
        Corr = self._model("legal.correspondence")
        if Corr is None:
            return []
        domain = ["|", ("state", "=", "draft"),
                  "&", "&", ("state", "=", "registered"), ("direction", "=", "in"),
                  "&", ("case_id", "=", False), ("is_contact_note", "=", False)]
        records = self._safe_search(Corr, domain, order="create_date desc",
                                    limit=QUEUE_LIMIT)
        rows = []
        for record in records:
            if record.state == "draft":
                reason = self.env._("Drafted; needs a register number.")
                tone = "critical"
            else:
                reason = self.env._("Registered but not attached to any matter.")
                tone = "warning"
            rows.append(self._correspondence_row(record, reason=reason, reason_tone=tone))
        return rows

    def _queue_correspondence_chase(self):
        """Letters we sent whose answer date has passed. Chasing is work."""
        Corr = self._model("legal.correspondence")
        if Corr is None:
            return []
        today = fields.Date.context_today(self)
        domain = [("user_id", "=", self.env.uid), ("state", "=", "registered"),
                  ("reply_expected", "=", True), ("reply_due_on", "<=", today)]
        records = self._safe_search(Corr, domain, order="reply_due_on asc",
                                    limit=QUEUE_LIMIT)
        return [self._correspondence_row(
            record,
            reason=self.env._("We are waiting on %(body)s.",
                              body=record.gov_body_id.display_name if record.gov_body_id
                              else self.env._("the other side")),
            reason_tone="critical") for record in records]

    def _correspondence_row(self, record, reason="", reason_tone="neutral"):
        return self._queue_row(
            record, kind="correspondence",
            reference=record.our_number or record.their_number or "",
            subject=record.subject or record.display_name,
            state_label=self._selection_label(record, "state"),
            state_tone="waiting" if record.reply_expected else "neutral",
            reason=reason, reason_tone=reason_tone,
            due=record.reply_due_on,
            owner=record.user_id.display_name if record.user_id else "",
            since=record.our_date or record.their_date,
        )

    # ------------------------------------------------------------------
    # Collectors - obligations and documents
    # ------------------------------------------------------------------
    def _queue_obligations_mine(self):
        Obligation = self._model("legal.obligation.instance")
        if Obligation is None:
            return []
        today = fields.Date.context_today(self)
        domain = [("state", "not in", ("filed", "waived")),
                  ("due_on", "<=", today + timedelta(days=14))]
        records = self._safe_search(Obligation, domain, order="due_on asc",
                                    limit=QUEUE_LIMIT)
        return [self._obligation_row(record) for record in records]

    def _queue_obligations_manager(self):
        Obligation = self._model("legal.obligation.instance")
        if Obligation is None:
            return []
        today = fields.Date.context_today(self)
        domain = [("state", "not in", ("filed", "waived")), ("due_on", "<", today)]
        records = self._safe_search(Obligation, domain, order="due_on asc",
                                    limit=QUEUE_LIMIT)
        return [self._obligation_row(
            record, reason=self.env._("A statutory period has closed unfiled."),
            reason_tone="critical") for record in records]

    def _obligation_row(self, record, reason=None, reason_tone=None):
        schedule = record.schedule_id
        return self._queue_row(
            record, kind="obligation",
            reference=record.period_key or "",
            subject=schedule.display_name if schedule else record.display_name,
            state_label=self._selection_label(record, "state"),
            state_tone="neutral",
            reason=reason if reason is not None
            else self.env._("Statutory filing period."),
            reason_tone=reason_tone or "neutral",
            due=record.due_on,
        )

    def _queue_documents_renewal(self):
        Doc = self._model("legal.document")
        if Doc is None:
            return []
        today = fields.Date.context_today(self)
        domain = [("state", "=", "active"), ("expiry_date", "!=", False),
                  ("expiry_date", "<=", today + timedelta(days=30))]
        records = self._safe_search(Doc, domain, order="expiry_date asc",
                                    limit=QUEUE_LIMIT)
        return [self._queue_row(
            record, kind="document",
            reference=record.reference if "reference" in record._fields else "",
            subject=record.name or record.display_name,
            state_label=self._selection_label(record, "state"),
            reason=self.env._("Validity ends; start the renewal."),
            reason_tone="warning",
            due=record.expiry_date,
        ) for record in records]

    # ==================================================================
    # THE AGENDA
    # ==================================================================
    def _office_agenda(self, role, today, degraded):
        """The next three weeks, off the union board and nothing else.

        ``legal.deadline`` already UNIONs the eleven clocks the suite runs into
        one dated view whose rows *are* the source rows. Composing the agenda
        from anything else would mean a second definition of "due" that could
        drift from the board the department escalates against, so this reads
        the board.
        """
        Deadline = self._model("legal.deadline")
        if Deadline is None:
            degraded.append(self.env._("The deadline board is not installed."))
            return {"title": self.env._("Coming up"), "groups": [], "total": 0}
        domain = [("state", "!=", "done"),
                  ("date_due", "<=", today + timedelta(days=AGENDA_HORIZON_DAYS))]
        if role["key"] in ("officer", "approver", "clerk"):
            # A personal agenda: rows that name this reader, plus the ones that
            # name nobody, because an unowned statutory date is everybody's.
            domain += ["|", ("user_id", "=", self.env.uid), ("user_id", "=", False)]
        try:
            records = Deadline.search(domain, order="date_due asc, id asc", limit=60)
        except Exception:  # noqa: BLE001
            _logger.warning("legal.office could not read the deadline board",
                            exc_info=True)
            degraded.append(self.env._("The agenda could not be read."))
            return {"title": self.env._("Coming up"), "groups": [], "total": 0}

        kinds = dict(Deadline._fields["kind"]._description_selection(self.env))
        buckets = [
            ("overdue", self.env._("Overdue"), "critical"),
            ("today", self.env._("Today"), "critical"),
            ("tomorrow", self.env._("Tomorrow"), "warning"),
            ("week", self.env._("This week"), "warning"),
            ("later", self.env._("Later"), "neutral"),
        ]
        grouped = {key: [] for key, _label, _tone in buckets}
        for record in records:
            delta = (record.date_due - today).days if record.date_due else 999
            if delta < 0:
                key = "overdue"
            elif delta == 0:
                key = "today"
            elif delta == 1:
                key = "tomorrow"
            elif delta <= 7:
                key = "week"
            else:
                key = "later"
            grouped[key].append({
                "id": record.id,
                "name": record.name or "",
                "kind": record.kind or "",
                "kind_label": kinds.get(record.kind, record.kind or ""),
                "icon": self._agenda_icon(record.kind),
                "date_label": fields.Date.to_string(record.date_due),
                "day_label": self._weekday_label(record.date_due) if record.date_due else "",
                "owner": record.user_id.display_name if record.user_id else "",
                "urgent": record.priority in ("1", "2"),
                "open": self._open_record(record.res_model, record.res_id)
                        if record.res_model else False,
            })
        groups = [{"key": key, "label": label, "tone": tone,
                   "rows": grouped[key], "count": len(grouped[key]),
                   "count_label": self._digits(len(grouped[key]))}
                  for key, label, tone in buckets if grouped[key]]
        return {
            "title": self.env._("Coming up"),
            "hint": self.env._("The next three weeks across every register."),
            "groups": groups,
            "total": sum(len(rows) for rows in grouped.values()),
            "empty": self.env._("No dates fall in the next three weeks."),
            "action": self._open_action(
                "legal.deadline", self.env._("Deadline board"),
                [("state", "!=", "done")],
                views=[[False, "list"], [False, "calendar"]]),
        }

    def _agenda_icon(self, kind):
        return {
            "obligation": "fa-calendar-check-o",
            "case_sla": "fa-folder-open-o",
            "correspondence_reply": "fa-reply",
            "document_expiry": "fa-id-card-o",
            "poa_expiry": "fa-user-secret",
            "hearing": "fa-gavel",
            "appeal_window": "fa-legal",
            "contract_obligation": "fa-check-square-o",
            "contract_expiry": "fa-file-text-o",
            "request_due": "fa-inbox",
            "opinion_due": "fa-balance-scale",
        }.get(kind, "fa-clock-o")

    # ==================================================================
    # SECONDARY - context, and only after the work
    # ==================================================================
    def _office_secondary(self, role, today, degraded):
        """What is true but not urgent, behind one row of tabs.

        Everything here answers "what can I safely ignore for now" - work that
        is genuinely moving, but elsewhere. It is one panel with tabs rather
        than four stacked panels precisely so that it cannot grow into a second
        screen below the first.
        """
        builders = {
            "clerk": self._secondary_clerk,
            "officer": self._secondary_officer,
            "approver": self._secondary_approver,
            "manager": self._secondary_manager,
            "auditor": self._secondary_auditor,
        }
        try:
            tabs = [tab for tab in builders[role["key"]](today) if tab]
        except Exception:  # noqa: BLE001
            _logger.warning("legal.office could not build the secondary strip",
                            exc_info=True)
            degraded.append(self.env._("The secondary panel is unavailable."))
            tabs = []
        return {"tabs": tabs}

    def _tab(self, key, label, rows, action=None, empty=""):
        return {
            "key": key,
            "label": label,
            "count": len(rows),
            "count_label": self._digits(len(rows)),
            "rows": rows[:SECONDARY_LIMIT],
            "action": action or False,
            "empty": empty or self.env._("Nothing here."),
        }

    def _mini_row(self, record, primary, secondary="", meta=""):
        return {
            "id": f"{record._name}:{record.id}",
            "primary": primary or "",
            "secondary": secondary or "",
            "meta": meta or "",
            "open": self._open_record(record._name, record.id),
        }

    def _secondary_officer(self, today):
        Case = self._model("legal.case")
        Corr = self._model("legal.correspondence")
        tabs = []
        if Case is not None:
            at_body = self._safe_search(
                Case, self._my_turn_domain(Case) + [("is_closed", "=", False),
                                                    ("kind", "=", "at_body")],
                order="stage_entered_on asc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "at_body", self.env._("With an external body"),
                [self._mini_row(record, record.subject or record.name,
                                record.current_body_id.display_name
                                if record.current_body_id else "",
                                record.name)
                 for record in at_body],
                self._open_action("legal.case", self.env._("With an external body"),
                                  self._my_turn_domain(Case) +
                                  [("is_closed", "=", False), ("kind", "=", "at_body")]),
                self.env._("Nothing of yours is lodged with a body.")))
            returned = self._safe_search(
                Case, [("user_id", "=", self.env.uid), ("is_closed", "=", False),
                       ("round", ">", 1)],
                order="write_date desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "returned", self.env._("Came back to you"),
                [self._mini_row(record, record.subject or record.name,
                                record.step_id.display_name if record.step_id else "",
                                record.name)
                 for record in returned],
                empty=self.env._("Nothing has been returned to you.")))
        if Corr is not None:
            recent = self._safe_search(
                Corr, [("user_id", "=", self.env.uid), ("state", "=", "registered")],
                order="create_date desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "recent", self.env._("Recently registered"),
                [self._mini_row(record, record.subject or record.display_name,
                                record.gov_body_id.display_name
                                if record.gov_body_id else "",
                                record.our_number or record.their_number or "")
                 for record in recent]))
        return tabs

    def _secondary_clerk(self, today):
        Corr = self._model("legal.correspondence")
        Case = self._model("legal.case")
        tabs = []
        if Corr is not None:
            registered = self._safe_search(
                Corr, [("state", "=", "registered")], order="create_date desc",
                limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "registered", self.env._("Registered today and recently"),
                [self._mini_row(record, record.subject or record.display_name,
                                record.gov_body_id.display_name
                                if record.gov_body_id else "",
                                record.our_number or record.their_number or "")
                 for record in registered],
                self._open_action("legal.correspondence", self.env._("The register"),
                                  [("state", "=", "registered")])))
            awaiting = self._safe_search(
                Corr, [("reply_expected", "=", True), ("state", "=", "registered"),
                       ("reply_due_on", ">=", today)],
                order="reply_due_on asc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "awaiting", self.env._("Answers still in time"),
                [self._mini_row(record, record.subject or record.display_name,
                                fields.Date.to_string(record.reply_due_on),
                                record.our_number or "")
                 for record in awaiting]))
        if Case is not None:
            opened = self._safe_search(Case, [("is_closed", "=", False)],
                                       order="date_open desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "opened", self.env._("Recently opened files"),
                [self._mini_row(record, record.subject or record.name,
                                record.user_id.display_name if record.user_id
                                else self.env._("Unassigned"),
                                record.name)
                 for record in opened]))
        return tabs

    def _secondary_approver(self, today):
        Request = self._model("legal.request")
        Contract = self._model("legal.contract")
        tabs = []
        if Request is not None:
            decided = self._safe_search(
                Request, [("state", "in", ("approved", "closed")),
                          ("approved_by_id", "=", self.env.uid)],
                order="approved_on desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "decided", self.env._("You decided recently"),
                [self._mini_row(record, record.subject or record.display_name,
                                self._selection_label(record, "decision"),
                                record.reference or "")
                 for record in decided]))
            returned = self._safe_search(
                Request, [("return_reason", "!=", False),
                          ("state", "in", ("assigned", "in_progress"))],
                order="write_date desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "returned", self.env._("Sent back for correction"),
                [self._mini_row(record, record.subject or record.display_name,
                                (record.return_reason or "")[:70],
                                record.reference or "")
                 for record in returned]))
        if Contract is not None:
            signed = self._safe_search(
                Contract, [("state", "in", ("signed", "active"))],
                order="signature_date desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "signed", self.env._("Recently in force"),
                [self._mini_row(record, record.title or record.display_name,
                                record.counterparty_id.display_name
                                if record.counterparty_id else "",
                                record.name or "")
                 for record in signed]))
        return tabs

    def _secondary_manager(self, today):
        """The room's shape: who is carrying what, and where it is piling up."""
        Case = self._model("legal.case")
        Request = self._model("legal.request")
        tabs = []
        if Case is not None:
            groups = self._safe_read_group(
                Case, [("is_closed", "=", False), ("user_id", "!=", False)],
                ["user_id"], ["__count"])
            rows = []
            for user, count in sorted(groups, key=lambda item: -item[1]):
                rows.append({
                    "id": f"user:{user.id}",
                    "primary": user.display_name,
                    "secondary": "",
                    "meta": self._digits(count),
                    "bar": count,
                    "open": self._open_action(
                        "legal.case",
                        self.env._("Files of %(who)s", who=user.display_name),
                        [("is_closed", "=", False), ("user_id", "=", user.id)]),
                })
            peak = max([row["bar"] for row in rows], default=1) or 1
            for row in rows:
                row["percent"] = int(round(100.0 * row["bar"] / peak))
            tabs.append(self._tab(
                "load", self.env._("Load per officer"), rows,
                empty=self.env._("No open file is assigned to anybody.")))
        if Request is not None:
            groups = self._safe_read_group(
                Request, [("state", "not in", ("closed", "cancelled"))],
                ["requesting_department"], ["__count"])
            rows = []
            for department, count in sorted(groups, key=lambda item: -item[1]):
                rows.append({
                    "id": f"dept:{department or 'none'}",
                    "primary": department or self.env._("Not stated"),
                    "secondary": "",
                    "meta": self._digits(count),
                    "bar": count,
                    "open": self._open_action(
                        "legal.request", department or self.env._("Not stated"),
                        [("state", "not in", ("closed", "cancelled")),
                         ("requesting_department", "=", department)]),
                })
            peak = max([row["bar"] for row in rows], default=1) or 1
            for row in rows:
                row["percent"] = int(round(100.0 * row["bar"] / peak))
            tabs.append(self._tab(
                "departments", self.env._("Demand by department"), rows))
        return tabs

    def _secondary_auditor(self, today):
        """The trail, and only the trail. Nothing here writes."""
        Log = self._model("legal.action.log")
        tabs = []
        if Log is not None:
            entries = self._safe_search(Log, [], order="create_date desc", limit=SECONDARY_LIMIT)
            tabs.append(self._tab(
                "trail", self.env._("Latest recorded moves"),
                [self._mini_row(
                    record,
                    record.display_name,
                    record.user_id.display_name if "user_id" in record._fields
                    and record.user_id else "",
                    self._digits(str(record.create_date)[:16]))
                 for record in entries],
                self._open_action("legal.action.log",
                                  self.env._("The action trail"), [])))
        Case = self._model("legal.case")
        if Case is not None:
            # Counted one value at a time rather than grouped: `sla_state` is
            # computed on read and carries a `search` method, so it can be
            # filtered but never grouped - `_read_group` on it raises, and the
            # degrade-to-empty helper would have hidden that behind a warning.
            labels = dict(Case._fields["sla_state"]._description_selection(self.env))
            rows = []
            for state, label in labels.items():
                domain = [("is_closed", "=", False), ("sla_state", "=", state)]
                count = self._optional_count(Case, domain)
                if not count:
                    continue
                rows.append({
                    "id": f"sla:{state}",
                    "primary": label,
                    "secondary": "",
                    "meta": self._digits(count),
                    "bar": count,
                    "open": self._open_action("legal.case", label, domain),
                })
            rows.sort(key=lambda row: -row["bar"])
            peak = max([row["bar"] for row in rows], default=1) or 1
            for row in rows:
                row["percent"] = int(round(100.0 * row["bar"] / peak))
            tabs.append(self._tab("sla", self.env._("Service level, open files"), rows))
        return tabs

    # ==================================================================
    # QUICK ACTIONS
    # ==================================================================
    def _office_create(self, role):
        """Five compact create controls, and none for a reader who may not write.

        Withheld server-side rather than hidden in the template: an auditor
        whose payload contains a create action has been given one, whatever the
        markup does with it.
        """
        if not role["can_write"]:
            return []
        candidates = [
            ("request", self.env._("Legal request"), "fa-inbox", "legal.request"),
            ("correspondence", self.env._("Letter"), "fa-envelope-o", "legal.correspondence"),
            ("case", self.env._("Government file"), "fa-folder-open-o", "legal.case"),
            ("contract", self.env._("Contract"), "fa-file-text-o", "legal.contract"),
            ("opinion", self.env._("Legal opinion"), "fa-balance-scale", "legal.opinion"),
            ("lawsuit", self.env._("Lawsuit"), "fa-gavel", "legal.lawsuit"),
        ]
        out = []
        for key, label, icon, model_name in candidates:
            model = self._model(model_name)
            if model is None:
                continue
            # `has_access` is the Odoo 19 checker; `check_access_rights` still
            # exists but has been deprecated since 18.0 and warns on every call.
            try:
                if not model.has_access("create"):
                    continue
            except Exception:  # noqa: BLE001 - an unanswerable check is a no
                continue
            out.append({
                "key": key,
                "label": label,
                "icon": icon,
                "action": {
                    "type": "ir.actions.act_window",
                    "name": label,
                    "res_model": model_name,
                    "views": [[False, "form"]],
                    "target": "current",
                },
            })
        return out

    # ==================================================================
    # Small shared helpers
    # ==================================================================
    def _selection_label(self, record, field_name):
        """The translated label of a selection value, or an empty string.

        Never the raw key: "ready_for_approval" on an Arabic screen is a defect,
        and the translation of the label is already carried by the field.
        """
        field = record._fields.get(field_name)
        if field is None or not record[field_name]:
            return ""
        try:
            return dict(field._description_selection(self.env)).get(
                record[field_name], record[field_name])
        except Exception:  # noqa: BLE001
            return record[field_name] or ""
