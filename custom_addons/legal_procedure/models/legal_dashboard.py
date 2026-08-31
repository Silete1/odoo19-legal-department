# Part of Legal Department. See LICENSE file for full copyright and licensing details.
"""Every figure, every colour and every Arabic sentence the OWL screens draw.

The three client screens of this module - the Mail Room, My Desk and the
per-body desks - are pure renderers. Not one threshold, not one working-day
subtraction, not one drill-through domain and not one translated string is
composed in the browser; all of it is built here and shipped as a plain dict.
That is not a stylistic preference. It is what keeps the module *configurable*:
the rail draws three phases or twelve without a line of JavaScript changing,
and the whole of the logic stays in Python where the tests are.

Two consequences follow, and both are visible everywhere below.

**Everything is probed before it is read.** This file is written alongside the
models it reports on, and it will outlive several of their field names. So it
never assumes: it asks the registry whether a model exists, asks the model
whether a field exists, and asks a Selection which values it actually offers.
A column whose model has not been written yet renders as its own empty state
with an honest sentence in it, which is a far better failure than a traceback
on the landing screen of the application.

**Ageing is counted in the body's working days, never in wall-clock days.**
An Iraqi office works Sunday to Thursday and closes for Eid. A chase list that
counts Fridays cries wolf every weekend, and a clerk who has learned to ignore
the chase list has lost the only thing this module sells. ``legal.gov.body``
already carries the calendar; this reads it through
:meth:`legal.gov.body._plan_days`'s sibling, ``get_work_duration_data``.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

#: How many rows a desk column shows before deferring to its "open all" link. A
#: column is a to-do list, not a report: past about eight entries a clerk stops
#: reading rows and starts using the register screen, which sorts and filters
#: properly.
COLUMN_LIMIT = 8

#: The display scale of the ageing meter, in days. It is a *scale*, not a
#: deadline - no Iraqi body has ever published a per-step target - so the exact
#: day count always sits beside the bar and the word "target" appears nowhere
#: except where a configured service level actually says one.
AGE_SCALE_DAYS = 14

#: Above this many days at one step the row is drawn as stuck. Two weeks is the
#: point at which a file has survived a full cycle of "I will ring them
#: tomorrow" without moving.
AGE_STUCK_DAYS = 14
AGE_SLIPPING_DAYS = 7

#: Eastern Arabic numerals, for the companies that set them. Applied only to
#: prose figures - never to a register number, which must be quotable over the
#: telephone and machine-readable in a search box.
_ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


class LegalDashboard(models.AbstractModel):
    """The payload composer for the module's three OWL screens.

    Abstract rather than transient on purpose: it stores nothing, so it needs
    no table, no vacuum and no ``ir.model.access`` row of its own. Every read it
    performs goes through the ordinary ORM as the calling user, so the record
    rules that hide another officer's body apply here exactly as they do on a
    list view - the dashboard can never show a file its owner could not open.
    """

    _name = "legal.dashboard"
    _description = "Legal Department Dashboard Payloads"

    # ==================================================================
    # Probing - how this file survives being written beside its models
    # ==================================================================
    def _has_model(self, name):
        """Is the model in the registry at all?"""
        return name in self.env

    def _model(self, name):
        """The model, or ``None`` - so a caller can guard with one ``if``."""
        return self.env[name] if name in self.env else None

    def _field(self, model, *candidates):
        """The first of ``candidates`` the model actually has.

        Field names are the part of a sibling module most likely to be renamed
        between the day this is written and the day it is read, so every access
        goes through here and every caller has a fallback.
        """
        if model is None:
            return None
        for name in candidates:
            if name in model._fields:
                return name
        return None

    def _selection_has(self, model, field_name, value):
        """Does that Selection actually offer that value?

        A domain leaf on a value the Selection does not carry is not an error
        in Postgres - it silently matches nothing - which would show a clerk an
        empty column and no reason for it.
        """
        if model is None or field_name not in model._fields:
            return False
        field = model._fields[field_name]
        try:
            return value in dict(field._description_selection(self.env))
        except Exception:  # noqa: BLE001 - a broken Selection must not blank the page
            _logger.debug("Could not read the selection of %s.%s", model._name, field_name)
            return False

    def _safe_search(self, model, domain, order=None, limit=None):
        """Search, and degrade to an empty recordset rather than to a traceback.

        The dashboard is the landing screen of the application. A domain built
        from a sibling model that has changed under it must cost the reader one
        empty column, not the whole page.

        An ``AccessError`` is deliberately NOT caught. It is not a defect in
        this file - it is the ORM answering the question correctly, and a
        reader who may not see a body's files should be told so rather than
        shown a screen of confident zeros. Swallowing it would turn a
        permissions problem into a data problem, which is the harder of the two
        to notice and the worse of the two to act on.
        """
        if model is None:
            return None
        try:
            return model.search(domain, order=order, limit=limit)
        except (AccessError, UserError):
            raise
        except Exception:  # noqa: BLE001
            _logger.warning(
                "legal.dashboard could not search %s with %s", model._name, domain,
                exc_info=True,
            )
            return model.browse()

    def _safe_count(self, model, domain):
        """The size of the whole queue, on the same terms as the search above."""
        if model is None:
            return 0
        try:
            return model.search_count(domain)
        except (AccessError, UserError):
            raise
        except Exception:  # noqa: BLE001
            _logger.warning(
                "legal.dashboard could not count %s with %s", model._name, domain,
                exc_info=True,
            )
            return 0

    # ==================================================================
    # Presentation primitives, all of them server-side by policy
    # ==================================================================
    def _rtl(self):
        """Which way round the reader's language runs.

        Odoo mirrors the interface by piping the compiled CSS through rtlcss
        and never sets ``direction`` on the document, so a component that lays
        itself out has to be told. The flag travels in every payload.
        """
        try:
            return self.env["res.lang"]._lang_get(self.env.lang).direction == "rtl"
        except Exception:  # noqa: BLE001
            return False

    def _numerals(self):
        """Western or Arabic-Indic digits, per the company setting."""
        company = self.env.company
        return getattr(company, "legal_numeral_system", "western") or "western"

    def _digits(self, text):
        """Render a figure in the company's numeral system.

        Applied to prose - "٦ أيام عمل" - and never to a register number, a
        reference or a date, because those are quoted back over the telephone
        and typed into a search box.
        """
        text = str(text)
        return text.translate(_ARABIC_INDIC) if self._numerals() == "arabic" else text

    def _days_label(self, days):
        """A day count as a sentence fragment, in the reader's language."""
        return self.env._("%s day(s)", self._digits(int(days)))

    def _working_days_label(self, days):
        return self.env._("%s working day(s)", self._digits(int(days)))

    def _date_label(self, value):
        """A date the reader can compare against the paper in their hand."""
        if not value:
            return ""
        try:
            return fields.Date.to_string(fields.Date.to_date(value))
        except Exception:  # noqa: BLE001
            return str(value)[:10]

    def _meter_label(self, done, total):
        """The document counter as ONE atomic chip.

        ``f"{done} / {total}"`` composed here rather than as two spans in the
        template, because the Unicode bidi algorithm reorders a bare "3 / 4"
        into "4 / 3" inside an Arabic paragraph. The component pins the span
        ``dir="ltr"`` as well; belt and braces, and both are cheap.
        """
        return f"{int(done)} / {int(total)}"

    def _age_band(self, days):
        """The three status hues, used identically everywhere ageing is shown.

        Never the sole carrier of the meaning: every row that gets a band also
        gets the day count in figures beside it.
        """
        if days >= AGE_STUCK_DAYS:
            return "stuck"
        if days >= AGE_SLIPPING_DAYS:
            return "slipping"
        return "fresh"

    def _age_percent(self, days):
        return min(100, int(round(100.0 * max(0, days) / AGE_SCALE_DAYS)))

    # ------------------------------------------------------------------
    # Working-day arithmetic through the body's own calendar
    # ------------------------------------------------------------------
    def _working_days_since(self, body, since):
        """Days of *that body's* working time between ``since`` and now.

        "Ten working days at the Registrar" is a different number from ten
        days, and it is the only number an Iraqi clerk recognises. Falls back to
        the company calendar and then to plain calendar days, so a body
        configured in a hurry still produces a usable figure rather than an
        error - the same ladder :meth:`legal.gov.body._plan_days` uses.
        """
        if not since:
            return 0
        now = fields.Datetime.now()
        try:
            since = fields.Datetime.to_datetime(since)
        except Exception:  # noqa: BLE001
            return 0
        if since >= now:
            return 0
        calendar = None
        if body is not None and body and "resource_calendar_id" in body._fields:
            calendar = body.resource_calendar_id
        calendar = calendar or self.env.company.resource_calendar_id
        if calendar:
            try:
                return int(calendar.get_work_duration_data(since, now, compute_leaves=True)["days"])
            except Exception:  # noqa: BLE001
                _logger.debug("Falling back to calendar days for %s", calendar)
        return max(0, (now - since).days)

    # ------------------------------------------------------------------
    # The clock, in words - our clock or theirs, which is the headline metric
    # ------------------------------------------------------------------
    def _clock(self, kind, days, target=None, body_label=""):
        """The one line that says whose delay this is.

        The distinction between "بانتظارنا" and "لدى الجهة" is the whole
        argument of the module: a legal department is measured on the first and
        can only chase the second. So the badge states which in words, and only
        then colours itself - colour never travels alone, and every verdict
        ships an icon and the written label beside its hue.
        """
        if kind == "at_body":
            kind_label = (
                self.env._("With %s", body_label) if body_label
                else self.env._("With the body")
            )
            age_label = self.env._(
                "With them for %s", self._working_days_label(days)
            )
            icon = "fa-institution"
        else:
            kind_label = self.env._("Waiting on us")
            age_label = self.env._("On our desk for %s", self._working_days_label(days))
            icon = "fa-hand-o-right"

        state = "on_track"
        overdue_label = ""
        target_label = ""
        if target:
            target_label = self.env._("Target %s", self._working_days_label(target))
            if days > target:
                state = "overdue"
                overdue_label = self.env._(
                    "%s past the target", self._working_days_label(days - target)
                )
                icon = "fa-exclamation-triangle"
            elif days >= max(1, int(target * 0.8)):
                state = "warning"
                icon = "fa-clock-o"
        elif days >= AGE_STUCK_DAYS:
            state = "warning"
            icon = "fa-clock-o"

        state_label = {
            "on_track": self.env._("On track"),
            "warning": self.env._("Due soon"),
            "overdue": self.env._("Overdue"),
        }[state]
        return {
            "state": state,
            "state_label": state_label,
            "kind": kind,
            "kind_label": kind_label,
            "age": self._working_days_label(days),
            "age_label": age_label,
            "overdue_label": overdue_label,
            "target_label": target_label,
            "icon": icon,
            "rtl": self._rtl(),
        }

    # ------------------------------------------------------------------
    # Drill-through. Composed here so the browser never invents a domain the
    # record rules would disagree with.
    # ------------------------------------------------------------------
    def _open_action(self, model, name, domain, views=None):
        if not self._has_model(model):
            return False
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "domain": domain,
            "views": views or [[False, "list"], [False, "form"]],
            "target": "current",
        }

    def _open_record(self, model, res_id):
        if not self._has_model(model):
            return False
        return {
            "type": "ir.actions.act_window",
            "res_model": model,
            "res_id": res_id,
            "views": [[False, "form"]],
            "target": "current",
        }

    # ==================================================================
    # THE MAIL ROOM - the default landing action
    # ==================================================================
    @api.model
    def get_mail_room_data(self):
        """The three columns of an Iraqi diwan clerk's morning.

        What arrived and has no file yet; what we sent and are still chasing;
        what has to go out today. That is the whole of a register clerk's day
        and it is the reason the Mail Room, and not a case list, is where this
        application opens.

        One call fills the page. Three calls would let the browser show three
        panels computed a second apart from three different transactions.
        """
        degraded = []
        Corr = self._model("legal.correspondence")
        if Corr is None:
            degraded.append(self.env._(
                "The correspondence register is not installed, so the incoming "
                "and awaiting-reply columns are empty."
            ))

        columns = [
            self._mail_room_incoming(Corr),
            self._mail_room_awaiting(Corr),
            self._mail_room_to_issue(degraded),
        ]
        hero, tiles = self._mail_room_head(columns)
        return {
            "rtl": self._rtl(),
            "numerals": self._numerals(),
            "title": self.env._("The Mail Room"),
            "subtitle": self.env._("What arrived, what we are chasing, what must go out"),
            "role": self._role_brief(),
            "hero": hero,
            "tiles": tiles,
            "columns": columns,
            "degraded": degraded,
        }

    def _mail_room_head(self, columns):
        """The hero and the three tiles, all derived from the columns themselves.

        Derived rather than counted a second time, because two numbers on one
        screen that disagree is worse than one number - and a hero count that
        does not match the column beneath it is exactly how a clerk learns not
        to trust the screen.
        """
        by_key = {column["key"]: column for column in columns}
        incoming = by_key.get("incoming", {})
        awaiting = by_key.get("awaiting", {})
        issue = by_key.get("issue", {})

        overdue = sum(
            1 for row in awaiting.get("rows", [])
            if (row.get("clock") or {}).get("state") == "overdue"
        )
        oldest = max(
            (row.get("waiting_days", 0) for row in awaiting.get("rows", [])),
            default=0,
        )
        waiting_for_you = incoming.get("count", 0) + issue.get("count", 0)

        hero = {
            "label": self.env._("Waiting for you"),
            "count": waiting_for_you,
            "count_label": self._digits(waiting_for_you),
            "note": (
                self.env._(
                    "%(new)s to register, %(out)s to send out",
                    new=self._digits(incoming.get("count", 0)),
                    out=self._digits(issue.get("count", 0)),
                )
                if waiting_for_you
                else self.env._("The register is clear. Nothing is waiting to be handled.")
            ),
            "oldest_label": (
                self.env._("Oldest chase: %s", self._working_days_label(oldest))
                if oldest else ""
            ),
            "action": incoming.get("action") or issue.get("action") or False,
        }

        tiles = [
            {
                "key": "overdue",
                "label": self.env._("Overdue replies"),
                "value": overdue,
                "value_label": self._digits(overdue),
                "hint": self.env._("Past the target, counted in their working days"),
                "icon": "fa-exclamation-triangle",
                "tone": "critical" if overdue else "neutral",
                "action": awaiting.get("action") or False,
            },
            {
                "key": "at_body",
                "label": self.env._("With the bodies"),
                "value": awaiting.get("count", 0),
                "value_label": self._digits(awaiting.get("count", 0)),
                "hint": self.env._("Sent, and no reply matched to it yet"),
                "icon": "fa-institution",
                "tone": "neutral",
                "action": awaiting.get("action") or False,
            },
            {
                "key": "to_issue",
                "label": self.env._("To be issued"),
                "value": issue.get("count", 0),
                "value_label": self._digits(issue.get("count", 0)),
                "hint": self.env._("Files whose next move is a letter from us"),
                "icon": "fa-paper-plane",
                "tone": "attention" if issue.get("count") else "neutral",
                "action": issue.get("action") or False,
            },
        ]
        return hero, tiles

    # -- Column one: وارد اليوم -----------------------------------------
    def _mail_room_incoming(self, Corr):
        """Registered incoming entries that belong to no file yet.

        This column is the answer to the one gap a case-centred design cannot
        close: an unprompted tax assessment, a summons or an inspection notice
        arrives with no file behind it and must be numbered the day it arrives.
        The clerk's two moves - attach it to an existing file, or open a new one
        from it - are the only two buttons on the row.
        """
        title = self.env._("Arrived today")
        hint = self.env._("Registered, and not yet attached to any file")
        empty = self.env._("Nothing new is waiting to be filed.")
        empty_hint = self.env._(
            "An incoming letter appears here the moment it is written into the "
            "register, until it is attached to a file or a new one is opened from it."
        )
        if Corr is None:
            return self._column("incoming", title, hint, empty, empty_hint, [], 0, False)

        domain = []
        direction = self._field(Corr, "direction")
        if direction and self._selection_has(Corr, direction, "in"):
            domain.append((direction, "=", "in"))
        case_field = self._field(Corr, "case_id")
        if case_field:
            domain.append((case_field, "=", False))
        # A telephone note is not post. It consumes no register number and
        # nothing arrived, so it has no business in a column headed "arrived
        # today" - it belongs to the chase it was made against.
        note_field = self._field(Corr, "is_contact_note")
        if note_field:
            domain.append((note_field, "=", False))
        state_field = self._field(Corr, "state")
        if state_field:
            states = [
                value for value in ("draft", "registered")
                if self._selection_has(Corr, state_field, value)
            ]
            if states:
                domain.append((state_field, "in", states))

        order = self._sort_clause(Corr, ("our_date desc", "id desc"))
        records = self._safe_search(Corr, domain, order=order, limit=COLUMN_LIMIT)
        rows = [self._incoming_row(record, Corr) for record in records]
        return self._column(
            "incoming", title, hint, empty, empty_hint, rows,
            self._safe_count(Corr, domain),
            self._open_action("legal.correspondence", title, domain),
        )

    def _incoming_row(self, record, Corr):
        body = self._body_of(record)
        their_ref = self._value(record, "their_number", "their_ref")
        their_date = self._value(record, "their_date")
        subject = self._value(record, "subject", "name", "display_name")
        our_number = self._value(record, "our_number", "name")
        state_field = self._field(Corr, "state")
        is_draft = bool(state_field) and record[state_field] == "draft"

        # The "link to a file" move opens the core record selector, scoped to
        # the body, so the clerk picks from that body's files rather than from
        # every file in the database. The scope is a server-composed domain for
        # the usual reason: the browser must never guess one.
        link = False
        if self._has_model("legal.case") and self._field(Corr, "case_id"):
            case_domain = []
            Case = self._model("legal.case")
            if body and self._field(Case, "body_id"):
                case_domain.append(("body_id", "=", body.id))
            link = {
                "model": "legal.case",
                "domain": case_domain,
                "title": self.env._("Attach to a file"),
            }

        return {
            "id": record.id,
            "model": "legal.correspondence",
            "our_number": our_number or "",
            "their_ref": their_ref or "",
            "their_date_label": self._date_label(their_date),
            "date_label": self._date_label(
                self._value(record, "our_date", "date", "create_date")
            ),
            "subject": subject or self.env._("(no subject recorded)"),
            "body_label": body.display_name if body else self.env._("Body not recorded"),
            "body_colour": (body.colour if body and "colour" in body._fields else 0) or 0,
            "is_draft": is_draft,
            "draft_label": self.env._("Not numbered yet") if is_draft else "",
            "attachment_id": self._attachment_of(record),
            "attachment_label": self.env._("Open the scan"),
            "link": link,
            "link_label": self.env._("Attach to a file"),
            "new_case": self._new_case_action(record, body),
            "new_case_label": self.env._("Open a new file"),
            "open": self._open_record("legal.correspondence", record.id),
        }

    def _new_case_action(self, record, body):
        """Open a file *from* this letter, with what we already know filled in.

        Composed here rather than pointing at an XML id, so the button keeps
        working whatever the wizard beside it is eventually called - and
        disappears honestly if no case model is installed at all.
        """
        Case = self._model("legal.case")
        if Case is None:
            return False
        context = {}
        if body and self._field(Case, "body_id"):
            context["default_body_id"] = body.id
        corr_field = self._field(Case, "correspondence_id", "origin_correspondence_id")
        if corr_field:
            context[f"default_{corr_field}"] = record.id
        subject = self._value(record, "subject", "name")
        if subject and self._field(Case, "subject"):
            context["default_subject"] = subject
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("New File"),
            "res_model": "legal.case",
            "views": [[False, "form"]],
            "target": "current",
            "context": context,
        }

    # -- Column two: بانتظار الرد ---------------------------------------
    def _mail_room_awaiting(self, Corr):
        """What we have sent and are still chasing, oldest first.

        Oldest first because a chase list is worked from the top down, and aged
        in the *body's* working days because that is the only number the clerk
        at the other counter would recognise. Every row offers the reminder,
        and every row also offers the telephone note - "I rang them and they
        said come back after Eid" is the single most common real event in this
        domain, and if recording it costs more than one click nobody records it
        and the chase list starts lying.
        """
        title = self.env._("Awaiting a reply")
        hint = self.env._("Sent by us, with no reply matched to it yet")
        empty = self.env._("We are not waiting on anybody.")
        empty_hint = self.env._(
            "An outgoing letter that expects an answer appears here the day it "
            "is issued, and leaves it when the reply is registered against it."
        )
        if Corr is None:
            return self._column("awaiting", title, hint, empty, empty_hint, [], 0, False)

        domain = []
        direction = self._field(Corr, "direction")
        if direction and self._selection_has(Corr, direction, "out"):
            domain.append((direction, "=", "out"))
        expects = self._field(Corr, "reply_expected", "expects_reply")
        if expects:
            domain.append((expects, "=", True))
        reply_state = self._field(Corr, "reply_state")
        if reply_state and self._selection_has(Corr, reply_state, "answered"):
            domain.append((reply_state, "!=", "answered"))
        elif self._field(Corr, "reply_id", "replied_by_id"):
            domain.append((self._field(Corr, "reply_id", "replied_by_id"), "=", False))
        state_field = self._field(Corr, "state")
        if state_field and self._selection_has(Corr, state_field, "void"):
            domain.append((state_field, "!=", "void"))

        order = self._sort_clause(Corr, ("reply_due_on asc", "our_date asc", "id asc"))
        records = self._safe_search(Corr, domain, order=order, limit=COLUMN_LIMIT)
        rows = [self._awaiting_row(record, Corr) for record in records]
        # Oldest first is the point of the column, and a fallback order that
        # could not use `reply_due_on` may not have delivered it.
        rows.sort(key=lambda row: -row["waiting_days"])
        return self._column(
            "awaiting", title, hint, empty, empty_hint, rows,
            self._safe_count(Corr, domain),
            self._open_action("legal.correspondence", title, domain),
        )

    def _awaiting_row(self, record, Corr):
        body = self._body_of(record)
        sent_on = self._value(record, "our_date", "date", "create_date")
        days = self._working_days_since(body, sent_on)
        target = self._reply_target(record, Corr)
        clock = self._clock(
            "at_body", days, target=target,
            body_label=body.display_name if body else "",
        )
        return {
            "id": record.id,
            "model": "legal.correspondence",
            "our_number": self._value(record, "our_number", "name") or "",
            "subject": self._value(record, "subject", "name") or "",
            "body_label": body.display_name if body else self.env._("Body not recorded"),
            "body_colour": (body.colour if body and "colour" in body._fields else 0) or 0,
            "date_label": self._date_label(sent_on),
            "due_label": (
                self.env._("Reply due %s", self._date_label(record[self._field(Corr, "reply_due_on")]))
                if self._field(Corr, "reply_due_on") and record[self._field(Corr, "reply_due_on")]
                else ""
            ),
            "waiting_days": days,
            "waiting_label": self._working_days_label(days),
            "age_band": self._age_band(days),
            "age_percent": self._age_percent(days),
            "clock": clock,
            "remind": self._remind_action(record, body),
            "remind_label": self.env._("Send a reminder"),
            "call": self._call_note_action(record, body),
            "call_label": self.env._("Log a telephone call"),
            "open": self._open_record("legal.correspondence", record.id),
        }

    def _reply_target(self, record, Corr):
        """The agreed number of working days for an answer, where one is set."""
        for name in ("reply_days", "reply_target_days"):
            field = self._field(Corr, name)
            if field and record[field]:
                return int(record[field])
        body = self._body_of(record)
        if body is not None and body:
            for name in ("reply_target_days", "default_reply_days"):
                if name in body._fields and body[name]:
                    return int(body[name])
        return None

    def _remind_action(self, record, body):
        """The reminder joins the original thread rather than starting one.

        Prefers the module's own issue-letter wizard where it exists, and
        degrades to opening a new outgoing entry pre-linked to the letter being
        chased, because a reminder that is not tied to the letter it chases is
        just a second letter for the body to lose.
        """
        Corr = self._model("legal.correspondence")
        if Corr is None:
            return False
        wizard = self.env.ref(
            "legal_procedure.action_legal_issue_letter_wizard", raise_if_not_found=False,
        ) or self.env.ref(
            "legal_correspondence.action_legal_issue_letter_wizard", raise_if_not_found=False,
        )
        context = {"default_is_reminder": True}
        reply_to = self._field(Corr, "reply_to_id", "in_reply_to_id", "parent_id")
        if reply_to:
            context[f"default_{reply_to}"] = record.id
        body_field = self._body_field(Corr)
        if body and body_field:
            context[f"default_{body_field}"] = body.id
        if wizard:
            return self._wizard_action(wizard, context)
        direction = self._field(Corr, "direction")
        if direction:
            context[f"default_{direction}"] = "out"
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Reminder"),
            "res_model": "legal.correspondence",
            "views": [[False, "form"]],
            "target": "new",
            "context": context,
        }

    def _call_note_action(self, record, body):
        """One click from the chase list, or it does not get recorded.

        A telephone note consumes no register number - nothing was written in
        the book - but it carries who was spoken to and what they promised, and
        the reply clock recomputes from that promise. Without it the software
        keeps chasing a body that has already answered.
        """
        wizard = self.env.ref(
            "legal_correspondence.action_legal_contact_note_wizard",
            raise_if_not_found=False,
        )
        if not wizard:
            return False
        Corr = self._model("legal.correspondence")
        Note = self._model("legal.contact.note.wizard")
        context = {"default_correspondence_id": record.id}
        body_field = self._body_field(Note) if Note is not None else None
        if body and body_field:
            context[f"default_{body_field}"] = body.id
        case_field = self._field(Corr, "case_id")
        if case_field and record[case_field] and Note is not None \
                and "case_id" in Note._fields:
            context["default_case_id"] = record[case_field].id
        return self._wizard_action(wizard, context)

    def _wizard_action(self, action_record, context):
        """A wizard action, composed rather than read.

        ``ir.actions.act_window.context`` is a ``Char`` holding a Python
        literal, so ``read()`` hands back a *string* where a dict is wanted and
        merging into it raises - on the landing screen, in front of a clerk.
        Only the four fields that matter are taken from the record, and the
        context is ours.
        """
        record = action_record.sudo()
        return {
            "type": "ir.actions.act_window",
            "name": record.name,
            "res_model": record.res_model,
            "views": [[False, "form"]],
            "target": "new",
            "context": context,
        }

    # -- Column three: للإصدار ------------------------------------------
    def _mail_room_to_issue(self, degraded):
        """Files whose next move is a letter from us.

        Each row carries the document meter and the twin buttons: the enabled
        primary when the file is ready, and its greyed twin - same label, same
        place - carrying the blocker summary as its title when it is not. Two
        buttons computed from one field, so they can never disagree, and the
        next action never disappears just because it is out of reach.
        """
        title = self.env._("To be issued")
        hint = self.env._("The next move on these files is a letter from us")
        empty = self.env._("No letter is waiting to be written.")
        empty_hint = self.env._(
            "A file appears here when its procedure reaches a step we answer "
            "with an outgoing letter."
        )
        Case = self._model("legal.case")
        if Case is None:
            degraded.append(self.env._(
                "The procedure engine is not installed, so the issuing column is empty."
            ))
            return self._column("issue", title, hint, empty, empty_hint, [], 0, False)

        domain = self._to_issue_domain(Case)
        if domain is None:
            # The engine is installed but does not yet say which of its steps
            # are answered with a letter. An honest empty column beats a column
            # listing every open file under a heading that would then be a lie.
            degraded.append(self.env._(
                "The procedure steps do not yet declare which of them are "
                "answered by an outgoing letter, so the issuing column is empty."
            ))
            return self._column("issue", title, hint, empty, empty_hint, [], 0, False)
        order = self._sort_clause(Case, ("priority desc", "stage_entered_on asc", "id asc"))
        records = self._safe_search(Case, domain, order=order, limit=COLUMN_LIMIT)
        rows = [self._issue_row(record, Case) for record in records]
        return self._column(
            "issue", title, hint, empty, empty_hint, rows,
            self._safe_count(Case, domain),
            self._open_action("legal.case", title, domain),
        )

    def _to_issue_domain(self, Case):
        """"Next step is outbound", expressed against whatever the engine offers.

        Two rungs, best first: the step's own kind, or a letter template hung on
        the step. Each is checked against the registry rather than assumed.
        Returns ``None`` when neither exists - the caller then renders an empty
        column and says why, rather than listing every open file under a
        heading that would be false.
        """
        Step = self._model("legal.procedure.step")
        step_field = self._field(Case, "step_id")
        domain = []
        letter = self._field(Step, "requires_letter") if Step is not None else None
        if step_field and Step is not None and letter:
            domain.append((f"{step_field}.{letter}", "=", True))
            # A letter we have to write is ours to write, so the step must be
            # on our desk: one that is with the body is not waiting for us.
            if self._selection_has(Step, "kind", "internal"):
                domain.append((f"{step_field}.kind", "=", "internal"))
        elif step_field and Step is not None and "letter_template_id" in Step._fields:
            domain.append((f"{step_field}.letter_template_id", "!=", False))
        if not domain:
            return None
        closed = self._field(Case, "is_closed", "closed")
        if closed:
            domain.append((closed, "=", False))
        elif self._selection_has(Case, "state", "done"):
            domain.append(("state", "!=", "done"))
        return domain

    def _issue_row(self, record, Case):
        body = self._body_of(record)
        done, total = self._checklist_counts(record, Case)
        ready_field = self._field(Case, "ready_to_send", "ready_to_advance")
        blocker_field = self._field(Case, "blocker_summary")
        blockers = record[blocker_field] if blocker_field else ""
        # A file with a missing prerequisite is not ready even if the engine
        # has not said so yet; the meter and the button must agree, because a
        # primary button beside "3 / 4" is how a clerk learns to distrust both.
        ready = bool(record[ready_field]) if ready_field else (done >= total)
        if not ready and not blockers:
            blockers = (
                self.env._(
                    "%s required document(s) still outstanding.",
                    self._digits(total - done),
                )
                if total > done
                else self.env._("The file is not ready for the letter to be written.")
            )
        return {
            "id": record.id,
            "model": "legal.case",
            "name": self._value(record, "name", "reference") or "",
            "subject": self._value(record, "subject", "display_name") or "",
            "body_label": body.display_name if body else self.env._("Body not recorded"),
            "body_colour": (body.colour if body and "colour" in body._fields else 0) or 0,
            "step_label": self._step_label(record, Case),
            "next_action_label": (
                self._value(record, "next_action_label") or self.env._("Write the letter")
            ),
            "docs_done": done,
            "docs_total": total,
            "meter_label": self._meter_label(done, total),
            "meter_percent": int(round(100.0 * done / total)) if total else 100,
            "ready": ready,
            "action_label": self.env._("Write the letter"),
            "blocker_summary": blockers or "",
            "open": self._open_record("legal.case", record.id),
        }

    def _checklist_counts(self, record, Case):
        """How many required documents are in, out of how many.

        Read from the case's own checklist payload where the engine publishes
        one, because the counter on the desk and the counter on the form must
        be the same number computed once.
        """
        payload_field = self._field(Case, "checklist_payload")
        if payload_field:
            payload = record[payload_field] or {}
            if isinstance(payload, dict) and "total" in payload:
                return int(payload.get("done") or 0), int(payload.get("total") or 0)
        lines_field = self._field(Case, "requirement_ids", "document_ids", "checklist_ids")
        if lines_field:
            lines = record[lines_field]
            required = lines.filtered("is_required") if "is_required" in lines._fields else lines
            satisfied = (
                required.filtered("is_satisfied") if "is_satisfied" in required._fields
                else required.filtered("is_provided") if "is_provided" in required._fields
                else required.browse()
            )
            return len(satisfied), len(required)
        return 0, 0

    # ==================================================================
    # MY DESK
    # ==================================================================
    @api.model
    def get_desk_data(self, window_days=None):
        """What is on this reader today, whichever role they hold.

        One screen, not one per role. A clerk, an approver and the legal manager
        differ in *which slice* of one procedure they own, not in kind, and the
        manager holds every role at once - which separate screens could not
        represent at all. So the payload changes and the component does not.
        """
        degraded = []
        Case = self._model("legal.case")
        if Case is None:
            degraded.append(self.env._(
                "The procedure engine is not installed, so there is no caseload to show."
            ))

        role = self._role_brief()
        files, total, domain = self._desk_files(Case, role)
        hero, tiles = self._desk_head(Case, files, total, domain)
        return {
            "rtl": self._rtl(),
            "numerals": self._numerals(),
            "title": self.env._("My Desk"),
            "role": role,
            "hero": hero,
            "tiles": tiles,
            "worklist": {
                "title": (
                    self.env._("Awaiting your approval") if role["landing_band"] == "approvals"
                    else self.env._("Needs your action")
                ),
                "hint": self.env._(
                    "Two ages on every row: at this step, and since the file was opened."
                ),
                "empty": self.env._("Nothing is waiting for you."),
                "empty_hint": self.env._(
                    "A file appears here the moment it reaches a step you own."
                ),
                "total": total,
                "files": files,
                "action": self._open_action("legal.case", self.env._("My files"), domain),
            },
            "bodies": self.get_body_desk_data().get("bodies", []),
            "degraded": degraded,
        }

    def _desk_files(self, Case, role):
        """The reader's own queue, urgent first and then oldest first.

        Urgent first because the priority flag exists to say exactly that; and
        within one priority, the file that has waited longest is the one that
        should be opened next.

        ``role`` deliberately does not narrow this. An approver's band differs
        from a clerk's in what it is *called* and in the order it is read, not
        in which files it contains: the engine already routes a file to the
        desk that owes the next move through ``pending_group_id``, and a second
        definition of "mine" here would be a second answer to a question that
        already has one. The day a step declares that it needs a signature
        rather than a move, that flag belongs in the domain below and in the
        Python tests beside it - not in the browser.
        """
        if Case is None:
            return [], 0, []
        domain = self._my_turn_domain(Case)
        closed = self._field(Case, "is_closed", "closed")
        if closed:
            domain.append((closed, "=", False))

        order = self._sort_clause(Case, ("priority desc", "stage_entered_on asc", "id asc"))
        records = self._safe_search(Case, domain, order=order, limit=COLUMN_LIMIT)
        return (
            [self._desk_row(record, Case) for record in records],
            self._safe_count(Case, domain),
            domain,
        )

    def _my_turn_domain(self, Case):
        """"Waiting for me", decided here and never in the browser.

        Two things make a file mine, and the engine already records both: it is
        assigned to me, or it is standing at a step whose owning desk is a group
        I hold. The second is the one that matters in a legal department, where
        work is owned by a desk rather than by a person and a clerk covering for
        a colleague on leave must see the queue without anybody reassigning
        sixty records.

        Composed as a domain rather than filtered in Python because the count
        beneath the hero must be the size of the whole queue, not of the page.
        """
        leaves = []
        mine = self._field(Case, "is_my_turn", "my_turn")
        if mine:
            return [(mine, "=", True)]
        user_field = self._field(Case, "user_id", "responsible_id")
        if user_field:
            leaves.append([(user_field, "=", self.env.uid)])
        group_field = self._field(Case, "pending_group_id")
        if group_field:
            user = self.env.user
            groups = (
                user.all_group_ids if "all_group_ids" in user._fields else user.group_ids
            )
            leaves.append([(group_field, "in", groups.ids)])
        if not leaves:
            return []
        domain = ["|"] * (len(leaves) - 1)
        for leaf in leaves:
            domain += leaf
        return domain

    def _desk_row(self, record, Case):
        """One file, with the two ages that answer two different questions.

        Time at this step says whose desk is blocked. Time since the file was
        opened is what the company actually experiences, and unlike the first it
        does not reset when the file moves from the Tax Commission to the
        Chamber. A file bounced four times looks fresh by the first measure and
        is four months old by the second, and a desk that shows only one of them
        is lying to somebody.
        """
        body = self._body_of(record)
        step_entered = self._value(
            record, "stage_entered_on", "step_entered_on", "write_date"
        )
        opened = self._value(record, "date_open", "opened_on", "create_date")
        at_step = self._working_days_since(body, step_entered)
        since_open = self._working_days_since(body, opened)
        with_body = self._is_with_body(record, Case)
        return {
            "id": record.id,
            "model": "legal.case",
            "name": self._value(record, "name", "reference") or "",
            "subject": self._value(record, "subject", "display_name") or "",
            "body_label": body.display_name if body else self.env._("Body not recorded"),
            "body_colour": (body.colour if body and "colour" in body._fields else 0) or 0,
            "step_label": self._step_label(record, Case),
            "urgent": self._value(record, "priority") in ("1", 1, True),
            "at_step_days": at_step,
            "at_step_label": self._working_days_label(at_step),
            "since_open_days": since_open,
            "since_open_label": self._working_days_label(since_open),
            "age_band": self._age_band(at_step),
            "age_percent": self._age_percent(at_step),
            "clock": self._clock(
                "at_body" if with_body else "at_us", at_step,
                body_label=body.display_name if body else "",
            ),
            "blocker_summary": self._value(record, "blocker_summary") or "",
            "open": self._open_record("legal.case", record.id),
        }

    def _is_with_body(self, record, Case):
        step_field = self._field(Case, "step_id")
        Step = self._model("legal.procedure.step")
        # The engine stores this on the case precisely so that nobody has to
        # join a configuration table to answer the question, so read it there
        # first and only fall back to the step.
        kind = self._field(Case, "kind")
        if kind and record[kind]:
            return record[kind] == "at_body"
        if step_field and Step is not None and "kind" in Step._fields:
            return record[step_field].kind == "at_body"
        return False

    def _desk_head(self, Case, files, total, domain):
        """The hero and the three tiles a legal department is actually judged on."""
        urgent = sum(1 for row in files if row["urgent"])
        oldest = max((row["at_step_days"] for row in files), default=0)
        stalled_ids = [row["id"] for row in files if row["age_band"] == "stuck"]
        with_body = [row for row in files if row["clock"]["kind"] == "at_body"]
        expiring, expiring_domain = self._expiring(Case)

        hero = {
            "label": self.env._("Waiting for you"),
            "count": total,
            "count_label": self._digits(total),
            "note": (
                self.env._("%s urgent", self._digits(urgent)) if urgent
                else self.env._("Nothing is marked urgent.")
            ),
            "oldest_label": (
                self.env._("Longest wait: %s", self._working_days_label(oldest))
                if oldest else ""
            ),
            "action": self._open_action("legal.case", self.env._("My files"), domain),
        }
        tiles = [
            {
                "key": "stalled",
                "label": self.env._("Stalled over a fortnight"),
                "value": len(stalled_ids),
                "value_label": self._digits(len(stalled_ids)),
                "hint": self.env._("On your desk and not moving"),
                "icon": "fa-hourglass-half",
                "tone": "critical" if stalled_ids else "neutral",
                "action": self._open_action(
                    "legal.case", self.env._("Stalled files"), [("id", "in", stalled_ids)],
                ) if stalled_ids else False,
            },
            {
                "key": "with_body",
                "label": self.env._("With the body"),
                "value": len(with_body),
                "value_label": self._digits(len(with_body)),
                "hint": self.env._("Our clock is paused; theirs is running"),
                "icon": "fa-institution",
                "tone": "attention" if any(
                    row["clock"]["state"] == "overdue" for row in with_body
                ) else "neutral",
                "action": self._open_action(
                    "legal.case", self.env._("With the body"),
                    [("id", "in", [row["id"] for row in with_body])],
                ) if with_body else False,
            },
            {
                "key": "expiring",
                "label": self.env._("Expiring within 90 days"),
                "value": expiring,
                "value_label": self._digits(expiring),
                "hint": self.env._("Company documents to renew"),
                "icon": "fa-calendar-times-o",
                "tone": "attention" if expiring else "neutral",
                "action": self._open_action(
                    "legal.document", self.env._("Expiring documents"), expiring_domain,
                ) if expiring else False,
            },
        ]
        return hero, tiles

    def _expiring(self, Case):
        """Documents whose renewal window has opened.

        Bucketed on ``start_by_date`` rather than on raw expiry, because a
        renewal that takes forty-five working days at a body that closes Friday
        and Saturday has to surface when there is still time to start it, not
        thirty days before it lapses. ``legal.expiry.mixin`` already computes
        that date; this only counts it.
        """
        Document = self._model("legal.document")
        if Document is None:
            return 0, []
        horizon = fields.Date.add(fields.Date.context_today(self), days=90)
        domain = []
        if "expiry_state" in Document._fields:
            domain.append(("expiry_state", "in", ("due_soon", "expiring", "expired")))
        elif "expiry_date" in Document._fields:
            domain.append(("expiry_date", "<=", horizon))
        else:
            return 0, []
        if "active" in Document._fields:
            domain.append(("active", "=", True))
        return self._safe_count(Document, domain), domain

    # ==================================================================
    # THE GOVERNMENT BODY DESKS
    # ==================================================================
    @api.model
    def get_body_desk_data(self, body_ids=None):
        """One panel per body the reader deals with.

        There is no per-body screen and there never will be one: a "Tax
        Commission dashboard" and a "Chamber of Commerce dashboard" are the same
        screen with a different ``body_id``, and shipping them separately is how
        a configurable module quietly becomes twelve forked ones. So a body is a
        *panel*, its sections come from configuration, and adding the General
        Commission for Taxes costs zero Python and zero JavaScript.
        """
        Body = self._model("legal.gov.body")
        if Body is None:
            return {"rtl": self._rtl(), "bodies": []}

        domain = []
        if body_ids:
            domain.append(("id", "in", list(body_ids)))
        elif "officer_ids" in Body._fields:
            # The bodies this reader actually deals with. Falls back to all of
            # them for a manager who is on nobody's officer list, because an
            # empty workspace would read as a broken one.
            mine = self._safe_search(Body, [("officer_ids", "in", self.env.uid)])
            if mine:
                domain.append(("id", "in", mine.ids))
        bodies = self._safe_search(Body, domain, order=self._sort_clause(Body, ("sequence", "name")))
        return {
            "rtl": self._rtl(),
            "title": self.env._("The bodies' desks"),
            "bodies": [self._body_panel(body) for body in bodies[:8]],
        }

    def _body_panel(self, body):
        sections = [
            section for section in (
                self._body_section_to_send(body),
                self._body_section_with_them(body),
                self._body_section_awaiting(body),
            ) if section
        ]
        return {
            "id": body.id,
            "key": (body.code if "code" in body._fields else str(body.id)) or str(body.id),
            "label": body.display_name,
            "mission": self._value(body, "letterhead_recipient", "address") or "",
            "open_hours": self._value(body, "open_hours") or "",
            "open_hours_label": self.env._("Opening hours"),
            "counter_notes": self._value(body, "note") or "",
            "counter_notes_label": self.env._("Which counter, which floor"),
            "colour": (body.colour if "colour" in body._fields else 0) or 0,
            "outstanding": sum(section["count"] for section in sections),
            "outstanding_label": self.env._("outstanding"),
            "sections": sections,
            "open": self._open_record("legal.gov.body", body.id),
        }

    def _body_section_to_send(self, body):
        Case = self._model("legal.case")
        if Case is None or not self._field(Case, "body_id"):
            return None
        outbound = self._to_issue_domain(Case)
        if outbound is None:
            return None
        domain = [("body_id", "=", body.id)] + outbound
        return self._body_section(
            "to_send", "case", body,
            self.env._("Waiting to be sent"),
            self.env._("The next move on these is a letter from us to this body."),
            self.env._("Nothing is waiting to go to this body."),
            Case, domain, "legal.case",
        )

    def _body_section_with_them(self, body):
        Case = self._model("legal.case")
        step_field = self._field(Case, "step_id") if Case is not None else None
        Step = self._model("legal.procedure.step")
        if Case is None or not self._field(Case, "body_id"):
            return None
        domain = [("body_id", "=", body.id)]
        if self._selection_has(Case, "kind", "at_body"):
            domain.append(("kind", "=", "at_body"))
        elif step_field and Step is not None and self._selection_has(Step, "kind", "at_body"):
            domain.append((f"{step_field}.kind", "=", "at_body"))
        else:
            return None
        return self._body_section(
            "with_them", "case", body,
            self.env._("With this body"),
            self.env._("Our clock is paused on these; theirs is running."),
            self.env._("This body is holding nothing of ours."),
            Case, domain, "legal.case",
        )

    def _body_section_awaiting(self, body):
        Corr = self._model("legal.correspondence")
        body_field = self._body_field(Corr)
        if Corr is None or not body_field:
            return None
        domain = [(body_field, "=", body.id)]
        note_field = self._field(Corr, "is_contact_note")
        if note_field:
            domain.append((note_field, "=", False))
        direction = self._field(Corr, "direction")
        if direction and self._selection_has(Corr, direction, "out"):
            domain.append((direction, "=", "out"))
        expects = self._field(Corr, "reply_expected", "expects_reply")
        if expects:
            domain.append((expects, "=", True))
        reply_state = self._field(Corr, "reply_state")
        if reply_state and self._selection_has(Corr, reply_state, "answered"):
            domain.append((reply_state, "!=", "answered"))
        return self._body_section(
            "awaiting", "correspondence", body,
            self.env._("Awaiting their reply"),
            self.env._("Letters we have sent to this body and are still chasing."),
            self.env._("We are not chasing this body for anything."),
            Corr, domain, "legal.correspondence",
        )

    def _body_section(self, key, kind, body, title, hint, empty, model, domain, model_name):
        """One panel of a body's desk.

        ``count`` is the size of the whole queue, never of the page: the rows
        are capped and the footer offers the rest, so a count taken from the
        rows would tell an officer the backlog is eight when it is eighty.
        """
        records = self._safe_search(model, domain, order=self._sort_clause(model, ("id desc",)), limit=5)
        rows = []
        for record in records:
            if model_name == "legal.case":
                rows.append(self._desk_row(record, model))
            else:
                rows.append(self._awaiting_row(record, model))
        return {
            "key": key,
            "kind": kind,
            "title": title,
            "hint": hint,
            "empty": empty,
            "count": self._safe_count(model, domain),
            "rows": rows,
            "action": self._open_action(model_name, f"{body.display_name} — {title}", domain),
        }

    # ==================================================================
    # Small shared pieces
    # ==================================================================
    def _column(self, key, title, hint, empty, empty_hint, rows, count, action):
        """A Mail Room column, empty state included.

        The empty state is part of the payload rather than a string in a
        template, because "nothing is waiting to be filed" is an *answer* to the
        clerk's question and an absent column is not.
        """
        return {
            "key": key,
            "title": title,
            "hint": hint,
            "empty": empty,
            "empty_hint": empty_hint,
            "count": count,
            "count_label": self._digits(count),
            "rows": rows,
            "overflow": max(0, count - len(rows)),
            "overflow_label": self.env._("%s more", self._digits(max(0, count - len(rows)))),
            "open_all_label": self.env._("Open all"),
            "action": action,
        }

    def _sort_clause(self, model, candidates):
        """The first order clause every field of which the model actually has."""
        if model is None:
            return None
        usable = [
            clause for clause in candidates
            if clause.split()[0] in model._fields
        ]
        return ", ".join(usable) or None

    def _value(self, record, *candidates):
        """The first of those fields the record carries, or ``False``."""
        for name in candidates:
            if name in record._fields:
                return record[name]
        return False

    def _body_field(self, model):
        """Whichever name that model gives to the government body.

        ``legal.correspondence`` calls it ``gov_body_id`` and ``legal.case``
        calls it ``body_id``. One helper rather than the name written out a
        dozen times, because the day one of them is renamed should cost one
        edit here and not a hunt through the file.
        """
        return self._field(model, "body_id", "gov_body_id")

    def _body_of(self, record):
        """The government body a row belongs to, however it is reached."""
        for name in ("body_id", "gov_body_id"):
            if name in record._fields and record[name]:
                return record[name]
        for name in ("case_id",):
            if name in record._fields and record[name]:
                return self._body_of(record[name])
        return None

    def _step_label(self, record, model):
        step = self._field(model, "step_id")
        if step and record[step]:
            return record[step].display_name
        state = self._field(model, "state")
        if state:
            try:
                return dict(
                    model._fields[state]._description_selection(self.env)
                ).get(record[state], "")
            except Exception:  # noqa: BLE001
                return ""
        return ""

    def _attachment_of(self, record):
        """The scan, for the file viewer - the first one attached, or nothing."""
        for name in ("message_main_attachment_id", "attachment_id"):
            if name in record._fields and record[name]:
                return record[name].id
        if "attachment_ids" in record._fields and record.attachment_ids:
            return record.attachment_ids[0].id
        return False

    def _role_brief(self):
        """Which slice of the procedure this reader owns.

        Decided here, from group membership, so the browser never has to match
        the module's role vocabulary against the user's groups and reach a
        different answer. ``landing_band`` is the whole of the difference
        between an approver's desk and a clerk's: the same action, a different
        payload.
        """
        user = self.env.user
        is_manager = user.has_group("legal_core.group_legal_manager")
        is_approver = is_manager or user.has_group("legal_core.group_legal_approver")
        is_officer = is_approver or user.has_group("legal_core.group_legal_officer")
        return {
            "is_manager": is_manager,
            "is_approver": is_approver,
            "is_officer": is_officer,
            "landing_band": "approvals" if (is_approver and not is_manager) else "files",
            "label": (
                self.env._("Legal Manager") if is_manager
                else self.env._("Approver") if is_approver
                else self.env._("Follow-up Officer") if is_officer
                else self.env._("Clerk")
            ),
        }

    # ==================================================================
    # The one write the Mail Room performs
    # ==================================================================
    @api.model
    def link_correspondence(self, correspondence_id, case_id):
        """Attach a registered incoming entry to an existing file.

        The clerk picks the file in the core record selector; the write happens
        here, as the reader, so the record rules and whatever guard the
        correspondence model puts on ``write`` both apply exactly as they would
        from the form. The browser decides which record - never whether the
        write is allowed.
        """
        Corr = self._model("legal.correspondence")
        if Corr is None:
            return {"ok": False, "message": self.env._("The correspondence register is not installed.")}
        field = self._field(Corr, "case_id")
        if not field:
            return {"ok": False, "message": self.env._("Entries cannot be attached to a file.")}
        record = Corr.browse(int(correspondence_id))
        record.write({field: int(case_id)})
        return {
            "ok": True,
            "message": self.env._(
                "%(entry)s is now on file %(case)s.",
                entry=record.display_name,
                case=record[field].display_name,
            ),
        }
