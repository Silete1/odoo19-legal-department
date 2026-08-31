{
    "name": "Legal Department - Iraq: Demonstration Data",
    "summary": "A worked Iraqi trading and contracting company: entity, signatories, register, five users and live files",
    "description": """
Iraq demonstration pack (بيانات العرض التوضيحي)
================================================

Installs a complete, plausible Iraqi legal department so that every screen in
the product has something real on it the moment it is opened.

**شركة الرافدين للتجارة والمقاولات العامة المحدودة** - a Baghdad LLC formed in
2016, capital IQD 750,000,000, registered at the Companies Registrar, filed at
the General Commission for Taxes, insured at Social Security and carrying a
Chamber of Commerce identity of الصنف الأول. Its four identifiers are four rows,
because those are four different numbers quoted at four different windows.

What the demo puts on each screen
----------------------------------

* **The document register** deliberately holds one of each state a board must
  be able to draw: a Chamber identity in force, a municipal licence expiring
  within the month, and a tax clearance that **has already expired**. A
  demonstration in which everything is green demonstrates nothing.
* **Five users, one per role**, each with an Arabic name, the Baghdad timezone
  and Arabic as their interface language. The follow-up officers are put on the
  ``officer_ids`` of the bodies they actually chase, which is what the per-body
  record rule reads - there is no group per ministry anywhere in this product.
* **Live files at different stages**: one waiting on us, one that has been
  sitting at the Tax Commission since April with three chase letters and a
  return for correction against it, one about to expire, one just completed.
  Their ages come from ``date_open`` and from the dates on the letters, which
  are real fields. What the demo cannot fake is *days at this step*: that is
  computed off ``legal.action.log``, which refuses every write including an
  administrator's, so a freshly installed demo shows each file as having
  arrived at its step on install day. That refusal is the engine behaving
  correctly, and seeding around it would have meant lying in the one table
  whose whole purpose is not to be edited.
* **A correspondence register with real numbers** - رقم صادر and رقم وارد in the
  form a Baghdad department writes them - including a **telephone contact note**
  that consumes no register number and carries a promised date, which is the
  entry that stops the software chasing a body that has already answered.

Why this lives in ``data/`` and not in ``demo/``
-------------------------------------------------

A pack whose content only appears when the database was created with demo data
is a pack that does not demonstrate: the first thing a consultant does for an
Iraqi pilot is create a clean database with ``--without-demo=all``. Installing
*this module* is itself the opt-in, and its name says so, so the records load
from ``data/`` and appear in every database. Uninstalling the module removes
them again.

The seal, the two specimen signatures and the letterhead emblem in
``static/img/`` are generated, not scanned, and the company, its people and its
file numbers are invented.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": [
        "legal_iq_registrar",
        "legal_iq_tax",
        "legal_iq_chamber",
        "legal_iq_social_security",
        "legal_iq_residency",
    ],
    "data": [
        "data/demo_language.xml",
        "data/demo_currency.xml",
        "data/demo_admin.xml",
        "data/demo_company.xml",
        "data/demo_users.xml",
        "data/demo_documents.xml",
        "data/demo_cases.xml",
        "data/demo_correspondence.xml",
        "data/demo_letter_templates.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
