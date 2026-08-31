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
- [x] Baseline git commit of untouched legal suite (+ .gitignore whitelist) — 0a8af9b
- [x] Deep audit workflow (17 agents, ~830 BEFORE shots) → docs/ui-audit/ — 223c9c9
- [x] Synthesis: docs/ui-audit/AUDIT.md severity table + P0–P4 plan
- [x] Decide target architecture (4 new modules + deadline + reports; keep the 9)
- [x] **P0 fixes — commit b2c71f9, all verified:**
      - Case kanban un-broken (sla_state progressbar dropped; was non-stored → SQL raise)
      - Write-guard bypass closed: process-local engine marker replaces the
        RPC-forgeable `legal_workflow`/`legal_allocating_number` context flags
        (verified: clerk with spoofed context still blocked)
      - procedure_type_id locked after intake; correspondence locked to
        draft→registered→void (verified: un-register blocked)
      - Seal/signature/identifier/contact scoped to company + rules (cross-company leak closed)
      - legal.document.entity_id cascade→restrict (permanent register)
      - IQD activated as company currency, whole-dinar rounding
      - wkhtmltopdf found at "C:\Program Files\Odoo 19.0.20260525\thirdparty" —
        server relaunched with it on PATH (see scratchpad/cycle.ps1)
      - Auditor still read-only + can read for oversight (verified)
- [x] P1 security: SoD (terminal transitions need approver+, reopen officer+,
      waive approver+, void officer+), admin→Legal Manager, IQD via <function>
      (noupdate lesson: base.* records need function calls on upgrade)
- [x] P1 core legal workflow: legal_request, legal_contract, legal_litigation,
      legal_opinion INSTALLED on legal_dept, zero errors/warnings; showcase in
      legal_iq_demo (4 lawsuits/3 hearings/3 judgments/16 courts/20
      jurisdictions/5 contracts/5 opinions/5 requests); source normalization of
      the 3 existing modules done (252 strings; seeds in docs/ui-audit/i18n/)
