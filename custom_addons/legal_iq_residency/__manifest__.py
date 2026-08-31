{
    "name": "Legal Department - Iraq: Residency & Entry Visas",
    "summary": "مديرية شؤون الإقامة - the entry-visa chain the React prototype hard-coded, as configuration",
    "description": """
Iraq content pack - Directorate of Residency Affairs (مديرية شؤون الإقامة)
==========================================================================

Data only: no ``models`` directory, no field, no Python beyond an empty
``__init__.py``. This pack is the one that proves the claim.

The proof
---------

The original React prototype for this product modelled entry visas with a
thirteen-value ``VisaStatus`` union hard-coded in TypeScript - ``draft``,
``dept_approval``, ``dept_approved``, ``rejected``, ``letter_pending``,
``sent_ministry``, ``at_ministry``, ``sent_residency``, ``at_residency``,
``visa_issued``, ``visa_received``, ``completed``, ``expired`` - with the
transitions, the ministry's outgoing and incoming numbers, the referral date and
the long-term follow-up alert all written as fields of one interface. Adding a
fourteenth state, or a second sponsoring ministry, or one more captured fact,
meant a developer and a release.

Every one of those thirteen states is a ``legal.procedure.step`` row in
``data/residency_procedures.xml``. The named buttons - «تحويل المعاملة إلى دائرة
الإقامة», «إعادة للتصحيح» - are ``legal.procedure.transition`` rows. The
prototype's ``visaNumber``, ``visaValidityDays`` and ``iraqEntryDate`` are
``legal.procedure.field`` rows captured at the step that learns them.

And three of the prototype's fields are deliberately **not** here:
``ministryOutgoingNumber``, ``ministryOutgoingDate`` and
``ministryIncomingNumber`` are رقم الصادر and رقم الوارد. They are register
entries, not properties of a visa request - the engine reserves those names and
points at ``legal.correspondence``, because a department is asked "what did we
send the Ministry of Oil last quarter" in aggregate, and an answer buried in one
workflow's payload cannot be given.

What else is inside
-------------------

* The Ministry of Interior, the Directorate of Residency and its Baghdad office,
  the Foreign Ministry's consular visa section, the sponsoring ministry with its
  own entry-visa section, and the Labour Ministry's Department of Labour and
  Vocational Training that issues the work permit.
* The entry-visa chain, the arrival report due within ten days, the residency
  permit, and the work permit at IQD 250,000 renewed during the last month
  before expiry.
* The federal sequence - residency first, then the work permit - with the
  Kurdistan inversion named in the notes, because in the Region the residency
  card is a *prerequisite* of the permit and the fee is IQD 110,000.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_procedure"],
    "data": [
        "data/residency_calendar.xml",
        "data/residency_bodies.xml",
        "data/residency_document_types.xml",
        "data/residency_procedures.xml",
        "data/residency_obligations.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
