# Deployment

## Addons and dependencies

Add `C:\Users\Lenovo\Documents\odoo19\custom_addons` to `addons_path`. Install `gov_hr_deputation`; Odoo installs `gov_hr_base` automatically. Runtime dependencies resolve entirely from Community/core Odoo 19. The supplied `odoo19_gov_hr_community.conf` deliberately excludes the Enterprise addon path and is suitable for dependency verification.

```powershell
.\.venv_odoo19\Scripts\python.exe .\odoo-19.0\odoo-bin -c .\odoo19_gov_hr_community.conf -d <database> -i gov_hr_deputation --without-demo=True --stop-after-init
```

For tests:

```powershell
.\.venv_odoo19\Scripts\python.exe .\odoo-19.0\odoo-bin -c .\odoo19_gov_hr_community.conf -d <test_database> -i gov_hr_deputation --without-demo=True --test-enable --test-tags /gov_hr_deputation --stop-after-init
```

The final Community-only verification used database `gov_hr_release_test`, installed 42 Community/core modules including the two custom addons, and completed 13 tests with zero failures or errors. Subsequent upgrade runs also passed. Static checks parsed all XML files, imported both Python addon trees, loaded both Arabic PO files, and built the backend and unit-test asset bundles.

The small Owl workflow component has a Hoot unit test and that test is present in `web.assets_unit_tests`. Browser verification with the Arabic requester account confirmed editable draft fields, employee selection, supporting-document type selection, and native binary upload. Complete a full role-by-role UAT cycle in the deployment browser before production acceptance.

A real wkhtmltopdf run produced an archived `%PDF-` final mission order and its rendered A4 page was inspected for RTL government layout, tables, title hierarchy, and print margins. Because no authorized stamp/logo/sample letter was supplied, branding and the visible production stamp still require owner acceptance with the real assets.

## Host prerequisites

- PostgreSQL 13 or newer is required by Odoo 19. The available local server is PostgreSQL 12.4, so Odoo emitted its expected unsupported-version warning during verification; upgrade the database server before production deployment.
- Install a supported `wkhtmltopdf` build reachable by the Odoo service account.
- Enable Arabic (`ar_001`) when Arabic UI labels are required. The official reports contain Arabic RTL text independently of the user's interface language.

## Configuration checklist

1. Assign the small Government HR role groups.
2. Ensure concerned departments have a manager employee with an active internal Odoo user.
3. In Settings, configure the Administrative Department, Director General, default Administrative Officer, and official stamp per company.
4. Confirm the default route and basis types; adjust labels/sequence only with Government HR Manager access.
5. Confirm Arabic language and wkhtmltopdf are installed on the Odoo host.
6. Test a full non-production request and verify the archived PDF before go-live.

No production stamp, logo, signature, or sample government letter was supplied. Upload the authorized stamp in company settings and have the records/communications owner approve the rendered memorandum and mission-order layout before go-live.

The stamp is sensitive configuration. Database/filestore backups must be access-controlled. Archived final attachments are authoritative records and must be included in retention and backup policy.
