{
    "name": "Legal Department - Core",
    "summary": "Government bodies, legal entities, signatories and the company's document register",
    "description": """
Legal Department - Core (الدائرة القانونية - الأساس)
=====================================================

The shared foundation every other Legal Department module builds on. On its own
it already answers three questions an Iraqi legal department is asked daily:

* **Who are we dealing with?** A typed register of external bodies - ministries,
  directorates, commissions, municipalities, syndicates, federations, banks,
  notaries, publishers and utilities - because the counters that actually block
  a filing include the Bar Association, Al-Rasheed Bank, the Translators
  Association, the newspapers and the electricity directorate, and not one of
  those is a ministry. Each body carries its working calendar, its opening
  hours, its named contacts and the letterhead block a letter to it must print.

* **Who are we?** ``legal.entity`` is the legal person - the LLC, the branch of
  the foreign company, the individual enterprise - which is not the same thing
  as ``res.company``. Every body issues its own identifier for us: the Registrar
  registration number, the tax file number, the social security project number,
  the Chamber membership number, the Kurdistan 14-digit UEN. Those are different
  numbers quoted at different windows, so they are rows, not fields.

* **What do we hold, and is it still valid?** ``legal.document`` is the permanent
  register of every dated artefact the company owns - the certificate of
  incorporation, the tax card, the Chamber identity with its class, the
  contractor classification with its grade, the municipal licence, a visa, a
  residency. A renewal creates a new record that supersedes the old one; it is
  never an edit that destroys the trail.

The reason this matters is that Iraqi procedure is a graph, not a list: a filing
at the Registrar is refused without good-standing letters from the Tax
Commission and Social Security, and a tender demands a Chamber identity that is
valid *at the closing date*. Documents produced by one body are inputs to
procedures at another, so they must live in one register that every module reads.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["base", "mail", "web", "resource"],
    "data": [
        "security/legal_core_security.xml",
        "security/ir.model.access.csv",
        "security/legal_core_rules.xml",
        "data/legal_jurisdiction_data.xml",
        "data/legal_gov_body_type_data.xml",
        "data/legal_document_kind_data.xml",
        "views/legal_jurisdiction_views.xml",
        "views/legal_gov_body_views.xml",
        "views/legal_entity_views.xml",
        "views/legal_signatory_views.xml",
        "views/legal_document_type_views.xml",
        "views/legal_document_views.xml",
        "views/legal_core_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "legal_core/static/src/scss/legal_backend.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
