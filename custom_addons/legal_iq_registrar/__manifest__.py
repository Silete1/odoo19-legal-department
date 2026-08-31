{
    "name": "Legal Department - Iraq: Companies Registrar",
    "summary": "دائرة تسجيل الشركات - bodies, document types, procedures and statutory clocks",
    "description": """
Iraq content pack - Companies Registrar (دائرة تسجيل الشركات)
=============================================================

Everything this pack ships is **data**. There is no ``models`` directory, no
field, no Python beyond an empty ``__init__.py``, and the purity test in
``tests/test_pack_purity.py`` fails the build if that ever stops being true.
That is the falsifiable form of the claim the product makes: an Iraqi
government body is *configured*, not coded, so a changed circular is a pack
bump rather than a release.

What is inside
--------------

* The Ministry of Trade, its Registrar, the three sections a clerk actually
  walks to, and the seven counters outside the Ministry that a formation file
  passes through anyway - the notary, the Bar Association, Al-Rasheed Bank, the
  Translators Association, the Foreign Ministry's certifications directorate,
  the official gazette and the daily papers. A body model that only admitted
  ministries could not hold any of them.
* The Registrar's working calendar - Sunday to Thursday, 08:30 to 14:15 - with
  the national closures, so that "they have had it for six working days" means
  six days the counter was actually open.
* The document types the Registrar issues and demands, each with the right
  validity model. A certificate of incorporation does not expire; a paid
  electricity bill does not expire either but goes *stale*, which is why
  directive 16180 of 2024 is modelled as ``freshness`` and not as an expiry date.
* The procedures: formation, capital increase, amendment of the formation
  contract, the seven-day address change of Article 200, branch opening, and the
  foreign branch's eight-month accounts filing under Article 8 of Regulation
  2/2017.
* The recurring obligations, each carrying its article, its source URL and the
  date a human last read it.

Figures that conflict in the sources are shipped with the better-sourced value,
``verification_status = 'stale'`` and the conflict written into the record's
note. A clerk who trusts a wrong seeded fee is wrong at the counter, and the
module - not the clerk - takes the credibility hit.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_procedure"],
    "data": [
        "data/registrar_calendar.xml",
        "data/registrar_bodies.xml",
        "data/registrar_document_types.xml",
        "data/registrar_procedures.xml",
        "data/registrar_obligations.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
