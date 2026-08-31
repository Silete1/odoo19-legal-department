{
    "name": "Legal Department - Deadlines",
    "summary": "المواعيد القانونية - one board for every clock the department runs",
    "description": """
Legal Department - Deadlines (المواعيد القانونية)
==================================================

The control tower of the suite. Every module keeps its own clock - the
obligation period, the case SLA, the awaited reply, the expiring document and
power of attorney, the hearing, the appeal window, the contract and its
obligation occurrences, the request's undertaken response date, the opinion's
due date - and each of those clocks is right, in its own register, on its own
screen. What no register can answer alone is the only question the head of
department actually asks in the morning: *what is due, across everything,
today?*

One decision carries the module. **The board is a SQL view, never a copy.**
A synchronised table of deadlines is a second place the truth has to be
maintained, and the first time a filed obligation lingers on the board the
department stops believing it. Here every row *is* the source row projected
through a UNION: discharge the period, register the reply, hold the hearing -
and the row is gone in the same transaction, because there was never a second
row to clean up. The view is read-only by construction and by access rights;
the one verb it offers is *open the source record*, because the work is done
where the clock lives, not on the board that reads it.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": [
        "legal_procedure",
        "legal_litigation",
        "legal_contract",
        "legal_opinion",
        "legal_request",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/legal_deadline_rules.xml",
        "views/legal_deadline_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
