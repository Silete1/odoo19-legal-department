"""التقارير والتحليلات - the management reporting workspace.

The other half of the split this module exists to make. My Office answers
*what requires my action now*; this screen answers *what is happening across
Legal Affairs*, and the two are separated because they are read by different
people, at different times, for different reasons. A head of department reads
this on a Thursday afternoon; a follow-up officer never opens it at all.

Three rules govern every panel below, and they are what keep the screen from
becoming decoration.

**Every chart states its management question.** A panel whose question cannot
be written in one sentence has no business being drawn. The question is part of
the payload, rendered above the chart, so the reader is told what they are
looking for rather than left to infer it from an axis label.

**Every figure drills through.** Each panel carries its own rows - the same
numbers the chart draws - and each row carries an ``ir.actions.act_window``
onto the records behind it. That is not only navigation: it is the accessible
table the canvas cannot be, it is what prints, and it is the thing a manager
who wanted the number rather than the sweep actually needed.

**Nothing is invented.** Where a trend would need history the suite does not
record, the panel shows a distribution the database can answer honestly rather
than a line interpolated from nothing.
"""

import logging
from collections import OrderedDict
from datetime import date, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

#: Two validated categorical slots and one status colour, per mode. Charts are
#: capped at two series precisely so this stays inside what has been validated:
#: the third status step (amber) sits below 3:1 on a white surface, and a
#: three-way stack would have put it there.
PALETTE = {
    "light": {"a": "#2a78d6", "b": "#eb6834", "bad": "#d03b3b", "good": "#0ca30c"},
    "dark": {"a": "#3987e5", "b": "#d95926", "bad": "#d03b3b", "good": "#0ca30c"},
}

#: How many months of history the time panels look back over.
DEFAULT_MONTHS = 12

#: Ageing buckets, in days. Chosen against the department's own service
#: levels rather than round numbers: a request inside three working days is
#: on time, inside a week is normal, past a month is a problem.
AGE_BUCKETS = [
    (0, 3), (4, 7), (8, 14), (15, 30), (31, None),
]


