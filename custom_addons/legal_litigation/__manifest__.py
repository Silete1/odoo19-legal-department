{
    "name": "Legal Department - Litigation",
    "summary": "Courts, lawsuits, hearings, judgments and the non-extendable appeal window",
    "description": """
Legal Department - Litigation (الدعاوى والقضايا)
================================================

The court side of the department, built on the same spine as the procedure
engine. A lawsuit (الدعوى) walks a clear lifecycle - assessment, preparation,
filing, hearing, judgment, appeal, enforcement, closure - and three facts about
Iraqi litigation shape the whole module.

**A file cannot be lodged on a power of attorney that will not stand.** The
court will refuse an advocate whose name is not on a وكالة بالمرافعة, so filing
reuses ``legal.poa`` and blocks outright rather than warning: the failure
belongs at the desk, not at the counter of the court.

**A hearing breeds the next hearing.** An Iraqi case is a chain of جلسات, each
one setting the date of the one after it, so recording ``next_hearing_date`` on
a sitting rolls the next row forward and puts the date on the advocate's
activity list - once, idempotently, never twice.

**The appeal window is a non-extendable clock that starts at التبليغ.** The
period is law, not preference - objection, appeal, cassation and the labour
courts each count differently, and cassation counts differently again for a
decision than for a judgment - so the day-counts live in a configurable
``legal.appeal.rule`` table, marked with a verification status, and the deadline
they produce is flagged non-extendable and surfaced as a chase before it lapses.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_procedure"],
    "data": [
        "security/ir.model.access.csv",
        "security/legal_litigation_rules.xml",
        "data/legal_litigation_data.xml",
        "data/legal_appeal_rule_data.xml",
        "data/legal_court_data.xml",
        "views/legal_appeal_rule_views.xml",
        "views/legal_court_views.xml",
        "views/legal_hearing_views.xml",
        "views/legal_judgment_views.xml",
        "views/legal_lawsuit_views.xml",
        "wizard/legal_lawsuit_reason_views.xml",
        "views/legal_litigation_menus.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}
