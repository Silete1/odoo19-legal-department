# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Where the accreditation process is actually slow.

Every figure here is derived from evidence the workflow already produced - the
immutable approval log and the state of the live caseload - and none of it is
estimated from anything else. There is no second source of truth to drift.

Three questions, three payloads
-------------------------------
``get_process_performance_data``  Where does the process spend its time, and is
                                 it getting better or worse?
``get_sla_dashboard_data``       What is late right now, and with whom?
``get_document_health_data``     What is wrong with the paperwork in the
                                 building?

Each returns a plain structure any screen can render, so a dashboard - this
module's or another agent's - never has to know how a median is computed.

On honesty with small samples
-----------------------------
A directorate accredits tens of organisations a year, not millions, and a
median of three files is not a fact. Every distribution therefore ships its
sample size, and anything computed from fewer than :data:`MIN_SAMPLE` closed
visits is flagged ``thin``, so the screen can say "3 files" instead of quietly
presenting an average as a performance figure.

On query behaviour
------------------
Stage timings come from ``_read_group`` over the three stored, indexed columns
the approval log now carries (``entered_on``, ``duration_hours``,
``is_transition``), with the percentiles computed by PostgreSQL. The whole
stage table is one query, the throughput series is one query per event kind,
and nothing here loads a request in a loop.
"""
import logging
from collections import defaultdict

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .dma_constants import (
    CLOSED_STATES,
    MAIN_PATH_STATES,
    ROLE_QUEUE_STATES,
    ROLE_SELECTION,
    SLA_TRACKED_STATES,
    STATE_PENDING_ROLE,
    role_label,
    state_label,
)

_logger = logging.getLogger(__name__)

#: Below this many closed visits, a median says more about luck than about the
#: process. The figure is still shown - hiding it would be worse - but it is
#: marked so the screen can say so.
MIN_SAMPLE = 5

#: Default window of the performance screen.
DEFAULT_MONTHS = 12


class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    # ==================================================================
    # Shared helpers
    # ==================================================================
    @api.model
    def _analytics_period(self, date_from=False, date_to=False):
        """Normalise the window, defaulting to the last twelve months."""
        today = fields.Date.context_today(self)
        date_to = fields.Date.to_date(date_to) or today
        date_from = fields.Date.to_date(date_from) or (
            date_to - relativedelta(months=DEFAULT_MONTHS)
        )
        if date_from > date_to:
            date_from, date_to = date_to, date_from
        return date_from, date_to

    @api.model
    def _analytics_env(self):
        """Bucket dates in the reader's own timezone.

        ``_read_group`` shifts a datetime column with ``context['tz']`` and
        *only* that key - it never looks at the user's own timezone - so a
        server-side dashboard that forgets this quietly reports UTC months.
        """
        return self.with_context(tz=self.env.user.tz or self.env.context.get("tz") or "UTC")

    @api.model
    def _analytics_guard(self):
        """Only somebody who may read the caseload may read figures about it."""
        self.check_access("read")

    @staticmethod
    def _distribution(values):
        """Count, mean, median and p90 of a list of hours, plus a thin flag."""
        ordered = sorted(value for value in values if value is not None)
        count = len(ordered)
        if not count:
            return {
                "count": 0, "avg": 0.0, "median": 0.0, "p90": 0.0, "thin": True,
            }

        def percentile(fraction):
            # Linear interpolation, the same definition PostgreSQL's
            # PERCENTILE_CONT uses, so the Python and SQL paths of this module
            # never disagree on the same data.
            if count == 1:
                return ordered[0]
            position = fraction * (count - 1)
            low = int(position)
            high = min(low + 1, count - 1)
            return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

        return {
            "count": count,
            "avg": sum(ordered) / count,
            "median": percentile(0.5),
            "p90": percentile(0.9),
            "thin": count < MIN_SAMPLE,
        }

    def _format_duration_days(self, hours):
        """A duration a manager reads: days, one decimal, or hours below one."""
        hours = float(hours or 0.0)
        if hours < 24:
            return self.env._("%s h", round(hours, 1))
        return self.env._("%s d", round(hours / 24.0, 1))

    # ==================================================================
    # Stage performance
    # ==================================================================
    @api.model
    def _stage_duration_stats(self, date_from, date_to):
        """Median, p90 and count of every *completed* visit, per step.

        One grouped query over the approval log. ``is_transition`` keeps the
        two signatures the dual confirmation writes mid-step out of the count,
        so "how long does the dual confirmation take" is measured once per
        visit and not three times.
        """
        Line = self.env["dma.approval.line"]
        rows = Line._read_group(
            domain=[
                ("is_transition", "=", True),
                ("date", ">=", fields.Datetime.to_datetime(date_from)),
                ("date", "<=", fields.Datetime.to_datetime(date_to) + relativedelta(days=1)),
                ("step", "in", list(MAIN_PATH_STATES)),
            ],
            groupby=["step"],
            aggregates=[
                "__count",
                "duration_hours:avg",
                "duration_hours:p50",
                "duration_hours:p90",
                "duration_hours:max",
            ],
        )
        return {
            step: {
                "count": count,
                "avg": average or 0.0,
                "median": median or 0.0,
                "p90": p90 or 0.0,
                "max": longest or 0.0,
                "thin": count < MIN_SAMPLE,
            }
            for step, count, average, median, p90, longest in rows
        }

    @api.model
    def _live_stage_counts(self):
        """How many files are sitting on each step right now, and how many are late."""
        rows = self._read_group(
            domain=[("state", "in", list(SLA_TRACKED_STATES))],
            groupby=["state"],
            aggregates=["__count"],
        )
        waiting = {state: count for state, count in rows}
        overdue = defaultdict(int)
        escalated = defaultdict(int)
        now = fields.Datetime.now()
        for request in self.search([("state", "in", list(SLA_TRACKED_STATES))]):
            verdict = request._sla_verdict(now=now)
            if verdict["state"] == "overdue":
                overdue[request.state] += 1
            elif verdict["state"] == "escalated":
                overdue[request.state] += 1
                escalated[request.state] += 1
        return waiting, overdue, escalated

    # ==================================================================
    # Throughput and cycle time
    # ==================================================================
    @api.model
    def _throughput_series(self, date_from, date_to):
        """Files submitted, accredited, rejected and returned, by month.

        Submissions come off the request itself; the other three come off the
        approval log, because "when was this granted" is a fact about a
        decision, not about the record's current status - a file that was
        granted in March and rejected in June has to count in both months.
        """
        analytics = self._analytics_env()
        start = fields.Datetime.to_datetime(date_from)
        end = fields.Datetime.to_datetime(date_to) + relativedelta(days=1)
        months = []
        cursor = date_from.replace(day=1)
        last = date_to.replace(day=1)
        while cursor <= last:
            months.append(cursor.strftime("%Y-%m"))
            cursor += relativedelta(months=1)

        def empty():
            return {month: 0 for month in months}

        series = {
            "submitted": empty(), "office_granted": empty(),
            "authorized": empty(), "rejected": empty(), "returned": empty(),
        }

        submissions = analytics._read_group(
            domain=[
                ("submission_date", ">=", date_from),
                ("submission_date", "<=", date_to),
            ],
            groupby=["submission_date:month"],
            aggregates=["__count"],
        )
        for bucket, count in submissions:
            if bucket:
                series["submitted"][bucket.strftime("%Y-%m")] = count

        # step -> the series a decision on that step feeds.
        decisions = {
            ("cert_check", "approved"): "office_granted",
            ("legal_refine", "approved"): "authorized",
        }
        rows = analytics.env["dma.approval.line"]._read_group(
            domain=[("date", ">=", start), ("date", "<", end)],
            groupby=["date:month", "step", "decision"],
            aggregates=["__count"],
        )
        for bucket, step, decision, count in rows:
            if not bucket:
                continue
            month = bucket.strftime("%Y-%m")
            if month not in series["submitted"]:
                continue
            key = decisions.get((step, decision))
            if key:
                series[key][month] = series[key].get(month, 0) + count
            elif decision == "rejected":
                series["rejected"][month] = series["rejected"].get(month, 0) + count
            elif decision == "returned":
                series["returned"][month] = series["returned"].get(month, 0) + count

        return {
            "months": months,
            "series": {
                key: [values[month] for month in months]
                for key, values in series.items()
            },
        }

    @api.model
    def _cycle_time_stats(self, date_from, date_to):
        """How long the two phases and the whole procedure actually take.

        Measured between the decisions themselves rather than between a
        submission date and today, so a file still in flight never drags an
        average down and a file that was returned twice counts the waiting it
        really caused.
        """
        start = fields.Datetime.to_datetime(date_from)
        end = fields.Datetime.to_datetime(date_to) + relativedelta(days=1)
        # One query for every milestone of every file that reached one in the
        # window, then the arithmetic in Python: three subtractions per file.
        lines = self.env["dma.approval.line"].search([
            ("is_transition", "=", True),
            ("step", "in", ("draft", "cert_check", "legal_refine")),
            ("decision", "in", ("approved", "confirmed")),
            ("date", ">=", start), ("date", "<", end),
        ], order="date asc, id asc")
        milestone_of = {
            "draft": "submitted_on",
            "cert_check": "office_on",
            "legal_refine": "authorized_on",
        }
        milestones = defaultdict(dict)
        for line in lines:
            # The *first* time a file passed a milestone is the one that counts:
            # a file granted, reset and granted again took as long as it took
            # the first time.
            milestones[line.request_id.id].setdefault(
                milestone_of[line.step], line.date,
            )

        def hours_between(first, second):
            return (second - first).total_seconds() / 3600.0

        office, operational, overall = [], [], []
        for stamps in milestones.values():
            if stamps.get("submitted_on") and stamps.get("office_on"):
                office.append(hours_between(stamps["submitted_on"], stamps["office_on"]))
            if stamps.get("office_on") and stamps.get("authorized_on"):
                operational.append(
                    hours_between(stamps["office_on"], stamps["authorized_on"])
                )
            if stamps.get("submitted_on") and stamps.get("authorized_on"):
                overall.append(
                    hours_between(stamps["submitted_on"], stamps["authorized_on"])
                )
        return {
            "office": self._distribution(office),
            "operational": self._distribution(operational),
            "overall": self._distribution(overall),
        }

    # ==================================================================
    # Rework
    # ==================================================================
    @api.model
    def _rework_stats(self, date_from, date_to):
        """Where files get sent back, and which ones keep coming back."""
        start = fields.Datetime.to_datetime(date_from)
        end = fields.Datetime.to_datetime(date_to) + relativedelta(days=1)
        rows = self.env["dma.approval.line"]._read_group(
            domain=[
                ("decision", "=", "returned"),
                ("date", ">=", start), ("date", "<", end),
            ],
            groupby=["step"],
            aggregates=["__count"],
        )
        by_step = [{
            "key": step,
            "label": state_label(self.env, step),
            "count": count,
        } for step, count in rows if step]
        by_step.sort(key=lambda item: item["count"], reverse=True)

        repeated = self.env["dma.approval.line"]._read_group(
            domain=[
                ("decision", "=", "returned"),
                ("date", ">=", start), ("date", "<", end),
            ],
            groupby=["request_id"],
            aggregates=["__count"],
            having=[("__count", ">", 1)],
            order="__count DESC",
            limit=10,
        )
        return {
            "total": sum(item["count"] for item in by_step),
            "by_step": by_step,
            "repeat_offenders": [{
                "id": request.id,
                "name": request.display_name,
                "count": count,
            } for request, count in repeated],
        }

    # ==================================================================
    # Department workload
    # ==================================================================
    @api.model
    def _workload_stats(self, date_from, date_to):
        """What each department is holding, how much of it is late, and how fast it works."""
        start = fields.Datetime.to_datetime(date_from)
        end = fields.Datetime.to_datetime(date_to) + relativedelta(days=1)
        completed = self.env["dma.approval.line"]._read_group(
            domain=[
                ("is_transition", "=", True),
                ("date", ">=", start), ("date", "<", end),
            ],
            groupby=["role"],
            aggregates=["__count", "duration_hours:p50", "duration_hours:p90"],
        )
        by_role = {
            role: (count, median or 0.0, p90 or 0.0)
            for role, count, median, p90 in completed
        }

        now = fields.Datetime.now()
        live = self.search([("state", "in", list(SLA_TRACKED_STATES))])
        holding = defaultdict(int)
        late = defaultdict(int)
        for request in live:
            verdict = request._sla_verdict(now=now)
            for role in request._pending_roles():
                holding[role] += 1
            if verdict["state"] in ("overdue", "escalated") and verdict["role"]:
                late[verdict["role"]] += 1

        rows = []
        for key, _label in ROLE_SELECTION:
            if key == "manager":
                continue
            count, median, p90 = by_role.get(key, (0, 0.0, 0.0))
            rows.append({
                "key": key,
                "label": role_label(self.env, key),
                "holding": holding.get(key, 0),
                "overdue": late.get(key, 0),
                "completed": count,
                "median_hours": median,
                "median_label": self._format_duration_days(median),
                "p90_hours": p90,
                "thin": count < MIN_SAMPLE,
                "domain": [("state", "in", ROLE_QUEUE_STATES.get(key, []))],
            })
        rows.sort(key=lambda row: (-row["overdue"], -row["holding"]))
        return rows

    # ==================================================================
    # The three public payloads
    # ==================================================================
    @api.model
    def get_process_performance_data(self, date_from=False, date_to=False):
        """Everything the process performance screen shows."""
        self._analytics_guard()
        date_from, date_to = self._analytics_period(date_from, date_to)
        durations = self._stage_duration_stats(date_from, date_to)
        waiting, overdue, escalated = self._live_stage_counts()

        stages = []
        for key in MAIN_PATH_STATES:
            if key in CLOSED_STATES:
                continue
            stats = durations.get(key, {
                "count": 0, "avg": 0.0, "median": 0.0, "p90": 0.0, "max": 0.0,
                "thin": True,
            })
            stages.append({
                "key": key,
                "label": state_label(self.env, key),
                "role": role_label(self.env, STATE_PENDING_ROLE.get(key) or "manager"),
                "count": stats["count"],
                "median_hours": stats["median"],
                "median_label": self._format_duration_days(stats["median"]),
                "p90_hours": stats["p90"],
                "p90_label": self._format_duration_days(stats["p90"]),
                "avg_hours": stats["avg"],
                "thin": stats["thin"],
                "waiting": waiting.get(key, 0),
                "overdue": overdue.get(key, 0),
                "escalated": escalated.get(key, 0),
                "overdue_rate": round(
                    100.0 * overdue.get(key, 0) / waiting[key]
                ) if waiting.get(key) else 0,
                "domain": [("state", "=", key)],
            })

        slowest = max((stage["median_hours"] for stage in stages), default=0.0)
        for stage in stages:
            stage["median_percent"] = round(
                100.0 * stage["median_hours"] / slowest
            ) if slowest else 0

        # The bottleneck ranking: the three questions a manager actually asks,
        # each answered by its own ordering rather than by one blended score
        # nobody could explain.
        bottlenecks = {
            "slowest": sorted(
                [stage for stage in stages if stage["count"]],
                key=lambda stage: stage["median_hours"], reverse=True,
            )[:5],
            "latest": sorted(
                [stage for stage in stages if stage["overdue"]],
                key=lambda stage: (stage["overdue_rate"], stage["overdue"]),
                reverse=True,
            )[:5],
            "busiest": sorted(
                [stage for stage in stages if stage["waiting"]],
                key=lambda stage: stage["waiting"], reverse=True,
            )[:5],
        }

        return {
            "rtl": self.env["res.lang"]._lang_get(
                self.env.lang or "en_US"
            ).direction == "rtl",
            "period": {
                "date_from": fields.Date.to_string(date_from),
                "date_to": fields.Date.to_string(date_to),
            },
            "min_sample": MIN_SAMPLE,
            "stages": stages,
            "bottlenecks": bottlenecks,
            "throughput": self._throughput_series(date_from, date_to),
            "cycle_time": {
                key: dict(
                    stats,
                    label=self._format_duration_days(stats["median"]),
                    p90_label=self._format_duration_days(stats["p90"]),
                )
                for key, stats in self._cycle_time_stats(date_from, date_to).items()
            },
            "rework": self._rework_stats(date_from, date_to),
            "workload": self._workload_stats(date_from, date_to),
        }

    @api.model
    def get_sla_dashboard_data(self, limit=12):
        """What is late right now, with whom, and how badly."""
        self._analytics_guard()
        now = fields.Datetime.now()
        live = self.search([("state", "in", list(SLA_TRACKED_STATES))])
        labels = self._sla_state_labels()
        counts = dict.fromkeys(labels, 0)
        worst = []
        for request in live:
            verdict = request._sla_verdict(now=now)
            counts[verdict["state"]] = counts.get(verdict["state"], 0) + 1
            if verdict["state"] in ("overdue", "escalated"):
                worst.append((verdict["overdue_hours"], request, verdict))
        worst.sort(key=lambda item: item[0], reverse=True)

        tracked = sum(
            counts.get(key, 0)
            for key in ("on_track", "warning", "overdue", "escalated")
        )
        settled = counts.get("on_track", 0) + counts.get("warning", 0)

        escalations = self.env["dma.sla.escalation"].search(
            [("is_open", "=", True)], order="level desc, triggered_on asc", limit=limit,
        )
        return {
            "rtl": self.env["res.lang"]._lang_get(
                self.env.lang or "en_US"
            ).direction == "rtl",
            "counts": [{
                "key": key,
                "label": labels[key],
                "count": counts.get(key, 0),
            } for key in labels if counts.get(key, 0)],
            "tracked": tracked,
            "on_time_percent": round(100.0 * settled / tracked) if tracked else 0,
            "worst": [{
                "id": request.id,
                "name": request.name,
                "partner": request.partner_id.display_name,
                "state_label": state_label(self.env, request.state),
                "role": role_label(self.env, verdict["role"]) if verdict["role"] else "",
                "overdue_hours": hours,
                "overdue_label": request._format_hours(hours),
                "sla_state": verdict["state"],
            } for hours, request, verdict in worst[:limit]],
            "escalations": [{
                "id": escalation.id,
                "request_id": escalation.request_id.id,
                "name": escalation.request_id.name,
                "partner": escalation.partner_id.display_name,
                "step": state_label(self.env, escalation.state),
                "role": role_label(self.env, escalation.role),
                "level": escalation.level,
                "triggered_on": fields.Datetime.to_string(escalation.triggered_on),
                "acknowledged": bool(escalation.acknowledged_on),
            } for escalation in escalations],
        }

    @api.model
    def get_document_health_data(self, limit=12):
        """What is wrong with the paperwork in the building.

        "A file is attached" is never counted as evidence: every figure below
        reads the review outcome, which is the Certifications Division's and
        nobody else's.
        """
        self._analytics_guard()
        Document = self.env["dma.request.document"]
        open_files = [("request_id.state", "not in", list(CLOSED_STATES))]

        def count(extra):
            return Document.search_count(open_files + extra)

        blocked = self.search([
            ("state", "in", list(SLA_TRACKED_STATES)),
            ("blocking_document_count", ">", 0),
        ], order="blocking_document_count desc, id asc", limit=limit)

        by_type = Document._read_group(
            domain=open_files + [("is_blocking", "=", True)],
            groupby=["type_id"],
            aggregates=["__count"],
            order="__count DESC",
            limit=10,
        )
        return {
            "rtl": self.env["res.lang"]._lang_get(
                self.env.lang or "en_US"
            ).direction == "rtl",
            "totals": {
                "pending_review": count([
                    ("is_provided", "=", True), ("review_result", "=", "pending"),
                ]),
                "invalid": count([("review_result", "=", "invalid")]),
                "missing": count([
                    ("is_required", "=", True), ("review_result", "=", "missing"),
                ]),
                "expiring": count([("validity_state", "=", "expiring")]),
                "expired": count([("validity_state", "=", "expired")]),
                "replaced": count([("superseded_count", ">", 0)]),
            },
            "blocked_requests": [{
                "id": request.id,
                "name": request.name,
                "partner": request.partner_id.display_name,
                "state_label": state_label(self.env, request.state),
                "blocking": request.blocking_document_count,
                "progress": request.checklist_progress,
            } for request in blocked],
            "worst_documents": [{
                "id": doc_type.id,
                "label": doc_type.display_name,
                "count": number,
            } for doc_type, number in by_type],
        }
