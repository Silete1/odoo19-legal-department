"""The vocabularies the engine refuses to let a configurer extend.

Almost everything in this module is data: the bodies, the steps, the documents,
the fees and the deadlines are all rows a consultant edits. The handful of lists
here are the deliberate exceptions, and each one is an exception for a reason
worth writing down.

A Selection may never name a government body, a document, a fee or a step - that
rule is what makes the product configurable rather than forked. But the *shapes*
below are not names of things in the world; they are the small closed alphabet
the engine reasons in. A checklist badge drawn from six fixed words can be
counted, coloured, sorted and translated once. The moment a configurer can add a
seventh word, every meter, rail and gate in the product has to guess what it
means, and they will guess differently.
"""

#: How a body is dealt with. Mirrors ``legal.gov.body.channel`` so a procedure
#: can override its body - a ministry may be online for renewals and paper for
#: everything else.
CHANNEL_SELECTION = [
    ("paper", "Paper"),
    ("online", "Online"),
    ("hybrid", "Both"),
]

#: Where a step sits relative to the counter. This is the "is it on our desk or
#: theirs" axis, and it is stored and indexed on the case because it is the
#: single most asked question in a legal department and no board should have to
#: join to a configuration table to answer it.
STEP_KIND_SELECTION = [
    ("internal", "On Our Desk"),
    ("at_body", "With The Body"),
    ("terminal", "Closed"),
]

#: What a terminal step *means*. Iraqi bodies return and conditionally grant far
#: more often than they refuse outright, and a system with only granted/rejected
#: forces the clerk to record a return as a rejection - which then poisons every
#: statistic the department is judged on.
OUTCOME_SELECTION = [
    ("none", "Not Concluded"),
    ("granted", "Granted"),
    ("granted_conditional", "Granted With Conditions"),
    ("returned_for_correction", "Returned For Correction"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
    ("expired", "Lapsed"),
]

#: The six-word checklist vocabulary, in Arabic, closed for ever.
#:
#: Every surface that speaks about a required document - the blocking gate, the
#: readiness meter, the phase rail and the desk row - reads exactly this list.
#: They cannot disagree about what "ready" means because there is only one
#: sentence they are all allowed to say.
DOCUMENT_LINE_STATUS_SELECTION = [
    ("not_required", "غير مطلوب"),
    ("missing", "لم يُقدَّم"),
    ("provided", "مُقدَّم"),
    ("under_review", "قيد التدقيق"),
    ("accepted", "مقبول"),
    ("rejected", "مرفوض"),
    ("expired", "منتهي الصلاحية"),
]

#: Line states that satisfy a requirement. ``provided`` deliberately does not:
#: handing a photocopy over the counter is not the same as the counter keeping
#: it, and a gate that treats the two alike lets a file leave incomplete.
SATISFYING_LINE_STATUS = ("not_required", "accepted")

#: Where the clock stands on a step. Not stored: a stored verdict is stale by
#: the next midnight, and a service-level badge that lies for a day is worse
#: than none. The *deadline* is stored; the verdict is read live.
SLA_STATE_SELECTION = [
    ("not_applicable", "No Target"),
    ("on_track", "On Track"),
    ("warning", "Due Soon"),
    ("overdue", "Overdue"),
    ("escalated", "Escalated"),
    ("paused", "Paused"),
]

#: Fields the engine owns. ``readonly=True`` is a client hint and stops nothing
#: coming in over RPC, so :meth:`legal.case.write` refuses these outright unless
#: the engine itself is the caller. Without this the statusbar becomes a way to
#: teleport a file past its own approvals.
WORKFLOW_OWNED_FIELDS = (
    "step_id",
    "phase_id",
    "outcome",
    "round",
    "stage_entered_on",
    "sla_due_on",
    "date_closed",
    "procedure_version",
)

#: Codes a per-step capture field may not use.
#:
#: Each of these is a fact that recurs across every body in the department, and
#: the department is asked about it in aggregate: "what did we pay the Registrar
#: this year", "which files are waiting on a number we quoted". A recurring fact
#: buried in a per-step JSON payload is invisible to ``_read_group`` for ever,
#: so the engine refuses the name and points the configurer at the real column.
RESERVED_FIELD_CODES = {
    "fee": "legal.fee",
    "amount": "legal.fee",
    "receipt": "legal.fee",
    "expiry": "legal.expiry.mixin",
    "issue_date": "legal.document",
    "our_number": "legal.correspondence",
    "their_number": "legal.correspondence",
    "reference": "legal.correspondence",
}


def reserved_code_message(env, code):
    """Explain *where* the fact belongs, not merely that the name is taken.

    Takes the environment rather than importing ``_`` at module level: this file
    holds no model, so a bare ``_()`` here has no frame to read the reader's
    language from and would be served in whatever language happened to be
    loaded. ``env._`` always knows.
    """
    return env._(
        "“%(code)s” is a fact the whole department reports on, so it has a real "
        "column of its own on %(model)s. A capture field of that name would hide "
        "it inside one step where no report can reach it. Use the field the "
        "engine already provides.",
        code=code,
        model=RESERVED_FIELD_CODES[code],
    )