class LegalAnalytics(models.AbstractModel):
    """The payload behind the ``legal_analytics`` client action."""

    _name = "legal.analytics"
    _inherit = "legal.dashboard"
    _description = "Legal Analytics Workspace"

    # ==================================================================
    # ENTRY POINT
    # ==================================================================
    @api.model
    def get_analytics_data(self, months=None):
        months = int(months or DEFAULT_MONTHS)
        today = fields.Date.context_today(self)
        since = self._month_start(today) - timedelta(days=31 * (months - 1))
        since = self._month_start(since)
        degraded = []
        sections = []
        for builder in (self._section_workload, self._section_timeliness,
                        self._section_lifecycle, self._section_horizon):
            try:
                section = builder(today, since, months)
            except Exception:  # noqa: BLE001
                _logger.warning("legal.analytics section failed", exc_info=True)
                degraded.append(self.env._("One section could not be computed."))
                continue
            if section and section["panels"]:
                sections.append(section)
        return {
            "rtl": self._rtl(),
            "numerals": self._numerals(),
            "title": self.env._("Legal Analytics"),
            "subtitle": self.env._("What is happening across Legal Affairs."),
            "months": months,
            "period_label": self.env._("Last %(n)s months", n=self._digits(months)),
            "period_choices": [
                {"months": 3, "label": self.env._("3 months")},
                {"months": 6, "label": self.env._("6 months")},
                {"months": 12, "label": self.env._("12 months")},
                {"months": 24, "label": self.env._("24 months")},
            ],
            "palette": PALETTE,
            "sections": sections,
            "degraded": degraded,
        }

    # ==================================================================
    # Panel plumbing
    # ==================================================================
    def _panel(self, key, question, title, chart, labels, series, rows,
               note="", legend=None):
        """One panel: a question, a chart, and the table that is the answer.

        ``rows`` is not an accessibility afterthought. It is the panel's
        primary content - the figures, and the drill-through onto the records
        that produced them - and the canvas is a summary of it. Building the
        panel this way round is why every chart on this screen can be clicked,
        read aloud, printed and disbelieved.
        """
        return {
            "key": key,
            "question": question,
            "title": title,
            "chart": chart,
            "labels": labels,
            "series": series,
            "legend": legend or [],
            "rows": rows,
            "total": sum(row.get("value", 0) for row in rows),
            "total_label": self._digits(sum(row.get("value", 0) for row in rows)),
            "note": note,
            "empty": self.env._("Nothing recorded in this period."),
        }

    def _row(self, label, value, action=None, secondary=""):
        return {
            "label": label,
            "value": value,
            "value_label": self._digits(value),
            "secondary": secondary,
            "action": action or False,
        }

    def _month_start(self, day):
        return date(day.year, day.month, 1)

    def _month_keys(self, since, months):
        """The month axis, materialised, so a month with no rows still appears.

        A bar chart that silently drops empty months turns a two-month gap in
        the register into a smooth line, which is the exact opposite of what a
        manager reading it needs to see.
        """
        keys = []
        cursor = self._month_start(since)
        for _index in range(months):
            keys.append(cursor)
            cursor = date(cursor.year + (cursor.month // 12),
                          (cursor.month % 12) + 1, 1)
        return keys

    def _month_label(self, day):
        return self._digits(f"{day.year}-{day.month:02d}")

    def _group_counts(self, model, domain, groupby):
        """``_read_group`` with the degrade-to-empty contract of the desks."""
        out = OrderedDict()
        for row in self._safe_read_group(model, domain, [groupby], ["__count"]):
            out[row[0]] = row[1]
        return out

    # ==================================================================
    # SECTION 1 - WORKLOAD: who is carrying what
    # ==================================================================
    def _section_workload(self, today, since, months):
        panels = []
        Case = self._model("legal.case")
        Request = self._model("legal.request")

        if Case is not None:
            counts = self._group_counts(Case, [("is_closed", "=", False)], "user_id")
            rows = []
            for user, count in sorted(counts.items(), key=lambda item: -item[1])[:12]:
                rows.append(self._row(
                    user.display_name if user else self.env._("Unassigned"), count,
                    self._open_action(
                        "legal.case",
                        user.display_name if user else self.env._("Unassigned"),
                        [("is_closed", "=", False),
                         ("user_id", "=", user.id if user else False)])))
            panels.append(self._panel(
                "officer_load",
                self.env._("Is the work spread evenly, and who is carrying too much?"),
                self.env._("Open files per officer"),
                "hbar", [row["label"] for row in rows],
                [{"key": "open", "label": self.env._("Open files"),
                  "data": [row["value"] for row in rows], "colour": "a"}],
                rows,
                self.env._("Counts open government files only; litigation and "
                           "contracts are counted in their own panels.")))

        if Request is not None:
            counts = self._group_counts(
                Request, [("state", "not in", ("closed", "cancelled"))],
                "requesting_department")
            rows = []
            for department, count in sorted(counts.items(), key=lambda item: -item[1])[:12]:
                label = department or self.env._("Not stated")
                rows.append(self._row(
                    label, count,
                    self._open_action("legal.request", label,
                                      [("state", "not in", ("closed", "cancelled")),
                                       ("requesting_department", "=", department)])))
            panels.append(self._panel(
                "department_demand",
                self.env._("Which departments generate the legal work?"),
                self.env._("Live requests by requesting department"),
                "hbar", [row["label"] for row in rows],
                [{"key": "live", "label": self.env._("Live requests"),
                  "data": [row["value"] for row in rows], "colour": "a"}],
                rows))

            counts = self._group_counts(
                Request, [("state", "not in", ("closed", "cancelled"))], "category_id")
            rows = []
            for category, count in sorted(counts.items(), key=lambda item: -item[1])[:12]:
                label = category.display_name if category else self.env._("Uncategorised")
                rows.append(self._row(
                    label, count,
                    self._open_action("legal.request", label,
                                      [("state", "not in", ("closed", "cancelled")),
                                       ("category_id", "=", category.id if category else False)])))
            panels.append(self._panel(
                "matter_type",
                self.env._("What kind of work is the department actually doing?"),
                self.env._("Live requests by type"),
                "hbar", [row["label"] for row in rows],
                [{"key": "live", "label": self.env._("Live requests"),
                  "data": [row["value"] for row in rows], "colour": "a"}],
                rows))

        return {"key": "workload", "title": self.env._("Workload"),
                "hint": self.env._("Who is carrying what, and where it comes from."),
                "panels": panels}

    # ==================================================================
    # SECTION 2 - TIMELINESS: are we late, and where
    # ==================================================================
    def _section_timeliness(self, today, since, months):
        panels = []
        Deadline = self._model("legal.deadline")
        Request = self._model("legal.request")
        Case = self._model("legal.case")

        if Deadline is not None:
            kinds = dict(Deadline._fields["kind"]._description_selection(self.env))
            open_counts = self._group_counts(Deadline, [("state", "=", "open")], "kind")
            late_counts = self._group_counts(Deadline, [("state", "=", "overdue")], "kind")
            keys = [key for key in kinds
                    if open_counts.get(key) or late_counts.get(key)]
            rows = []
            for key in sorted(keys, key=lambda k: -(late_counts.get(k, 0))):
                rows.append(self._row(
                    kinds[key], late_counts.get(key, 0),
                    self._open_action("legal.deadline", kinds[key],
                                      [("kind", "=", key), ("state", "=", "overdue")],
                                      views=[[False, "list"], [False, "calendar"]]),
                    secondary=self.env._("%(n)s still open",
                                         n=self._digits(open_counts.get(key, 0)))))
            panels.append(self._panel(
                "deadline_state",
                self.env._("Which clocks are we missing, and which are merely running?"),
                self.env._("Deadlines by register"),
                "stacked", [kinds[key] for key in
                            sorted(keys, key=lambda k: -(late_counts.get(k, 0)))],
                [
                    {"key": "overdue", "label": self.env._("Overdue"),
                     "data": [late_counts.get(key, 0) for key in
                              sorted(keys, key=lambda k: -(late_counts.get(k, 0)))],
                     "colour": "bad"},
                    {"key": "open", "label": self.env._("Open"),
                     "data": [open_counts.get(key, 0) for key in
                              sorted(keys, key=lambda k: -(late_counts.get(k, 0)))],
                     "colour": "a"},
                ],
                rows,
                self.env._("Read off the union board, so a deadline discharged "
                           "at its source leaves this chart in the same transaction."),
                legend=[{"label": self.env._("Overdue"), "colour": "bad"},
                        {"label": self.env._("Open"), "colour": "a"}]))

        if Request is not None:
            # Ageing is computed in Python over the live rows rather than in
            # SQL, because "age" here is age *of the open request*, which no
            # stored column carries and a groupby cannot express.
            live = self._safe_search(
                Request, [("state", "not in", ("closed", "cancelled"))],
                order="request_date asc", limit=2000)
            buckets = OrderedDict()
            for low, high in AGE_BUCKETS:
                label = (self.env._("%(a)s-%(b)s days", a=self._digits(low),
                                    b=self._digits(high)) if high
                         else self.env._("over %(a)s days", a=self._digits(low - 1)))
                buckets[(low, high)] = [label, 0]
            for record in live:
                if not record.request_date:
                    continue
                age = (today - record.request_date).days
                for low, high in AGE_BUCKETS:
                    if age >= low and (high is None or age <= high):
                        buckets[(low, high)][1] += 1
                        break
            rows = []
            for (low, high), (label, count) in buckets.items():
                domain = [("state", "not in", ("closed", "cancelled")),
                          ("request_date", "<=", today - timedelta(days=low))]
                if high is not None:
                    domain.append(("request_date", ">=", today - timedelta(days=high)))
                rows.append(self._row(label, count,
                                      self._open_action("legal.request", label, domain)))
            panels.append(self._panel(
                "request_ageing",
                self.env._("How long has work been sitting with us unfinished?"),
                self.env._("Ageing of live requests"),
                "bar", [row["label"] for row in rows],
                [{"key": "age", "label": self.env._("Live requests"),
                  "data": [row["value"] for row in rows], "colour": "a"}],
                rows))

            # Turnaround: a real trend, because both dates are recorded.
            decided = self._safe_search(
                Request, [("approved_on", "!=", False),
                          ("approved_on", ">=", fields.Datetime.to_string(
                              fields.Datetime.to_datetime(since)))],
                order="approved_on asc", limit=5000)
            per_month = OrderedDict((key, []) for key in self._month_keys(since, months))
            for record in decided:
                if not record.request_date or not record.approved_on:
                    continue
                key = self._month_start(fields.Date.to_date(record.approved_on))
                if key in per_month:
                    per_month[key].append(
                        (fields.Date.to_date(record.approved_on) - record.request_date).days)
            labels, data, rows = [], [], []
            for key, ages in per_month.items():
                average = round(sum(ages) / len(ages), 1) if ages else 0
                labels.append(self._month_label(key))
                data.append(average)
                rows.append(self._row(
                    self._month_label(key), average,
                    secondary=self.env._("%(n)s decided", n=self._digits(len(ages)))))
            panels.append(self._panel(
                "turnaround",
                self.env._("Are we getting faster or slower at deciding requests?"),
                self.env._("Average days from request to decision"),
                "line", labels,
                [{"key": "days", "label": self.env._("Days"), "data": data,
                  "colour": "a"}],
                rows,
                self.env._("Calendar days between the request date and the "
                           "recorded decision. A month with no decisions reads zero.")))

        if Case is not None:
            # Counted per value, never grouped: `sla_state` is computed on read
            # with a `search` method, so a group-by raises where a filter works.
            labels_map = dict(Case._fields["sla_state"]._description_selection(self.env))
            rows = []
            for state, label in labels_map.items():
                domain = [("is_closed", "=", False), ("sla_state", "=", state)]
                count = self._safe_count(Case, domain)
                if not count:
                    continue
                rows.append(self._row(
                    label, count, self._open_action("legal.case", label, domain)))
            rows.sort(key=lambda row: -row["value"])
            panels.append(self._panel(
                "sla_state",
                self.env._("How many open files are already outside their service level?"),
                self.env._("Open files by service level"),
                "bar", [row["label"] for row in rows],
                [{"key": "sla", "label": self.env._("Open files"),
                  "data": [row["value"] for row in rows], "colour": "a"}],
                rows))

        return {"key": "timeliness", "title": self.env._("Timeliness"),
                "hint": self.env._("Where the clocks are being missed."),
                "panels": panels}

    # ==================================================================
    # SECTION 3 - LIFECYCLE: where things stand
    # ==================================================================
    def _section_lifecycle(self, today, since, months):
        panels = []
        for model_name, field, question, title, closed_domain in (
            ("legal.contract", "state",
             self.env._("Where are the contracts stuck on their way to signature?"),
             self.env._("Contracts by lifecycle stage"), [("is_closed", "=", False)]),
            ("legal.lawsuit", "state",
             self.env._("What stage is our litigation at?"),
             self.env._("Lawsuits by stage"), [("is_closed", "=", False)]),
            ("legal.case", "phase_id",
             self.env._("Where do government files accumulate?"),
             self.env._("Open files by phase"), [("is_closed", "=", False)]),
            ("legal.opinion", "state",
             self.env._("How much advisory work is in flight, and where?"),
             self.env._("Opinions by stage"), [("state", "!=", "closed")]),
        ):
            model = self._model(model_name)
            if model is None:
                continue
            counts = self._group_counts(model, closed_domain, field)
            if not counts:
                continue
            labels_map = {}
            if model._fields[field].type == "selection":
                labels_map = dict(model._fields[field]._description_selection(self.env))
            rows = []
            for value, count in sorted(counts.items(), key=lambda item: -item[1]):
                if labels_map:
                    label = labels_map.get(value, value or self.env._("Not set"))
                    raw = value
                else:
                    label = value.display_name if value else self.env._("Not set")
                    raw = value.id if value else False
                rows.append(self._row(
                    label, count,
                    self._open_action(model_name, label,
                                      closed_domain + [(field, "=", raw)])))
            panels.append(self._panel(
                f"lifecycle_{model_name.replace('.', '_')}",
                question, title, "hbar", [row["label"] for row in rows],
                [{"key": "count", "label": title,
                  "data": [row["value"] for row in rows], "colour": "a"}],
                rows))

        return {"key": "lifecycle", "title": self.env._("Lifecycle"),
                "hint": self.env._("Where each register's work is standing."),
                "panels": panels}

    # ==================================================================
    # SECTION 4 - HORIZON: what is coming
    # ==================================================================
    def _section_horizon(self, today, since, months):
        panels = []
        Contract = self._model("legal.contract")
        Hearing = self._model("legal.hearing")
        Corr = self._model("legal.correspondence")

        if Contract is not None:
            keys = self._month_keys(self._month_start(today), 12)
            labels, data, rows = [], [], []
            for key in keys:
                nxt = date(key.year + (key.month // 12), (key.month % 12) + 1, 1)
                domain = [("is_closed", "=", False), ("expiry_date", ">=", key),
                          ("expiry_date", "<", nxt)]
                count = self._safe_count(Contract, domain)
                labels.append(self._month_label(key))
                data.append(count)
                rows.append(self._row(self._month_label(key), count,
                                      self._open_action("legal.contract",
                                                        self._month_label(key), domain)))
            panels.append(self._panel(
                "contract_expiry",
                self.env._("What are we going to have to renew, and when?"),
                self.env._("Contract expirations, next twelve months"),
                "bar", labels,
                [{"key": "expiry", "label": self.env._("Contracts ending"),
                  "data": data, "colour": "a"}],
                rows,
                self.env._("Counts contracts still in force with a recorded end date.")))

        if Hearing is not None:
            labels, data, rows = [], [], []
            for week in range(8):
                start = today + timedelta(days=7 * week)
                end = start + timedelta(days=7)
                domain = [("date", ">=", fields.Datetime.to_string(
                    fields.Datetime.to_datetime(start))),
                    ("date", "<", fields.Datetime.to_string(
                        fields.Datetime.to_datetime(end)))]
                count = self._safe_count(Hearing, domain)
                # A week label is an axis tick people compare against a diary.
                label = fields.Date.to_string(start)
                labels.append(label)
                data.append(count)
                rows.append(self._row(label, count,
                                      self._open_action(
                                          "legal.hearing", label, domain,
                                          views=[[False, "list"], [False, "calendar"]])))
            panels.append(self._panel(
                "hearings",
                self.env._("How heavy are the next eight weeks in court?"),
                self.env._("Hearings by week"),
                "bar", labels,
                [{"key": "hearings", "label": self.env._("Hearings"),
                  "data": data, "colour": "a"}],
                rows,
                self.env._("Each column is the week beginning on the date shown.")))

        if Corr is not None:
            keys = self._month_keys(since, months)
            incoming, outgoing, rows = [], [], []
            for key in keys:
                nxt = date(key.year + (key.month // 12), (key.month % 12) + 1, 1)
                base = [("state", "=", "registered"), ("create_date", ">=",
                        fields.Datetime.to_string(fields.Datetime.to_datetime(key))),
                        ("create_date", "<", fields.Datetime.to_string(
                            fields.Datetime.to_datetime(nxt)))]
                in_count = self._safe_count(Corr, base + [("direction", "=", "in")])
                out_count = self._safe_count(Corr, base + [("direction", "=", "out")])
                incoming.append(in_count)
                outgoing.append(out_count)
                rows.append(self._row(
                    self._month_label(key), in_count + out_count,
                    self._open_action("legal.correspondence",
                                      self._month_label(key), base),
                    secondary=self.env._("%(i)s in / %(o)s out",
                                         i=self._digits(in_count),
                                         o=self._digits(out_count))))
            panels.append(self._panel(
                "correspondence_volume",
                self.env._("Is the register getting busier, and in which direction?"),
                self.env._("Registered correspondence per month"),
                "grouped", [self._month_label(key) for key in keys],
                [
                    {"key": "in", "label": self.env._("Incoming"),
                     "data": incoming, "colour": "a"},
                    {"key": "out", "label": self.env._("Outgoing"),
                     "data": outgoing, "colour": "b"},
                ],
                rows,
                legend=[{"label": self.env._("Incoming"), "colour": "a"},
                        {"label": self.env._("Outgoing"), "colour": "b"}]))

        return {"key": "horizon", "title": self.env._("The horizon"),
                "hint": self.env._("What the next months already hold."),
                "panels": panels}
