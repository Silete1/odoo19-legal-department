# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The numbers behind the directorate workspace.

Kept apart from the workflow model on purpose: this file answers questions
*about* the caseload rather than moving files through it, and the two have
different reasons to change.

Three rules hold everywhere below.

**Everything is counted server side.** The queue definitions live once, in
``ROLE_QUEUE_STATES``, and the browser never re-derives them. ``_read_group``
calls ``check_access`` and ``_search``, so record rules apply to every
aggregate without the caller doing anything.

**Nothing is published that the schema cannot support.** There is no snapshot
table, so there is no way to know how many files were stalled six weeks ago.
The workspace therefore shows history only where a dated column exists -
``submission_date``, ``issue_date`` and ``dma.approval.line.date`` - and shows
the present everywhere else. A trend line drawn from a query that cannot answer
the question is a fabricated number on a government screen.

**A statistic says how many files it was measured on.** A median drawn from
four files is noise, and a director will quote it to a minister, so below
:data:`COHORT_FLOOR` the workspace reports the cohort and refuses the
percentile.
"""
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models

from .dma_constants import (
    AGE_BANDS,
    COHORT_FLOOR,
    IN_PROCESS_STATES,
    ROLE_SELECTION,
    STATE_PENDING_ROLE,
    role_label,
    state_label,
)

class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    # ==================================================================
    # Shared definitions
    # ==================================================================
    @api.model
    def _pending_roles_from(self, state, finance_signed, operations_signed):
        """Which departments still owe a move on a file in this state.

        The one definition, used by :meth:`_pending_roles` on a record and by
        the aggregates below on raw column values. The dual confirmation is the
        only step with two responsible departments at once, and attributing
        such a file to just one of them - which is what ``pending_group`` does,
        since it keeps ``roles[0]`` - tells Operations it has nothing stalled
        while it does.
        """
        if state == "dual_confirm":
            roles = []
            if not finance_signed:
                roles.append("finance")
            if not operations_signed:
                roles.append("operations")
            return roles or ["finance"]
        role = STATE_PENDING_ROLE.get(state)
        return [role] if role else []

    # ==================================================================
    # Aggregates
    # ==================================================================
    @api.model
    def _dashboard_ageing(self, request_ids):
        """How long the open caseload has been standing still, by department.

        Age is measured from the last thing that happened to the file, which is
        the question "whose desk is blocked" - not from submission, which is the
        question "is this applicant being failed". The worklist carries the
        second number per file; this carries the first.
        """
        blank = {"labels": [], "bands": [], "totals": [], "sufficient": False,
                 "stuck_total": 0, "worst": False}
        if not request_ids:
            return blank

        self.env.cr.execute(
            """
            SELECT r.state,
                   r.finance_confirmed_sop_fee,
                   r.operations_confirmed_sop,
                   EXTRACT(EPOCH FROM (%s - COALESCE(MAX(l.date), r.create_date)))
                       / 86400.0 AS days
              FROM dma_accreditation_request r
              LEFT JOIN dma_approval_line l ON l.request_id = r.id
             WHERE r.id = ANY(%s)
             GROUP BY r.id, r.state, r.finance_confirmed_sop_fee,
                      r.operations_confirmed_sop, r.create_date
            """,
            (fields.Datetime.now(), list(request_ids)),
        )

        # role -> band -> count. A file awaiting two departments is counted
        # under both, which is the point; the caption says so.
        roles = [key for key, _label in ROLE_SELECTION if key != "manager"]
        tally = {role: {band: 0 for band, _lo, _hi in AGE_BANDS} for role in roles}
        for state, finance_signed, operations_signed, days in self.env.cr.fetchall():
            days = float(days or 0.0)
            for band, low, high in AGE_BANDS:
                if days >= low and (high is None or days < high):
                    break
            for role in self._pending_roles_from(
                state, finance_signed, operations_signed,
            ):
                if role in tally:
                    tally[role][band] += 1

        present = [role for role in roles if any(tally[role].values())]
        if not present:
            return blank

        totals = [sum(tally[role].values()) for role in present]
        stuck = [tally[role]["stuck"] for role in present]
        worst = present[stuck.index(max(stuck))] if max(stuck) else False
        return {
            "labels": [role_label(self.env, role) for role in present],
            "roles": present,
            "bands": [
                {
                    "key": band,
                    "label": {
                        "fresh": self.env._("up to 3 days"),
                        "slipping": self.env._("3 to 7 days"),
                        "stuck": self.env._("over 7 days"),
                    }[band],
                    "data": [tally[role][band] for role in present],
                }
                for band, _lo, _hi in AGE_BANDS
            ],
            "totals": totals,
            "stuck": stuck,
            "stuck_total": sum(stuck),
            "worst": role_label(self.env, worst) if worst else False,
            "sufficient": True,
        }

    @api.model
    def _dashboard_cycle_time(self, request_ids):
        """How long each step actually takes, measured on finished spans.

        A step's span runs from the moment the file arrived to the moment it
        left, so the several sign-offs the dual confirmation records collapse
        into one wait rather than three instant ones.
        """
        empty = {"rows": [], "sufficient": False, "cohort": 0, "slowest": False}
        if not request_ids:
            return empty

        self.env.cr.execute(
            """
            WITH spans AS (
                SELECT l.request_id, l.step, MAX(l.date) AS left_at
                  FROM dma_approval_line l
                 WHERE l.request_id = ANY(%s)
                 GROUP BY l.request_id, l.step
            ),
            waits AS (
                SELECT s.step,
                       EXTRACT(EPOCH FROM (
                           s.left_at - COALESCE(
                               LAG(s.left_at) OVER (
                                   PARTITION BY s.request_id ORDER BY s.left_at
                               ),
                               r.create_date
                           )
                       )) AS secs
                  FROM spans s
                  JOIN dma_accreditation_request r ON r.id = s.request_id
            )
            SELECT step,
                   count(*) AS n,
                   percentile_cont(0.5) WITHIN GROUP (ORDER BY secs) AS median_secs,
                   percentile_cont(0.9) WITHIN GROUP (ORDER BY secs) AS p90_secs
              FROM waits
             WHERE secs > 0
             GROUP BY step
            """,
            (list(request_ids),),
        )

        by_step = {
            step: (int(count), float(median or 0), float(p90 or 0))
            for step, count, median, p90 in self.env.cr.fetchall()
        }
        cohort = max((count for count, _m, _p in by_step.values()), default=0)
        rows = []
        for step in IN_PROCESS_STATES:
            count, median, p90 = by_step.get(step, (0, 0.0, 0.0))
            if not count:
                continue
            rows.append({
                "key": step,
                "label": state_label(self.env, step),
                "count": count,
                "median_days": round(median / 86400.0, 1),
                "p90_days": round(p90 / 86400.0, 1),
                "domain": [("state", "=", step)],
            })
        rows.sort(key=lambda row: row["median_days"], reverse=True)
        longest = rows[0]["median_days"] if rows else 0
        for row in rows:
            row["percent"] = (
                round(100.0 * row["median_days"] / longest) if longest else 0
            )
        return {
            "rows": rows,
            "cohort": cohort,
            # Under the floor the numbers are still shown, but the workspace
            # says what they were measured on rather than presenting a median
            # of four files as a fact.
            "sufficient": cohort >= COHORT_FLOOR,
            "slowest": rows[0]["label"] if rows else False,
        }

    @api.model
    def _dashboard_throughput(self, start):
        """Applications received against accreditations issued, by month."""
        received = dict(
            (group[0].strftime("%Y-%m") if group[0] else "", group[1])
            for group in self._read_group(
                [("submission_date", ">=", start)],
                groupby=["submission_date:month"],
                aggregates=["__count"],
            )
        )
        issued = dict(
            (group[0].strftime("%Y-%m") if group[0] else "", group[1])
            for group in self._read_group(
                [("issue_date", ">=", start)],
                groupby=["issue_date:month"],
                aggregates=["__count"],
            )
        )
        months = sorted(set(received) | set(issued))
        months = [month for month in months if month]
        if not months:
            return {"labels": [], "series": [], "sufficient": False, "net": 0}

        # Fill the gaps: a month nobody worked is information, and leaving it
        # out would compress the axis and hide the gap.
        first = fields.Date.to_date(months[0] + "-01")
        last = fields.Date.to_date(months[-1] + "-01")
        span, cursor = [], first
        while cursor <= last:
            span.append(cursor)
            cursor += relativedelta(months=1)

        labels = [fields.Date.to_string(month)[:7] for month in span]
        received_series = [received.get(month.strftime("%Y-%m"), 0) for month in span]
        issued_series = [issued.get(month.strftime("%Y-%m"), 0) for month in span]
        return {
            "labels": labels,
            "series": [
                {"key": "received", "label": self.env._("Applications received"),
                 "data": received_series},
                {"key": "issued", "label": self.env._("Accreditations issued"),
                 "data": issued_series},
            ],
            "net": sum(received_series) - sum(issued_series),
            "sufficient": len(span) >= 2,
        }

    @api.model
    def _dashboard_returns(self, start):
        """Which step sends work back, and how often."""
        groups = self.env["dma.approval.line"]._read_group(
            [("decision", "in", ("returned", "rejected")), ("date", ">=", start)],
            groupby=["step", "decision"],
            aggregates=["__count"],
        )
        tally = {}
        for step, decision, count in groups:
            entry = tally.setdefault(step, {"returned": 0, "rejected": 0})
            entry[decision] = count
        rows = [
            {
                "key": step,
                "label": state_label(self.env, step),
                "returned": counts["returned"],
                "rejected": counts["rejected"],
                "total": counts["returned"] + counts["rejected"],
                "domain": [("state", "=", step)],
            }
            for step, counts in tally.items()
        ]
        rows.sort(key=lambda row: row["total"], reverse=True)
        worst = max((row["total"] for row in rows), default=0)
        for row in rows:
            row["percent"] = round(100.0 * row["total"] / worst) if worst else 0
        return {
            "rows": rows[:8],
            "total": sum(row["total"] for row in rows),
            "sufficient": bool(rows),
            "worst": rows[0]["label"] if rows else False,
        }
