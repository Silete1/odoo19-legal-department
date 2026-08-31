{
    "name": "Legal Department - Iraq: Chamber of Commerce",
    "summary": "غرفة التجارة - the annually renewed هوية with its أصناف, and the Federation's national name check",
    "description": """
Iraq content pack - Chamber of Commerce (غرفة التجارة)
=======================================================

Data only: no ``models`` directory, no field, no Python beyond an empty
``__init__.py``.

Why this pack is small and yet the one a tender fails on
--------------------------------------------------------

Baghdad Governorate publishes its tender notices with an explicit qualification
checklist, and two of its lines are this pack: *هوية غرفة تجارة نافذة* and, for
larger works, *هوية غرفة تجارة صنف (ممتاز) نافذة*. The identity is renewed
annually, and it is graded - so a bid is not refused for the want of a
certificate, it is refused for the want of a certificate *of the right class,
valid at the closing date*.

That is why the grades are ``legal.licence.grade`` records rather than a text
field. A readiness check can evaluate "at least صنف أول" against a record with a
seniority ordering; it can do nothing at all with a string somebody typed.

The pack also ships the Federation of Iraqi Chambers of Commerce as its own
body, because the national trade-name uniqueness check is a genuinely separate
physical procedure: the local chambers' name databases are not electronically
linked, so a name cleared in Baghdad is cleared in Baghdad only until the
Federation says otherwise.

Fees here are the least reliable data in the whole suite and they are shipped
saying so. The Ministry of Trade brief, the Chamber's own Arabic procedure page
and the eRegulations survey give three different figures for the same counter,
and no class-by-class renewal schedule could be verified from an authoritative
page at all.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_procedure"],
    "data": [
        "data/chamber_calendar.xml",
        "data/chamber_bodies.xml",
        "data/chamber_document_types.xml",
        "data/chamber_procedures.xml",
        "data/chamber_obligations.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
