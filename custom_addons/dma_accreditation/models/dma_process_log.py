# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The approval log, read as a process event log.

The module already keeps an immutable line for every workflow transition. That
log is a complete record of the process - who decided what, when - and this
turns it into something a database can *aggregate*: three stored, indexed
columns saying when the step began, how long it lasted, and whether the entry
is the one that closed it.

Nothing here is written by hand. All three are computed off the log itself, so
they can never disagree with it, an upgrade backfills every historical file for
free, and the log stays as immutable as it was.

Why the durations live here rather than on the request
------------------------------------------------------
A duration that is not a stored column cannot be grouped, averaged or ordered
by the database, so every performance question would degrade into loading every
file and adding up timestamps in Python. Stored here, "median time in the Legal
Department review over the last year" is one indexed ``_read_group``.
"""
from collections import defaultdict

from odoo import api, fields, models
from odoo.models import parse_read_group_spec
from odoo.tools import SQL

#: Extra aggregate verbs understood by :meth:`_read_group_select`.
#:
#: PostgreSQL computes an exact percentile with ``PERCENTILE_CONT``, but Odoo's
#: aggregate whitelist stops at avg/min/max. A distribution is the whole point
#: of a waiting time - an average hides the file that sat for three months
#: behind twenty that took an afternoon - so the two verbs the Directorate
#: actually needs are added through the documented per-model hook rather than
#: by pulling every row into Python.
PERCENTILE_AGGREGATES = {
    "p50": 0.5,
    "p90": 0.9,
    "p95": 0.95,
}


class DmaApprovalLine(models.Model):
    _inherit = "dma.approval.line"

    entered_on = fields.Datetime(
        string="Step Entered On", compute="_compute_process_timing", store=True,
        index=True,
        help="When the file reached the step this decision was taken on.",
    )
    duration_hours = fields.Float(
        string="Step Duration (hours)", compute="_compute_process_timing", store=True,
        # A Float aggregates as a SUM by default, which is meaningless for a
        # duration: twenty files that each took a day are not "twenty days".
        aggregator="avg",
        help="How long the file had been on the step when this decision was "
             "taken.",
    )
    is_transition = fields.Boolean(
        string="Closed the Step", compute="_compute_process_timing", store=True,
        index=True,
        help="True on the entry that actually moved the file on. The parallel "
             "dual confirmation writes an entry per department while the file "
             "stays put; only the last of them closed the step.",
    )

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------
    @api.depends(
        "request_id.state", "request_id.create_date",
        "request_id.approval_line_ids.step", "request_id.approval_line_ids.date",
    )
    def _compute_process_timing(self):
        """Reconstruct entry, duration and closure for a batch of entries.

        Grouped by file and sorted once per file rather than once per entry:
        the answer for any single entry depends on its neighbours, so doing it
        naively would re-sort the whole log for every line of it.
        """
        by_request = defaultdict(lambda: self.browse())
        for line in self:
            by_request[line.request_id] |= line

        for request, lines in by_request.items():
            ordered = list(request._ordered_approval_lines())
            entry = request.create_date
            timings = {}
            for index, line in enumerate(ordered):
                if index and ordered[index - 1].step != line.step:
                    # The previous entry named another step, so it is the one
                    # that closed it - and this file arrived here then.
                    entry = ordered[index - 1].date
                following = ordered[index + 1] if index + 1 < len(ordered) else None
                if following is not None:
                    closed = following.step != line.step
                else:
                    # The last entry of the log closed its step unless the file
                    # is still sitting on it.
                    closed = request.state != line.step
                timings[line.id] = (entry, closed)
            for line in lines:
                entered, closed = timings.get(line.id, (request.create_date, False))
                line.entered_on = entered
                line.is_transition = closed
                line.duration_hours = max(
                    (line.date - entered).total_seconds() / 3600.0, 0.0,
                ) if (line.date and entered) else 0.0

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    def _read_group_select(self, aggregate_spec, query):
        """Teach ``_read_group`` two percentile verbs on top of Odoo's own.

        Odoo 19 validates aggregates against a closed whitelist (``sum``,
        ``avg``, ``min``, ``max``, ...) but exposes this per-model hook and
        accepts any word as the function name, so ``duration_hours:p50`` is a
        supported extension rather than a patch. The SQL is injected into the
        query ``_search`` built, which means the record rules of the log still
        apply to every aggregate.
        """
        fname, _property_name, func = parse_read_group_spec(aggregate_spec)
        if func in PERCENTILE_AGGREGATES and fname in self._fields:
            return SQL(
                "PERCENTILE_CONT(%s) WITHIN GROUP (ORDER BY %s)",
                PERCENTILE_AGGREGATES[func],
                self._field_to_sql(self._table, fname, query),
            )
        return super()._read_group_select(aggregate_spec, query)
