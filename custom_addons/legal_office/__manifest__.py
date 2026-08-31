{
    "name": "Legal Department - My Desk & Analytics",
    "summary": "The redesigned مكتبي workspace, and the management reporting screen beside it",
    "description": """
Legal Department - My Desk (مكتبي)
===================================

Two screens, and the whole module exists to keep them apart.

**مكتبي - My Desk** is not a new screen. This module re-points the existing
``legal_procedure.action_legal_desk`` at a new component, so the menu entry,
the name and the ``/odoo/legal-desk`` URL people already use are unchanged and
only what they render is different.

It answers *what requires my action now*. It is a
workspace, not a dashboard: an attention rail of three to five filtered
queues, one unified work list that crosses eight registers, a three-week
agenda drawn from the ``legal.deadline`` union board, and a tabbed strip of
context underneath. There is not one chart on it, because a chart cannot be
worked through and closed.

**التقارير والتحليلات - Analytics** answers *what is happening across Legal
Affairs*. It is the management screen: turnaround, ageing, workload,
lifecycle and volume, every figure drilling through to the records behind it.

Those are different questions asked by different people at different times of
the week, and a single screen that tries to answer both ends up answering
neither - which is the failure mode this module was written to repair.

What مكتبي used to also carry - one panel per government body, with its
opening hours and counter notes - was reference material sitting on top of the
day's work. It keeps its content and its component, moves to its own
**مكاتب الجهات / Government Desks** screen, and stops competing for the
landing position.

The design system
-----------------

``static/src/scss/legal_ds.scss`` is the suite's single source of spacing,
type, surface, border, row-height, tone and focus decisions;
``legal_native.scss`` applies the same vocabulary to the ordinary Odoo list,
kanban and form views so that My Office does not read as a separate product
bolted onto the side of the application.

Everything is composed server-side through the ORM as the reading user, so
the record rules and the read-only auditor ACLs apply untouched, and no
payload contains an affordance the server would refuse.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    # legal_deadline already depends on procedure, litigation, contract,
    # opinion and request, so one line here pulls the whole suite in and the
    # queue can query every register without soft-dependency gymnastics.
    "depends": ["legal_deadline", "legal_reports"],
    "data": [
        "views/legal_office_views.xml",
        "views/legal_office_menus.xml",
    ],
    "assets": {
        # Listed rather than globbed, because SCSS in an Odoo bundle is
        # concatenated in this order before it is compiled: the design system
        # has to be parsed before anything that uses its variables, and a glob
        # would make that depend on the alphabet.
        "web.assets_backend": [
            "legal_office/static/src/scss/legal_ds.scss",
            "legal_office/static/src/scss/legal_native.scss",
            "legal_office/static/src/office/legal_office.scss",
            "legal_office/static/src/analytics/legal_analytics.scss",
            "legal_office/static/src/office/*.js",
            "legal_office/static/src/office/*.xml",
            "legal_office/static/src/analytics/*.js",
            "legal_office/static/src/analytics/*.xml",
        ],
        "web.assets_unit_tests": [
            "legal_office/static/tests/**/*.test.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
