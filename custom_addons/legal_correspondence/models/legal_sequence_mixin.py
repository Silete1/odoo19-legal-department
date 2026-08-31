import logging
import re
from datetime import date

from psycopg2 import errors as pgerrors

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL, date_utils, index_exists
from odoo.tools.misc import format_date

_logger = logging.getLogger(__name__)


class LegalSequenceMixin(models.AbstractModel):
    """A register number the clerk may type, that still behaves like a sequence.

    This is a deliberate port of ``account``'s ``sequence.mixin`` rather than a
    use of ``ir.sequence``, and the reason is the paper book. An Iraqi صادر
    register is a physical object; its numbers are quoted over the telephone,
    written on envelopes and copied into the ministry's own book. Three things
    follow, none of which ``ir.sequence`` can do:

    * The clerk must be able to **type** the number. A department that migrates
      in October is at 1,247 and will not restart at 1. So the number is a plain
      editable field, and the *next* one is deduced from the *last* one rather
      than from a counter nobody can see.
    * The **format** is whatever the department already writes - ``1247``,
      ``2026/1247``, ``ق/2026/1247`` - and it must be inferred, not configured,
      because the department will not describe its own format correctly and will
      discover the mismatch on the letter that is already at the counter.
    * The **year reset** must be deduced from that same format. A book numbered
      ``2026/1247`` restarts on 1 January; one numbered ``1247`` does not. The
      software follows the book; it does not impose a convention on it.

    We do not simply depend on ``account`` to get this: ``account`` drags a
    chart of accounts, a fiscal year and a tax engine into a legal department
    that has no use for any of them.

    What was simplified from the upstream mixin, and why:

    * The ``year_range`` and ``year_range_month`` formats (``2024-2025/0001``)
      are dropped. They exist for fiscal years that straddle a calendar year;
      Iraqi correspondence registers reset on 1 January with the Gregorian year,
      and every extra regex is one more way for the deduction to guess wrongly.
    * The per-transaction sequence cache is dropped. It exists so that posting a
      thousand invoices does not take a thousand savepoints. A legal department
      registers letters one at a time, at the speed a human types, and the
      savepoint loop alone is both correct and fast enough.
    * ``_is_end_of_seq_chain`` and the resequencing tooling are dropped: nothing
      here may be deleted or resequenced, because a registered entry is voided
      rather than removed.
    """

    _name = "legal.sequence.mixin"
    _description = "Editable Register Numbering"

    #: The stored Char holding the number, the stored Date it must agree with,
    #: and the column the chain is scoped to (the register book).
    _sequence_field = "name"
    _sequence_date_field = "date"
    _sequence_index = False

    _re_prefix1 = r"(?P<prefix1>.*?)"
    _re_prefix3 = r"(?P<prefix3>\D+?)"
    _re_seq = r"(?P<seq>\d*)"
    _re_month = r"(?P<month>(0[1-9]|1[0-2]))"
    # ``(19|20|21)`` catches the 19th, 20th and 21st century prefixes.
    _re_year = r"(?P<year>((?<=\D)|(?<=^))((19|20|21)\d{2}|(\d{2}(?=\D))))"
    _re_suffix = r"(?P<suffix>\D*?)"

    _sequence_monthly_regex = (
        r"^" + _re_prefix1 + _re_year + r"(?P<prefix2>\D*?)" + _re_month
        + _re_prefix3 + _re_seq + _re_suffix + r"$"
    )
    _sequence_yearly_regex = (
        r"^" + _re_prefix1 + r"(?P<year>((?<=\D)|(?<=^))((19|20|21)?\d{2}))"
        + r"(?P<prefix2>\D+?)" + _re_seq + _re_suffix + r"$"
    )
    _sequence_fixed_regex = r"^" + _re_prefix1 + r"(?P<seq>\d{0,9})" + _re_suffix + r"$"

    sequence_prefix = fields.Char(compute="_compute_split_sequence", store=True)
    sequence_number = fields.Integer(compute="_compute_split_sequence", store=True)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def init(self):
        """The composite index the "what was the last number" query needs.

        Without it, allocating a number in a register with fifty thousand rows
        is a sequential scan, once per letter, in front of a clerk waiting to
        print.
        """
        if self._abstract or not self._sequence_index:
            return
        index_name = self._table + "_sequence_index"
        if not index_exists(self.env.cr, index_name):
            self.env.cr.execute(
                SQL(
                    """
                    CREATE INDEX %(index_name)s ON %(table)s
                        (%(sequence_index)s, sequence_prefix desc, sequence_number desc, %(field)s);
                    CREATE INDEX %(index2_name)s ON %(table)s
                        (%(sequence_index)s, id desc, sequence_prefix);
                    """,
                    sequence_index=SQL.identifier(self._sequence_index),
                    index_name=SQL.identifier(index_name),
                    index2_name=SQL.identifier(index_name + "2"),
                    table=SQL.identifier(self._table),
                    field=SQL.identifier(self._sequence_field),
                )
            )
        unique_index = self.env.execute_query(
            SQL(
                """
                SELECT 1
                  FROM pg_class t
                  JOIN pg_index ix ON t.oid = ix.indrelid
                  JOIN pg_attribute a ON a.attrelid = t.oid
                                     AND a.attnum = ANY(ix.indkey)
                 WHERE t.relkind = 'r'
                   AND t.relname = %(table)s
                   AND t.relnamespace = current_schema::regnamespace
                   AND a.attname = %(column)s
                   AND ix.indisunique
                """,
                table=self._table,
                column=self._sequence_field,
            )
        )
        if not unique_index:
            # Allocation takes its lock by *updating a row covered by a unique
            # index*. With no such index there is no lock, and two clerks
            # registering in the same second get the same number.
            _logger.warning(
                "legal.sequence.mixin has no unique index on %s.%s; concurrent "
                "registrations may duplicate a register number.",
                self._table,
                self._sequence_field,
            )

    # ------------------------------------------------------------------
    # Splitting a written number into prefix and counter
    # ------------------------------------------------------------------
    @api.depends(lambda self: [self._sequence_field])
    def _compute_split_sequence(self):
        for record in self:
            sequence = record[record._sequence_field] or ""
            regex = self._make_regex_non_capturing(
                record._sequence_fixed_regex.replace(r"?P<seq>", "")
            )
            matching = re.match(regex, sequence)
            record.sequence_prefix = sequence[: matching.start(1)]
            record.sequence_number = int(matching.group(1) or 0)

    def _make_regex_non_capturing(self, regex):
        """Turn ``(?P<name>...)`` into ``(?:...)`` so only one group is left."""
        return re.sub(r"\?P<\w+>", "?:", regex)

    @api.model
    def _deduce_sequence_number_reset(self, name):
        """Does the book this number came from restart, and when?

        Deduced from the number itself, because that is the only evidence which
        cannot be wrong: ``2026/1247`` restarts on 1 January, ``ق/03/1247``
        restarts monthly, ``1247`` never restarts.
        """
        for regex, ret_val, requirements in [
            (self._sequence_monthly_regex, "month", ["seq", "month", "year"]),
            (self._sequence_yearly_regex, "year", ["seq", "year"]),
            (self._sequence_fixed_regex, "never", ["seq"]),
        ]:
            match = re.match(regex, name or "")
            if match and all(
                match.groupdict().get(req) is not None for req in requirements
            ):
                return ret_val
        raise ValidationError(
            _(
                "A register number must contain a digit group the software can "
                "increment, for example 1247, 2026/1247 or ق/2026/1247. "
                "'%(number)s' does not.",
                number=name,
            )
        )

    def _get_sequence_date_range(self, reset):
        ref_date = fields.Date.to_date(self[self._sequence_date_field])
        if reset == "year":
            return (date(ref_date.year, 1, 1), date(ref_date.year, 12, 31))
        if reset == "month":
            return date_utils.get_month(ref_date)
        if reset == "never":
            return (date(1, 1, 1), date(9999, 12, 31))
        raise NotImplementedError(reset)

    def _get_sequence_format_param(self, previous):
        """Take a written number apart into a format string and its values."""
        sequence_number_reset = self._deduce_sequence_number_reset(previous)
        regex = self._sequence_fixed_regex
        if sequence_number_reset == "year":
            regex = self._sequence_yearly_regex
        elif sequence_number_reset == "month":
            regex = self._sequence_monthly_regex
        format_values = re.match(regex, previous).groupdict()
        format_values["seq_length"] = len(format_values["seq"])
        format_values["year_length"] = len(format_values.get("year") or "")
        if not format_values.get("seq") and "prefix1" in format_values:
            # No counter at all: what looked like a prefix and a suffix is
            # really just a prefix.
            format_values["prefix1"] = format_values["suffix"]
            format_values["suffix"] = ""
        for field in ("seq", "year", "month"):
            format_values[field] = int(format_values.get(field) or 0)

        placeholders = re.findall(r"\b(prefix\d|seq|suffix\d?|year|month)\b", regex)
        format_string = "".join(
            "{seq:0{seq_length}d}"
            if s == "seq"
            else "{month:02d}"
            if s == "month"
            else "{year:0{year_length}d}"
            if s == "year"
            else "{%s}" % s
            for s in placeholders
        )
        return format_string, format_values

    # ------------------------------------------------------------------
    # The number must agree with the date on the letter
    # ------------------------------------------------------------------
    def _truncate_year_to_length(self, year, length):
        return year % (10 ** length) if length else year

    def _sequence_matches_date(self):
        self.ensure_one()
        entry_date = fields.Date.to_date(self[self._sequence_date_field])
        sequence = self[self._sequence_field]
        if not sequence or not entry_date:
            return True
        format_values = self._get_sequence_format_param(sequence)[1]
        reset = self._deduce_sequence_number_reset(sequence)
        date_start, _date_end = self._get_sequence_date_range(reset)
        year_match = not format_values["year"] or format_values[
            "year"
        ] == self._truncate_year_to_length(
            date_start.year, len(str(format_values["year"]))
        )
        month_match = (
            not format_values["month"] or format_values["month"] == entry_date.month
        )
        return year_match and month_match

    def _must_check_constrains_date_sequence(self):
        return True

    @api.constrains(lambda self: (self._sequence_field, self._sequence_date_field))
    def _constrains_date_sequence(self):
        """Refuse 2025/0148 dated in 2026.

        A number that disagrees with its own date means either the date was
        mistyped or the number was reused, and both are how a register quietly
        stops matching the book.
        """
        for record in self:
            if not record._must_check_constrains_date_sequence():
                continue
            entry_date = fields.Date.to_date(record[record._sequence_date_field])
            sequence = record[record._sequence_field]
            if sequence and entry_date and not record._sequence_matches_date():
                raise ValidationError(
                    _(
                        "The %(date_field)s (%(date)s) does not agree with the "
                        "register number %(sequence)s. Either the date or the "
                        "number is wrong; clear the number to have one allocated.",
                        date_field=record._fields[
                            record._sequence_date_field
                        ]._description_string(self.env),
                        date=format_date(self.env, entry_date),
                        sequence=sequence,
                    )
                )

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------
    def _get_last_sequence_domain(self, relaxed=False):
        """SQL WHERE clause selecting the chain this record belongs to.

        Overridden by the inheriting model. ``relaxed`` means "look outside the
        current period", used to find the *shape* of last year's numbers when
        this year has none yet.
        """
        self.ensure_one()
        return "", {}

    def _get_starting_sequence(self):
        """What the first number of a brand-new chain looks like."""
        self.ensure_one()
        return "00000000"

    def _get_last_sequence(self, relaxed=False, with_prefix=None):
        """The highest number already written in this chain.

        Highest by ``sequence_number`` *within the prefix of the most recent
        row*, which is why a prefix is changed at the turn of a year and never
        in March.
        """
        self.ensure_one()
        field = self._fields.get(self._sequence_field)
        if not field or not field.store:
            raise ValidationError(_("%s is not a stored field", self._sequence_field))
        where_string, param = self._get_last_sequence_domain(relaxed)
        if self._origin.id:
            where_string += " AND id != %(id)s "
            param["id"] = self._origin.id
        if with_prefix is not None:
            where_string += " AND sequence_prefix = %(with_prefix)s "
            param["with_prefix"] = with_prefix

        query = """
            SELECT {field} FROM {table}
            {where_string}
            AND sequence_prefix = (
                SELECT sequence_prefix FROM {table} {where_string} ORDER BY id DESC LIMIT 1
            )
            ORDER BY sequence_number DESC
            LIMIT 1
        """.format(field=self._sequence_field, table=self._table, where_string=where_string)
        self.flush_model([self._sequence_field, "sequence_number", "sequence_prefix"])
        self.env.cr.execute(query, param)
        return (self.env.cr.fetchone() or [None])[0]

    def _get_next_sequence_format(self):
        last_sequence = self._get_last_sequence()
        new = not last_sequence
        if new:
            # Nothing in this period. Borrow the previous period's *shape*, so a
            # book that wrote ق/2025/0148 continues as ق/2026/0001 rather than
            # inventing a format of its own.
            last_sequence = (
                self._get_last_sequence(relaxed=True) or self._get_starting_sequence()
            )

        format_string, format_values = self._get_sequence_format_param(last_sequence)
        if new:
            reset = self._deduce_sequence_number_reset(last_sequence)
            date_start, _date_end = self._get_sequence_date_range(reset)
            format_values["seq"] = 0
            format_values["year"] = self._truncate_year_to_length(
                date_start.year, format_values["year_length"]
            )
            format_values["month"] = fields.Date.to_date(
                self[self._sequence_date_field]
            ).month
        return format_string, format_values

    def _locked_increment(self, format_string, format_values):
        """Take the next free number, holding a database lock while doing it.

        The lock is taken by *updating the row itself*: the unique constraint on
        (register, number, company) means the UPDATE grabs an exclusive lock on
        the B-tree entry for that number, so a second clerk registering in the
        same second waits, discovers the number is taken and moves on to the
        next one. A savepoint is needed because that collision surfaces as a
        constraint violation the transaction must recover from.
        """
        seq = format_values.pop("seq")
        self.flush_recordset()
        with self.env.cr.savepoint(flush=False) as sp:
            while True:
                seq += 1
                sequence = format_string.format(seq=seq, **format_values)
                try:
                    self.env.cr.execute(
                        SQL(
                            "UPDATE %(table)s SET %(fname)s = %(sequence)s WHERE id = %(id)s",
                            table=SQL.identifier(self._table),
                            fname=SQL.identifier(self._sequence_field),
                            sequence=sequence,
                            id=self.id,
                        ),
                        log_exceptions=False,
                    )
                    return sequence
                except (pgerrors.ExclusionViolation, pgerrors.UniqueViolation):
                    sp.rollback()

    def _set_next_sequence(self):
        self.ensure_one()
        format_string, format_values = self._get_next_sequence_format()
        sequence = self._locked_increment(format_string, format_values)
        # The raw UPDATE above is invisible to the ORM cache, so write the same
        # value through the ORM. The context flag lets the inheriting model's
        # write lock recognise its own allocation and stand aside.
        self.with_context(legal_allocating_number=True)[self._sequence_field] = sequence
        self._compute_split_sequence()
        return sequence
