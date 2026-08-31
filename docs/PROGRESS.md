# Legal Affairs (legal_dept) — audit/redesign progress

Living checklist for the audit → redesign → implementation of the Iraqi
corporate Legal Affairs suite. A fresh session resumes from here.

## Environment facts (verified 2026-08-31)

- Server: source checkout `odoo-19.0/`, venv `.venv_odoo19` (the live process
  currently uses system Python311 — both have the deps), config
  `odoo19_legal.conf`, port **8090**, DB **legal_dept**, data dir
  `.odoo_data_legal`.
- Launch: `python odoo-19.0/odoo-bin -c odoo19_legal.conf` from repo root.
  No docker, no Windows service for this instance (the PostgreSQL service is
  `PostgreSQL_For_Odoo` from an Odoo 17 installer, listening on 5432).
- Upgrade loop:
  `.venv_odoo19/Scripts/python.exe odoo-19.0/odoo-bin -c odoo19_legal.conf -d legal_dept -u <modules> --stop-after-init --logfile=<fresh log>`
  then restart the foreground server and hard-reload the browser.
- Enterprise addons NOT available (`sign`, `documents`, `helpdesk`, etc. are
  `uninstallable`). Community only.
- Installed custom modules: legal_core, legal_correspondence, legal_procedure,
  legal_iq_registrar, legal_iq_tax, legal_iq_chamber, legal_iq_social_security,
  legal_iq_residency, legal_iq_demo.
- Users: admin/admin + clerk/officer/approver/manager/auditor `@legal.iq`
  (password documented in the task, not here). Langs: ar_001 + en_US active.
- Company: شركة الرافدين للتجارة والمقاولات العامة المحدودة (single company).
- Record counts at baseline: 6 legal_case, 14 legal_correspondence,
  15 legal_document.
- Browser automation: system Python311 has playwright + chromium and reaches
  the server. `npx playwright` 1.62.1 also present. venv python does NOT have
  playwright.
- AI Studio mock: `odoo-19-entry-visas-&-security-clearances.zip` at repo
  root, extracted to the session scratchpad `mock_app/` (React 19 + Vite +
  Tailwind + lucide; AI Studio metadata confirmed).

## Backup / restore

- Filestore backup: `_backups/filestore_legal_dept_20260831/` (copy of
  `.odoo_data_legal/filestore/legal_dept`).
- DB dump: `_backups/legal_dept_20260831.dump` made with
  `"C:\Program Files\Odoo 17.0.20260217\PostgreSQL\bin\pg_dump.exe" -h localhost -U openpg -Fc legal_dept`.
- Restore: `createdb -h localhost -U openpg legal_dept_restored` then
  `pg_restore -h localhost -U openpg -d legal_dept_restored _backups/legal_dept_20260831.dump`,
  then copy the filestore folder back to `.odoo_data_legal/filestore/<dbname>`.
- `_backups/` is git-ignored by the root `/*` rule; never commit dumps.

## Findings queue (from initial scout — feed into audit doc)

- [ ] No `i18n/` translation files anywhere in the legal suite; verify how
      ar_001 renders (labels likely hardcoded in one language).
- [ ] Active currency is USD only; task demands IQD demo currency.
- [ ] Legal modules were untracked by git until this branch (now whitelisted).
- [ ] Coverage gaps vs task scope, to confirm in audit: no litigation/court
      module (legal.case is a *procedure file*, not a lawsuit), no contracts
      module, no legal-opinions module, no internal legal-request intake, no
      hearings, no unified deadline surface, no courts registry.

## Phase checklist

- [x] Scout repo, find module suite, mock app, server, DB, users
- [x] Safety baseline: branch `audit-redesign`, filestore backup, DB dump
- [ ] Baseline git commit of untouched legal suite (+ .gitignore whitelist)
- [ ] Deep audit workflow (static code, security, i18n, OWL, packs, mock,
      browser-per-role with BEFORE screenshots, research) → docs/ui-audit/
- [ ] Synthesis: docs/ui-audit/AUDIT.md severity table + P0–P4 plan
- [ ] Decide target architecture (module layout, menus, new models)
- [ ] P0 fixes
- [ ] P1 core legal workflow (requests, contracts, litigation, opinions,
      deadlines, correspondence, role workflow)
- [ ] P2 operational UX (dashboard, queues, lists, search, forms)
- [ ] P3 corporate legal coverage (records, licensing, POA, optional domains)
- [ ] P4 polish (spacing, icons, empty states, reports, responsive)
- [ ] i18n: translation machinery working for ar_001, zero leakage
- [ ] Demo data: complete Iraqi scenario per §43 (IQD amounts)
- [ ] Tests: backend + frontend green; browser UAT per role (§51)
- [ ] AFTER screenshots + visual regression pass (§52)
- [ ] Final report → docs/ui-audit/FINAL_REPORT.md
