# Odoo 19 Government HR Deputations

Community-safe Odoo 19 modules for Arabic government employee deputations
(`الإيفادات`). One case drives the memorandum, mission order, approvals,
supporting-document verification, outgoing registration, and immutable final
PDF archive.

## Modules

- `gov_hr_base`: reusable government administrative case, approval route,
  activities, structured audit history, organization role resolution, and
  company configuration.
- `gov_hr_deputation`: deputation fields and participants, structured
  supporting documents, workflow configuration, Arabic RTL reports, final
  stamp archival, analytics, security, and tests.

Runtime dependencies are Odoo Community/core only: `mail` and `hr`. There are
no Enterprise or third-party module dependencies.

## Installation

Add this repository's `custom_addons` directory to the Odoo `addons_path`, then
install the application module. Odoo installs the foundation automatically.

```powershell
python path\to\odoo-bin `
  -d your_database `
  --addons-path=path\to\this-repository\custom_addons,path\to\odoo\addons `
  -i gov_hr_deputation `
  --without-demo=True `
  --stop-after-init
```

For an existing installation, replace `-i` with `-u`.

## Tests

Run against a disposable database:

```powershell
python path\to\odoo-bin `
  -d gov_hr_test `
  --addons-path=path\to\this-repository\custom_addons,path\to\odoo\addons `
  -i gov_hr_deputation `
  --without-demo=True `
  --test-enable `
  --test-tags /gov_hr_deputation `
  --stop-after-init
```

The verified Odoo suite currently reports 13 tests with zero failures and zero
errors. The role-based local UAT accounts can be created on a disposable
database with `scripts/setup_gov_hr_test_users.py`; see
`docs/test_users.md`. Never run that script against production.

## Documentation

Architecture, workflow, security, reporting, deployment, Odoo reuse findings,
and Access migration analysis are under `docs/`.

## License

Both addon manifests declare LGPL-3.0. See the Odoo module manifests for the
authoritative addon metadata.
