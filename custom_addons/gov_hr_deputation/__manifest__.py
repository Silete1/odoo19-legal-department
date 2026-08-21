{
    "name": "Government HR Deputations",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Arabic government employee deputation workflow and official documents",
    "license": "LGPL-3",
    "author": "Government HR",
    "depends": ["gov_hr_base"],
    "data": [
        "security/gov_hr_deputation_security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/default_workflow.xml",
        "data/basis_types.xml",
        "report/paperformat.xml",
        "report/memorandum_report.xml",
        "report/mission_order_report.xml",
        "report/report_actions.xml",
        "views/deputation_views.xml",
        "views/deputation_reporting_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "gov_hr_deputation/static/src/components/workflow_overview/*",
        ],
        "web.assets_unit_tests": [
            "gov_hr_deputation/static/tests/**/*",
        ],
    },
    "installable": True,
    "application": True,
}
