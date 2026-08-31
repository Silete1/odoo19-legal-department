from odoo import api, fields, models


class LegalCorrespondenceKind(models.Model):
    """What kind of entry this is - نوع القيد.

    A record with semantic flags, never a hard-coded list, because the list is
    wrong the moment it leaves Baghdad. The flags exist so that the engine can
    reason about an entry it has never seen: a customer who invents
    ``إنذار قانوني`` ticks *expects a reply* and *closes nothing*, and every
    clock, counter and board in the product understands it immediately.

    Four of the flags are the ones that make statistics honest, and each of them
    exists because the naive model gets a real number wrong:

    * ``is_acknowledgement`` - a وصل proves the letter was *received*. It closes
      nothing. A system that treats a receipt as an answer reports a two-day
      turnaround at a body that has not yet read the file.
    * ``is_return`` - **they** sent it back for completion. This is the rework
      signal. Without it, a file that went round the Registrar four times looks
      like one submission that took ninety days, and nobody can see that the
      ninety days were four rejections over a missing stamp.
    * ``is_repeatable`` - a تذكير recurs. Three reminders are not three
      submissions and must not inflate any expectation count.
    * ``is_contact_note`` - the telephone. An entry that consumes **no register
      number at all**, because it never touched the book. It carries who was
      spoken to and what they promised, and it is the difference between chasing
      a body that has already answered and knowing to call back after Eid.
    """

    _name = "legal.correspondence.kind"
    _description = "Correspondence Kind"
    _order = "sequence, code"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True, translate=True, index="trigram")
    code = fields.Char(required=True, help="Stable key used by content packs and wizards.")
    direction = fields.Selection(
        [
            ("out", "صادر - Outgoing"),
            ("in", "وارد - Incoming"),
            ("internal", "داخلي - Internal"),
        ],
        required=True,
        default="out",
    )

    # ------------------------------------------------------------------
    # Semantics
    # ------------------------------------------------------------------
    is_submission = fields.Boolean(
        string="Is A Submission",
        help="A filing at the counter that starts or advances something. This is "
        "what a cycle-time statistic counts from.",
    )
    is_acknowledgement = fields.Boolean(
        string="Is A Receipt (وصل)",
        help="Proves the letter was received. Closes nothing, answers nothing, "
        "and must never be counted as a reply.",
    )
    is_return = fields.Boolean(
        string="Sent Back For Completion",
        help="They returned it for correction. Increments the round counter, "
        "which is the only way rework shows up in the statistics instead of "
        "hiding inside a long first cycle.",
    )
    is_reminder = fields.Boolean(
        string="Is A Reminder (تذكير)",
        help="A chase. Does not restart the clock and does not count as a new "
        "submission.",
    )
    is_repeatable = fields.Boolean(
        string="May Recur",
        help="May be entered many times against the same thread without "
        "corrupting any expectation count.",
    )
    is_issued_document = fields.Boolean(
        string="Produces A Document",
        help="Registering an entry of this kind files a record in the company's "
        "permanent document register, so a licence that arrives as an incoming "
        "letter does not have to be typed twice.",
    )
    document_type_id = fields.Many2one(
        "legal.document.type",
        string="Document Type",
        ondelete="restrict",
        help="Used when this kind produces a document. Left empty, the clerk is "
        "asked which type it is.",
    )
    closes_thread = fields.Boolean(
        string="Closes The Thread",
        help="The matter is settled by this entry. A receipt does not do this; "
        "an approval or a final refusal does.",
    )
    expects_reply = fields.Boolean(
        string="Expects A Reply",
        help="Starts the reply clock. What follows is chased until an answer is "
        "registered against it.",
    )
    default_reply_days = fields.Integer(
        string="Reply Expected Within (working days)",
        default=7,
        help="Counted in the body's own working days through its calendar, so a "
        "target does not cry wolf every Friday and every Eid.",
    )
    is_contact_note = fields.Boolean(
        string="Consumes No Register Number",
        help="A telephone call or a personal مراجعة. It never touched the book, so "
        "it takes no number - but it is evidence, it moves the reply clock, and "
        "it suppresses the next chase when the counter has promised a date.",
    )

    colour = fields.Integer(string="Colour")
    sequence = fields.Integer(default=10)
    note = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)", "A correspondence kind code must be unique."
    )

    @api.onchange("is_contact_note")
    def _onchange_is_contact_note(self):
        """A contact note is internal by construction: nothing left or entered
        the building, somebody picked up a telephone."""
        for kind in self:
            if kind.is_contact_note:
                kind.direction = "internal"