- [ ] i18n phase 2: export ar.po scaffolding (odoo-bin i18n export -l ar per
      module — needs proper occurrence metadata; hand-authored po entries have
      none so they don't apply yet), merge msgstr from module ar.po + seed
      maps, -u to load, verify Arabic UI in browser
      NOTE: throwaway DB legal_i18n exists (pre-normalization restore) but
      export can run against legal_dept directly (it is current)
      LESSON: Odoo's PoFileReader requires every entry's '#.' comment to start
      'module: <name>' and applies entries only via '#:' occurrence lines
- [x] Arabic translations COMPLETE & committed (700c859): 3,030 entries across
      7 modules, verified 0 empty / 0 placeholder mismatches — NOT YET LOADED
      into the DB (needs the combined upgrade below)
- [x] legal_deadline union board built & committed (fcbd931) — NOT yet installed
- [x] Demo integrity + menu dedup + corporate self-update committed (495c385):
      opinion finalize records now updatable, SLA rules/fees/expiring POA
      seeded, role landing actions, Registers→40, dup menus killed, expiry
      cron + supersession guards
- [~] Still in flight: legal_procedure UX finisher agent (role bands, honest
      tiles, error states, auditor menus, OWL wiring) + legal_reports agent
- [x] Combined upgrade DONE (zero errors/warnings): 13 modules, Arabic loaded
      (1,792 field descriptions + menus in ar_001), deadline board live (94
      rows), reports installed; delta export+translate for 204 new strings
      DONE; Legal is now the FIRST app (Odoo 19 ignores res.users.action_id —
      lands on first root menu) and My Desk is its first item; desk verified
      in browser per role (Arabic role bands render)
- [x] Test suite GREEN: 0 failed, 0 errors of 192 (commit 0b9ea7f) — four
      real production bugs found & fixed on the way (phases payload, walk
      cache, modification _order, is_overdue search exception, generator
      idempotency, report configurator detour)
- [x] AFTER sweep: 76/76 role×screen renders clean, zero JS errors
- [x] §51 UAT: C/E/F passed; A/B/D findings ALL fixed same day and re-verified
      (freeze on decided requests, editable urgency, translated decision
      labels, reply-clock rule + stored flags, origin links on the register
      form, officer implies contact-creation, one-off obligations on the
      board, board Arabic-first + XML-RPC-safe ids, demo values Arabized,
      po repairs) — suite re-run green 0/0 of 192
- [x] FINAL_REPORT complete (docs/ui-audit/FINAL_REPORT.md)
- [x] Merge audit-redesign → main — DONE; the branch is fully contained in main
      NOTE: server err log tracebacks are all from unrelated dma_* databases
      (multi-DB server); legal_dept clean
- [x] **P2 — مكتبي redesigned in place + analytics split out (module `legal_office`)**
      - The EXISTING `legal_procedure.action_legal_desk` was re-pointed at the
        new `legal_office` tag. Same record, same name, same menu entry, same
        `/odoo/legal-desk` URL. **No second menu entry** — an earlier pass added
        one and it was removed; there must only ever be one مكتبي.
      - What مكتبي used to also carry (one panel per government body) moved to
        its own screen: `legal_office.action_legal_gov_desks`, tag `legal_desk`,
        `/odoo/gov-desks`, menu **مكاتب الجهات** at sequence 3.
      - New: attention rail (3–5 role-specific filtered queues, one line);
        unified work queue crossing 8 registers with a *why* column; agenda off
        the `legal.deadline` union view; tabbed secondary strip; compact
        `+ جديد` in the control panel. No hero numeral anywhere.
      - Analytics: `legal.analytics` → **التقارير والتحليلات**, 14 panels in 4
        sections, every panel states its management question and drills through.
        Chart.js lazily via `loadBundle("web.chartjs_lib")` — zero new deps.
      - Design system `legal_ds.scss` + `legal_native.scss`, scoped by
        `o_legal_view` stamped on 123 view roots by
        `scripts/legal_stamp_view_class.py` (idempotent, has `--check`).
      - `eh_board` evaluated: **licence is OPL-1 (proprietary)**. Nothing copied,
        no dependency taken; native analytics built instead. See
        `docs/ui-audit/MY_OFFICE_REDESIGN.md` §4.
      - Bugs fixed on the way: `legal.case.document.blocking_reason` was
        `store=True` so the Arabic queue rendered frozen English (now split into
        `_compute_blocking_reason`, unstored, `depends_context=('lang',)`);
        `.o_legal_rail` collided with `legal_phase_rail.scss`; client actions
        opened by URL breadcrumbed as *غير مسمى*; queue columns left the subject
        150px; dates were being run through the Arabic-Indic converter.
      - Arabic: `legal_office/i18n/ar.po` 262 entries, 0 untranslated;
        `legal_procedure` catalogue regenerated (1,070 entries, 0 regressions).
- [ ] P2 remainder: search views, form-level polish beyond the shared vocabulary
- [ ] P3 corporate legal coverage (records, licensing, POA, optional domains)
- [ ] P4 polish (spacing, icons, empty states, reports, responsive)
- [ ] i18n: translation machinery working for ar_001, zero leakage
- [ ] Demo data: complete Iraqi scenario per §43 (IQD amounts)
- [ ] Tests: backend + frontend green; browser UAT per role (§51)
- [x] AFTER screenshots for the redesign: `docs/ui-audit/before-office/` (120
      renders) and `docs/ui-audit/after-office/`, 6 roles × 3 viewports, via
      `scripts/legal_ui_capture.py` (note: Odoo's bus never goes idle, so the
      harness uses explicit selector waits, and `/web/login?db=` is required on
      this multi-database server)
- [ ] AFTER visual regression pass for the remaining screens (§52)
- [ ] Final report → docs/ui-audit/FINAL_REPORT.md
