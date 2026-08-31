{
    "name": "Legal Department - Management Reports",
    "summary": "Analysis views and the official printed artifacts of the legal department",
    "description": """
Legal Department - Management Reports (التقارير الإدارية)
=========================================================

The suite records everything and, until this module, answered nothing in
aggregate. This module adds the two halves of departmental reporting:

**Analysis.** Pivot and graph views over the existing models - cases by step
and body, the register's traffic by month, fees by body and procedure, the
compliance calendar, lawsuits by court and capacity, contract values, requests
and opinions by month. No new models: every figure is read from the records the
other modules already keep, under the access rules they already enforce.

**Prints.** Four official artifacts, Arabic and right-to-left the way the
printed page actually leaves the department:

* دفتر السجل - the register book of a year, voided rows struck through exactly
  as a clerk strikes them.
* غلاف الإضبارة - the case file cover sheet: procedure, step, fees, the
  document checklist and the trail.
* تقرير موقف الدعوى - parties, court, hearings, judgments and the appeal
  windows still open.
* خلاصة العقد - parties, value with its amendment trail, key dates and the
  obligations with their states.

The printed bodies are deliberately Arabic-only - an official Iraqi artifact is
Arabic whatever the language of the officer who pressed Print - and follow the
official letter's own conventions: Arabic-Indic numerals where the company asked
for them, Baghdad dates, and a book number block where the paper is formal.
""",
    "version": "19.0.1.0.0",
    "category": "Services/Legal",
    "license": "LGPL-3",
    "author": "Legal Department",
    "depends": [
        "legal_procedure",
        "legal_correspondence",
        "legal_litigation",
        "legal_contract",
        "legal_opinion",
        "legal_request",
    ],
    "data": [
        "security/ir.model.access.csv",
        "report/legal_reports_paperformat.xml",
        "report/report_register_book.xml",
        "report/report_case_cover.xml",
        "report/report_lawsuit_status.xml",
        "report/report_contract_summary.xml",
        "report/legal_reports_reports.xml",
        "views/legal_reports_case_views.xml",
        "views/legal_reports_correspondence_views.xml",
        "views/legal_reports_litigation_views.xml",
        "views/legal_reports_contract_views.xml",
        "views/legal_reports_request_opinion_views.xml",
        "views/legal_reports_compliance_views.xml",
        "wizard/legal_register_book_wizard_views.xml",
        "views/legal_reports_menus.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "legal_reports/static/src/scss/legal_reports_print.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
