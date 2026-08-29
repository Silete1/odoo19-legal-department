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
""",
    "version": "19.0.1.0.0",
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
        "data/mail_template_data.xml",
        "report/paperformat.xml",
        "report/report_office_letter.xml",
        "report/report_certificate.xml",
        "report/report_request_summary.xml",
        "report/report_actions.xml",
        "wizard/dma_decision_reason_views.xml",
        "views/dma_document_type_views.xml",
        "views/dma_accreditation_scope_views.xml",
        "views/dma_fee_payment_views.xml",
        "views/dma_approval_line_views.xml",
        "views/dma_accreditation_request_views.xml",
        "views/dma_accreditation_settings_views.xml",
        "views/dma_menus.xml",
    ],
    "demo": [
        "demo/dma_demo_users.xml",
        "demo/dma_demo_requests.xml",
    ],
    "assets": {
        "web.report_assets_common": [
            "dma_accreditation/static/src/scss/dma_report.scss",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}
