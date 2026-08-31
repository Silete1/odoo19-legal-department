{
    "name": "Legal Department - Correspondence Register",
    "summary": "The outgoing/incoming register, the official letter and the reply clock",
    "description": """
Legal Department - Correspondence (سجل الصادر والوارد)
=======================================================

The register book, made electronic without being made unfaithful.

Every Iraqi department runs on two bound books - صادر and وارد - and every
number in them is quoted back over the telephone, written on the envelope and
copied into the ministry's own book. Three consequences shape this module.

**The number belongs to the paper, not to the software.** ``our_number`` is
clerk-editable, so a department migrating mid-year types 1,247 and carries on;
the sequence chain then continues from what the book says rather than from what
the database would have preferred. It resets on the calendar year the way the
book does, and it is gap-checked, because a register with a hole in it is a
register somebody has been editing.

**Nothing is ever deleted.** A registered entry cannot be unlinked and cannot
have its number, its date or its register changed. A mistake is *voided* with a
reason - the number stays, struck through, exactly as a clerk draws a line
across a page and writes ملغى. A paper register has no deleted rows, and the
moment ours does, it stops being evidence.

**The register exists before the file does.** ``legal.correspondence`` has a
nullable case, because an unprompted tax assessment or a summons arrives before
anybody has opened a file for it. The mail room is therefore the landing screen:
what came in this morning, what has not been answered, and who promised what.

**The telephone is a first-class entry.** ``تدوين اتصال هاتفي`` consumes no
register number - it never touched the book - but it records who was spoken to,
what they said and what they promised. Without it, "راجعنا بعد العيد" leaves the
software chasing a body that already answered, and the escalation everybody
learns to ignore is the escalation that fires on a settled matter.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_core"],
    "data": [
        "security/legal_correspondence_security.xml",
        "security/ir.model.access.csv",
        "security/legal_correspondence_rules.xml",
        "data/legal_correspondence_kind_data.xml",
        "data/legal_register_data.xml",
        "report/legal_correspondence_paperformat.xml",
        "report/report_official_letter.xml",
        "report/legal_correspondence_reports.xml",
        "views/legal_register_views.xml",
        "views/legal_correspondence_kind_views.xml",
        "views/legal_letter_template_views.xml",
        "views/legal_correspondence_views.xml",
        "wizard/legal_correspondence_wizard_views.xml",
        "views/legal_correspondence_menus.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "legal_correspondence/static/src/scss/legal_letter.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
