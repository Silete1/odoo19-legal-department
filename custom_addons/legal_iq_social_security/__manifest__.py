{
    "name": "Legal Department - Iraq: Social Security",
    "summary": "دائرة التقاعد والضمان الاجتماعي للعمال - registration, the 30-day notification, contributions and براءة الذمة",
    "description": """
Iraq content pack - Retirement & Social Security for Workers (الضمان الاجتماعي)
================================================================================

Data only: no ``models`` directory, no field, no Python beyond an empty
``__init__.py``.

Why this pack matters more than its size suggests
--------------------------------------------------

Law 18 of 2023 came into force on 1 December 2023 and replaced Law 39 of 1971.
It widened the contribution base from basic salary plus fixed allowances to
basic salary plus **all** allowances, and it left the enforcement teeth in
place: a criminal fine of IQD 1,000,000 to 5,000,000 for failing to register
employees, compensation to the department of **five times** the unpaid
contributions, and a late-payment penalty of 1% a month from day 121 capped at
100% of principal. Counsel's worked example - ten workers at IQD 500,000 a month
over three years of non-compliance - comes to roughly IQD 219 million of
exposure against IQD 30.6 million if paid on time, about seven times.

In March 2025 the Federal Court of Cassation confirmed those liabilities survive
criminal amnesty, because they are financial resources of the Pension Fund
rather than penalties.

So the two clocks in this pack - notify an appointment within **30 days**
(Articles 23 and 93) and pay the monthly contribution - are the highest-value
reminders in the whole suite, and the pack ships them with their arithmetic
rather than with the word "penalties apply".

**One deadline in here is disputed** and is shipped saying so: the monthly
contribution is stated by law-firm sources as due by the end of the following
calendar month, while payroll vendors state fifteen days after month end. The
schedule ships the better-sourced figure, flags itself, and puts the conflict in
the note.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": ["legal_procedure"],
    "data": [
        "data/psso_calendar.xml",
        "data/psso_bodies.xml",
        "data/psso_document_types.xml",
        "data/psso_procedures.xml",
        "data/psso_obligations.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
