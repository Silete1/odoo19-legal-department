{
    "name": "Legal Department - Iraq: General Commission for Taxes",
    "summary": "الهيئة العامة للضرائب - the annual return, monthly withholding, براءة الذمة and the objection ladder",
    "description": """
Iraq content pack - General Commission for Taxes (الهيئة العامة للضرائب)
=========================================================================

Data only. No ``models`` directory, no field, no Python beyond an empty
``__init__.py`` - which is what makes the "configured, not forked" claim
falsifiable rather than decorative.

What is inside
--------------

* The Commission and the sections a clerk physically walks between - قسم
  الشركات, قسم الاستقطاع المباشر, قسم الحجوزات الضريبية, قسم كبار مكلفي الدخل,
  قسم التدقيق والفحص, القسم القانوني and لجنة الاستئناف. They are separate
  bodies because they are separate queues with separate officers, and a clerk is
  routed by section, never by "the Tax Commission".
* **The annual return**, due 31 May, with the 10% late-filing penalty capped at
  IQD 500,000.
* **Monthly withholding**, remitted to قسم الاستقطاع المباشر within fifteen days
  of the month following the deduction, and the annual deduction schedule due
  31 March.
* **براءة الذمة as it is actually walked**: one step at the Commission carrying
  twenty-two ordered counter checks, each naming the stamp it produces - ختم قسم
  الدخل، ختم الحجوزات الضريبية، ختم الخصم المباشر، ختم تجميع الشركات - because
  "the file is at the Tax Commission" is not an answer and "the file is at window
  seven waiting for ختم الحجوزات الضريبية" is.
* **كتاب عدم ممانعة**, which a Baghdad Governorate tender demands be
  *نافذ الصلاحية عند تاريخ الغلق* - in force at the closing date, not today.
* **The objection ladder as a branch**: twenty-one days to object, the assessed
  tax payable within the objection period or the objection is not heard,
  twenty-one days to appeal a rejection, then cassation.

Every deadline carries its article, its source and the date a human last read
it. Where a figure is disputed, the note says so.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_procedure"],
    "data": [
        "data/tax_calendar.xml",
        "data/tax_bodies.xml",
        "data/tax_document_types.xml",
        "data/tax_procedures.xml",
        "data/tax_clearance.xml",
        "data/tax_obligations.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
