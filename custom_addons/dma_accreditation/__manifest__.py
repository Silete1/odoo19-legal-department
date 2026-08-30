{
    "name": "DMA Accreditation",
    "summary": "Office and Operational accreditation of demining companies (IMAS/TNMA 07.30)",
    "description": """
Directorate of Mine Action - Accreditation of Demining Organisations
====================================================================

Implements the two phase accreditation process described by IMAS 07.30 and
TNMA 07.30/01 for the Directorate of Mine Action:

* **Office Accreditation** - reception, General Director initial acceptance,
  Legal Department review, Certifications Division prerequisite checklist and
  the official Office Accreditation letter.
* **Operational Accreditation** - SOP submission (paper and electronic), SOP
  reading fee, parallel Finance/Operations sign off, operational demonstration
  fee, the Accreditation Committee decision, legal refinement of the decision
  and the final Operational Accreditation certificate.

Every transition is recorded in an immutable approval log, posted to the
chatter and pushed to the next responsible group as a scheduled activity.

On top of the procedure itself the module adds three operational layers:

* **Document intelligence** - the prerequisites checklist becomes an evidence
  file: what each document says about itself, whether it is still valid, which
  version is current, what the previous ones were and why they were replaced,
  and precisely which line is holding the office accreditation up.

* **Service levels and escalation** - a configurable target per step, measured
  from the moment the file reached it (read off the approval log, so it can
  never drift), with reminders, escalation to the Accreditation Manager and a
  scheduled job that is safe to run as often as you like.

* **Process performance** - median and p90 waiting time per step, cycle times,
  bottlenecks, departmental workload and rework, all derived from the immutable
  approval log rather than estimated.

Plus the **accreditation dossier**: the complete evidence and decision trail of
one file, as a printed index and as a downloadable archive.
""",
    "version": "19.0.1.1.0",
    "category": "Services",
    "license": "LGPL-3",
    "author": "Directorate of Mine Action",
    "website": "https://www.mineactionstandards.org/standards/07-30-01/",
    "depends": ["base", "mail", "web"],
    "data": [
        "security/dma_accreditation_security.xml",
        "security/ir.model.access.csv",
        "security/dma_accreditation_rules.xml",
        "data/ir_sequence_data.xml",
        "data/dma_accreditation_scope_data.xml",
        "data/dma_document_type_data.xml",
        "data/dma_document_validity_data.xml",
        "data/mail_template_data.xml",
        "data/dma_sla_data.xml",
        "report/paperformat.xml",
        "report/report_office_letter.xml",
        "report/report_certificate.xml",
        "report/report_request_summary.xml",
        "report/report_dossier_index.xml",
        "report/report_actions.xml",
        "wizard/dma_decision_reason_views.xml",
        "views/dma_document_type_views.xml",
        "views/dma_document_evidence_views.xml",
        "views/dma_accreditation_scope_views.xml",
        "views/dma_fee_payment_views.xml",
        "views/dma_approval_line_views.xml",
        "views/dma_accreditation_request_views.xml",
        "views/dma_accreditation_settings_views.xml",
        "views/dma_accreditation_dashboard_views.xml",
        "views/dma_sla_views.xml",
        "views/dma_accreditation_request_sla_views.xml",
        "views/dma_menus.xml",
        "views/dma_menus_doc_sla.xml",
    ],
    "demo": [
        "demo/dma_demo_users.xml",
        "demo/dma_demo_requests.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "dma_accreditation/static/src/components/progress/*",
            "dma_accreditation/static/src/components/dashboard/*",
            "dma_accreditation/static/src/components/sla_badge/*",
            "dma_accreditation/static/src/components/dossier/*",
            "dma_accreditation/static/src/components/performance/*",
        ],
        "web.assets_unit_tests": [
            "dma_accreditation/static/tests/**/*.test.js",
        ],
        "web.assets_tests": [
            "dma_accreditation/static/tests/tours/*.js",
        ],
        "web.report_assets_common": [
            "dma_accreditation/static/src/scss/dma_report.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
