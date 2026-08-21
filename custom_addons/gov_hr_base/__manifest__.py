{
    "name": "Government HR Case Foundation",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Reusable government administrative case and approval foundation",
    "license": "LGPL-3",
    "author": "Government HR",
    "depends": ["mail", "hr"],
    "data": [
        "security/gov_hr_security.xml",
        "security/ir.model.access.csv",
        "data/mail_activity_type.xml",
        "views/res_config_settings_views.xml",
        "views/gov_hr_configuration_views.xml",
        "wizard/gov_hr_return_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
}
