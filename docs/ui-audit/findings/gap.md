# Functional Coverage Gap Analysis — legal suite vs. target Iraqi corporate legal-affairs product

Audit date: 2026-08-31 · BEFORE state · DB `legal_dept` @ :8090 (all 9 `legal_*` modules installed, 19.0.1.0.0)

## Summary

The installed suite is a **government-liaison transaction engine**, not a corporate legal-affairs
system. What it does, it does unusually well: a data-driven procedure engine (`legal.case` walking
`legal.procedure.step` rows — no hardcoded state machine), a faithful صادر/وارد register with
void-not-delete and frozen letter snapshots, a permanent document register with supersede chains, a
genuinely blocking POA gate, a statutory-obligation calendar with an idempotent generator, an
append-only action trail, a real 5-role security ladder with a server-side read-only auditor, and
three server-composed OWL screens (Mail Room / My Desk / Body Desk). Five Iraq content packs prove
the "configured, not coded" claim (23 procedure types, 17 obligation schedules, 39 bodies seeded).

Against the client spec, however, **five of the thirteen target areas do not exist at all**:
contracts + contract obligations, litigation cases + hearings + a courts registry, legal
opinions/consultations, a legal-request intake front door, and a unified deadline control tower.
There is a `COURT` body type but **zero court records**; the jurisdiction table holds only two rows
(federal / KRI) — **no governorates**. Reporting is one QWeb letter report; there is not a single
pivot/graph view in the suite. No legal module ships an `i18n/` directory, so an Arabic (`ar_001`)
user sees untranslated English field labels and menus despite the Arabic-first requirement.

The good news: the existing engine and mixins (`legal.expiry.mixin`, snapshot-freeze pattern,
obligation instance generation, per-body record rules) are exactly the primitives the missing areas
need. The redesign is mostly **additive** — four new modules plus a unification layer — not a
rewrite.

## Matrix

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Request intake + triage + approval | No request model. Intake = clerk registers incoming letter in Mail Room, or opens `legal.case` directly. Approval = transition `group_ids` gates | Business departments cannot submit a request; no triage queue, no accept/reject/convert lifecycle, no requester visibility | **high** | New `legal.request` (طلب خدمة قانونية) that routes/converts to case, contract, opinion or lawsuit; keep transition gates as approvals |
| 2 | Contracts + contract obligations | Nothing. Only `contract_value` on case (fee % rules) and contract *documents* as register rows | Core spec area wholly missing: no lifecycle, no parties, no renewal, no per-contract obligations | **critical** | New `legal_contract` module: `legal.contract`, `legal.contract.obligation` feeding the unified deadline layer; reuse expiry mixin + document register |
| 3 | Litigation + hearings + courts registry | `COURT` body type exists (0 rows); POA has `litigation` scope; no lawsuit, hearing, judgment or court model; 2 jurisdictions, no governorates | Second core spec area wholly missing; engine has no repeating-session child concept | **critical** | New `legal_litigation`: `legal.court` registry (degree: بداءة/استئناف/تمييز/عمل/جنح وجنايات/قضاء إداري × governorate), `legal.lawsuit`, `legal.hearing`, judgments; seed 18 governorates under `legal.jurisdiction` |
| 4 | Legal opinions / consultations | Nothing dedicated. Freeze-on-issue mechanic already exists in correspondence (`snapshot_html`) | No opinion record, no draft→review→issue→frozen lifecycle, no opinion register | **high** | New `legal.opinion` reusing the snapshot-freeze + register-number pattern from `legal.correspondence` |
| 5 | Correspondence register | **Complete & strong**: registers, year-reset clerk-editable numbers, gap check, void with reason, secrecy rule, contact notes, reply clock, templates, QR letter report | Only links to `legal.case`; new object types (lawsuit/contract/opinion) will need origin links | low | Extend with m2o links (or one relation model) to the new objects; keep everything else |
| 6 | Corporate records / licenses | **Mostly covered**: `legal.entity` + identifiers + signatories + `legal.document` supersede chain, grades, freshness, Renewals Due | No board-resolution/meeting register, no capital-change history as first-class rows | medium | Extend: `legal.entity.resolution` (or document kind + dated rows); keep register as-is |
| 7 | POA / authorizations | **Good fit**: `legal.poa` — who/which body/when gate, litigation scope, bar registration, revocation wizard, blocking transitions | No lawsuit link yet; no internal تخويل (authorization letter) print; 0 records in demo | low | Keep model; add `lawsuit_ids` + تخويل QWeb report; seed demo POAs |
| 8 | Unified deadline control | Four separate clocks: obligation instances, SLA due/warn/escalate, correspondence `reply_due_on`, document/POA expiry, case `date_deadline` | No single screen/model unifying them; hearings & contract obligations will add a 5th and 6th source | **high** | `legal.deadline` union view (`_auto=False`) + calendar/list + daily digest cron; one "control tower" menu |
| 9 | Properties (optional) | Nothing | Optional per spec | low | Small `legal.property` register on top of document register, if bought |
| 10 | Investigations / committees (optional) | Nothing; procedure engine could host committee stages | Optional per spec; sessions pattern shared with hearings | low | `legal.investigation` + sessions reusing the hearing child pattern |
| 11 | Reports | One QWeb report (official letter ×2 variants). **Zero pivot/graph views in the whole suite** | Spec demands professional reports; managers cannot aggregate anything | **high** | Register book print, case cover sheet, lawsuit/contract/compliance reports; pivot+graph on case, correspondence, fees, obligations |
| 12 | Settings / configuration | Rich config menus (bodies, procedures, docs, registers, SLA, fees, obligations); company-level letterhead/numerals/hijri on `res.company`; no `res.config.settings` panel | Acceptable philosophy (config-as-data) but no central settings screen; company fields hidden on company form | medium | Thin `res.config.settings` section exposing company legal fields + defaults |
| 13 | Role dashboard | OWL Mail Room + My Desk + Body Desk, payloads 100% server-side (`legal.dashboard`), role-aware; Overdue/Escalations/Compliance menus | No manager KPI/analytics screen, no approver "awaiting my signature" queue, no auditor view; desks unaware of future areas | medium | Extend `legal.dashboard` with manager/approver/auditor briefs; new areas plug their columns into the same payload composer |
| — | Arabic-first & translations (cross-cutting) | `ar_001` active, demo users Arabic, RTL letter SCSS; **no `i18n/*.po` in any legal module**; labels/strings English with Arabic asides | Arabic user gets a mixed EN/AR interface — fails "Arabic-first with working translations" | **critical** | Export `.pot`, ship complete `ar.po` per module (pattern exists in `gov_hr_base/i18n/`) |
| — | IQD currency (cross-cutting) | IQD defaulted everywhere (`base.IQD` on case, fee, document, entity) | — (covered) | — | Keep |
| — | Security incl. read-only auditor (cross-cutting) | 5 groups + registrar job group; auditor is 1,0,0,0 on **every** model; per-body officer record rules; engine-owned fields refused in `write()` | — (covered; strongest part of the suite) | — | Replicate the same ACL ladder + auditor row on every new model |

## Detailed notes by area

### 1. Legal request intake, triage, approval lifecycle — HIGH

**What exists.** Intake today is the Mail Room client action
(`legal_procedure/models/legal_dashboard.py:352` `get_mail_room_data`; menu at
`legal_procedure/views/legal_dashboard_views.xml:39`): incoming letters land in
`legal.correspondence` (`legal_correspondence/models/legal_correspondence.py:66`) with a nullable
`case_id` added by `legal_procedure/models/legal_correspondence.py:21`, and the dashboard offers
"open a file from this letter" (`_new_case_action`, `legal_dashboard.py:565`) and
`link_correspondence` (`legal_dashboard.py:1428`). Approval is expressed as transition gating:
`legal.procedure.transition.group_ids` (`legal_procedure/models/legal_procedure_transition.py:62`)
plus `require_reason/require_valid_poa/require_documents/require_fees_paid` flags, enforced in
`legal.case._fire`/`_blockers` (`legal_procedure/models/legal_case.py:789,1059`). The engine also
hard-refuses RPC writes to workflow-owned fields (`legal_case.py:902` reading
`WORKFLOW_OWNED_FIELDS` from `legal_procedure/models/legal_constants.py:88`) — a real server-side
approval guarantee.

**Gap.** There is no طلب (request) object: an employee of the finance department cannot ask the
legal department for anything through the system; there is no triage state (new → under review →
accepted/rejected/converted), no requester-visible tracking, no routing decision recorded
("this became contract C-102 / opinion O-31"). The spec's clerk→officer→approver intake ladder is
implementable today *only* by configuring a `legal.procedure.type` per request kind, which
mis-uses the government-facing engine for an internal service desk and gives the requester nothing.

**Recommendation.** New model `legal.request` in a small `legal_request` module: requester
(user/department), classification (استشارة / عقد / دعوى / معاملة / أخرى), priority, description +
attachments, triage actions that **create and link** the downstream object (case, contract,
opinion, lawsuit) and close the request with a pointer. Reuse the five groups; the approver gate
stays on the downstream object's transitions. Do not extend `legal.case` for this: the case is
version-snapshotted per procedure (`legal_case.py:75 procedure_version`) which is meaningless for
intake and would force a fake procedure type per request category.

### 2. Contracts + obligations lifecycle — CRITICAL

**What exists.** Nothing contract-shaped. The word appears only as: `contract_value` on the case
for percentage fee rules (`legal_case.py:294`), `max_contract_value` on licence grades
(`legal_core/models/legal_document_type.py:48`), and contract *documents* (عقد التأسيس, عقد إيجار
مصدق) as document types in the packs (`legal_iq_registrar/data/registrar_document_types.xml:49,284`).
The obligation engine (`legal_procedure/models/legal_obligation.py:17` schedule, `:329` instance)
is deliberately **statutory**: keyed to body/jurisdiction/procedure with four calendar shapes and a
12-month idempotent generator — there is no way to say "clause 7 of contract X requires a bank
guarantee renewal every 6 months until 2028".

**Recommendation.** New `legal_contract` module (this is the largest single build):
- `legal.contract`: number, Arabic/English title, type (m2o `legal.contract.type`), our entity
  (m2o `legal.entity`), counterparty(ies) (`res.partner` lines with role), value (Monetary, IQD
  default like `legal_case.py:299`), signature/commencement/expiry dates, renewal terms, state
  ladder draft → legal review → approved → signed → active → expired/terminated/renewed with the
  approver gate; `_inherit` `mail.thread`, `mail.activity.mixin`, **`legal.expiry.mixin`**
  (`legal_core/models/legal_expiry_mixin.py:40` gives expiry_state/notice/renewal-lead for free).
- `legal.contract.obligation`: clause reference, responsible party/user, one-off or recurring
  (borrow the schedule shapes), amount, due date(s) — materialised into dated instance rows exactly
  as `legal.obligation.schedule._generate` does (`legal_obligation.py:252`), so the unified
  deadline layer sees them.
- The signed PDF files into `legal.document` with a `company_register` type, so supersede/renewal
  history is inherited, and the outgoing signed letter goes through the correspondence register.
- Fit-with-extension option considered and rejected: driving the contract *approval* through
  `legal.case` procedure types would give versioned workflow for free, but the contract is a
  long-lived asset with its own obligations and renewal, not a file that closes; the case engine's
  terminal-outcome design (`legal_constants.py:41 OUTCOME_SELECTION`) fights that.

### 3. Litigation, hearings, courts registry — CRITICAL

**What exists.** Three stubs prove courts were anticipated but never built:
`body_type_court` (محكمة) in `legal_core/data/legal_gov_body_type_data.xml:69` — **zero bodies of
that type in the DB** (verified by SQL: 39 bodies, none COURT); `legal.poa.scope = 'litigation'`
with bar-association fields (`legal_procedure/models/legal_poa.py:70-93`) and a scope-aware gate
`_is_valid_for(scope='litigation')` (`legal_poa.py:187`); and `legal.jurisdiction` is hierarchical
(`parent_id`/`parent_path`, `legal_core/models/legal_jurisdiction.py:32`) but seeded with only
IQ-FED and IQ-KRI (`legal_core/data/legal_jurisdiction_data.xml`) — **no 18 governorates**. There
is no lawsuit model, no hearing model, no judgment, no opponent/party structure, and the engine has
no repeating-event child (checks `legal.case.step.check` are per-step to-dos, `legal.action.log`
is an append-only audit trail — `legal_procedure/models/legal_action_log.py:29`).

**Recommendation.** New `legal_litigation` module:
- **Courts registry**: `legal.court` — name, degree Selection (محكمة البداءة / الاستئناف / التمييز /
  محكمة العمل / محكمة الجنح والجنايات / القضاء الإداري), governorate m2o `legal.jurisdiction`,
  optional link to a `legal.gov.body` row (type COURT) so calendars, officers, record rules and
  correspondence addressing all work unchanged. Seed data: 18 governorate jurisdictions under
  IQ-FED/IQ-KRI + the court network (بداءة per governorate, استئناف per region, تمييز اتحادية…).
- **`legal.lawsuit`**: our capacity (مدعي/مدعى عليه/شخص ثالث), opponents (partner lines), court m2o,
  court case number + year (the number belongs to the court, same doctrine as `our_number` on
  correspondence), subject/claim value (IQD), lawyer m2o with **required valid litigation POA**
  (reuse `legal.poa._is_valid_for`), degree-progression (بداءة → استئناف → تمييز as linked
  lawsuits or rounds — the engine's `round` concept at `legal_case.py:131` is the precedent),
  judgment records with dates and appeal windows (appeal deadline = deadline row, never a computed
  absence — the doctrine stated at `legal_obligation.py` module docstring).
- **`legal.hearing`**: one2many on lawsuit — date, courtroom/الهيئة, purpose (مرافعة/استماع
  شهود/نطق بالحكم…), attendance, minutes, decision, **next hearing date** which auto-creates the
  next row and a deadline entry. This is the child-record pattern the spec names explicitly.
- Engine reuse verdict: model litigation as a *sibling* of `legal.case`, not on it. The case
  engine assumes a configured linear-ish procedure snapshot; litigation is adversarial,
  open-ended, degree-recursive and hearing-driven. Reuse the mixins, the POA gate, the
  correspondence links, the SLA/escalation model (`legal.sla.escalation`,
  `legal_procedure/models/legal_sla_rule.py:154`) and the per-body record-rule pattern
  (`legal_procedure/security/legal_procedure_rules.xml` confidential rules) verbatim.

### 4. Legal opinions / consultations with issue-then-freeze — HIGH

**What exists.** No model. But the exact mechanic the spec demands — *editable while drafted,
frozen forever once issued* — is already implemented for letters:
`legal.correspondence.snapshot_html` + `snapshot_attachment_id`
(`legal_correspondence/models/legal_correspondence.py:220,230`), registration locking (number/date/
register immutable after registration, deletion refused, void-with-reason instead — enforced in
model code, not view attrs), and the two-variant QWeb report
(`legal_correspondence/report/report_official_letter.xml:191`).

**Recommendation.** `legal.opinion` in a `legal_opinion` module: requester (links to
`legal.request`), legal question, researcher/reviewer/approver chain (clerk→officer→approver using
the existing groups), the opinion body (Html), references (laws/articles — the suite already has
the habit: `legal_basis`/`legal_basis_url`/`last_verified_on` triple appears on body, document
type, fee rule, obligation), and **issue = take snapshot + allocate an outgoing register number
via `legal.correspondence`** so the issued opinion is simultaneously a frozen artifact and a
register entry. Revision after issue = new opinion superseding the old (`supersedes_id` /
`superseded_by_id` pattern from `legal.document`, `legal_core/models/legal_document.py:95-98`).

### 5. Correspondence register — LOW (best-covered area)

Complete against spec: `legal.register` with year-reset, clerk-editable `our_number`, gap check and
per-register write group (`legal_correspondence/models/legal_register.py:95`), void-not-delete,
secrecy record rule (`legal_correspondence/security/legal_correspondence_rules.xml`), telephone
contact notes consuming no number, reply clock (`reply_due_on/reply_state`), thread rounds,
letter templates with letterhead variants, QR verification token, official-letter report with
paper format. 14 entries live in demo. Only work needed: origin links to the four new objects
(lawsuit/contract/opinion/request) mirroring how `legal_procedure/models/legal_correspondence.py:21`
adds `case_id`, so "all letters of lawsuit X" is one smart button.

### 6. Corporate records / licenses — MEDIUM

`legal.entity` (+ `entity.form` with Companies-Law minimum capital, `entity.identifier` rows per
issuing body, `legal.signatory` with specimen signature/stamp/appointment document —
`legal_core/models/legal_signatory.py:20`) and the `legal.document` register (validity models
including `freshness` for directive 16180/2024 staleness, grades for Chamber أصناف, supersede
chains, Renewals Due menu `legal_core/views/legal_core_menus.xml:29`) cover the register duty well.
The general-assembly procedure ships as pack data (`MOT-GENERAL-ASSEMBLY` in DB). Missing as
first-class rows: board/assembly resolutions register and capital-change history (currently only
derivable from superseded عقد تأسيس documents, e.g. demo `demo_documents.xml:92`). Extend
`legal.entity` with a dated resolution/capital line model; no new module needed.

### 7. POA / authorizations — LOW (`legal.poa` fits)

Assessment of fit: **keep**. The model already answers who/which-body/when
(`legal_poa.py:158 _is_valid_for`), blocks transitions (`require_valid_poa` on transition +
`_blocking_reason` shared by gate, desk and blocker summary), distinguishes عامة/خاصة/بالمرافعة,
records the notary and bar registration, refuses unlink, and expires by cron rather than by stale
compute (`legal_poa.py:229 _cron_expire` — the right call for a gate). Needed: `lawsuit_ids` link
when litigation lands; a تخويل (internal authorization) print template; demo/seed rows (POA count
in DB is **0**, so the whole gate is un-demonstrated); optionally an agent-scoped "my deeds" desk.

### 8. Unified deadline control — HIGH

Five clocks exist, each excellent, none unified: obligation instances with state ladder
(`legal_obligation.py:375`), SLA `sla_due_on/sla_warn_on/sla_escalate_on` + live `sla_state`
(`legal_case.py:348-365`) + escalation rows + deadline cron (`legal_case.py:1407
_cron_deadline_scan`), correspondence `reply_due_on/reply_state`, expiry mixin on
documents/POAs/case subjects (`legal_expiry_mixin.py:40`), and case `date_deadline`. The Compliance
Calendar menu shows only obligation instances (`legal_procedure/views/legal_procedure_menus.xml:44`).
Hearings and contract obligations will add two more sources. Build one `legal.deadline` read model
(`_auto=False` SQL union, company- and record-rule-safe) with list + calendar + filters (mine /
my bodies / this week / overdue), one daily digest, and make it the لوحة المواعيد menu. Host it in
`legal_procedure` or a thin `legal_deadline` module the new modules can register sources into
(a `_deadline_sources()` hook keeps it open for packs).

### 9. Properties — LOW (optional)

Nothing exists. If bought: `legal.property` register (سند العقار number, location m2o jurisdiction
/governorate, area, ownership document m2o `legal.document`, encumbrances one2many) — a register
sibling of the document register, plus links from lawsuits (عقارية disputes) and contracts (leases;
the suite already ships عقد إيجار مصدق as a doc type).

### 10. Investigations / committees — LOW-MEDIUM (optional)

Nothing exists. The procedure engine *can* host a committee walk (steps = مراحل التحقيق) — an
internal-only procedure type with `responsible_group_id` per step needs zero code. But a proper
`legal.investigation` (subject employee, committee member lines, session rows sharing the
`legal.hearing` pattern, recommendation, decision, confidential-by-default reusing the
confidential record rule at `legal_procedure_rules.xml` rule_legal_case_confidential) is the
cleaner target if the client confirms the scope.

### 11. Reports — HIGH

Inventory: exactly one report — the official letter, in two `ir.actions.report` variants
(`legal_correspondence/report/legal_correspondence_reports.xml:4,16`) with a dedicated paper
format and RTL SCSS. Nothing else: no register-book print (سجل الصادر/الوارد as the bound book an
auditor asks for), no case cover sheet / file summary, no compliance-status report, no fee ledger,
and — verified by grep across all view XMLs — **no pivot or graph view anywhere in the suite**.
The OWL `legal_chart` component exists (`legal_procedure/static/src/components/chart/`) but only
feeds the desks. Target: per-object QWeb prints (case file, lawsuit status incl. hearings,
contract summary, obligations/compliance for a period, register book by year), plus pivot+graph
views with proper measures on case (our_days/their_days, fee_total), correspondence, fees,
obligation instances, and future lawsuits/contracts, and date-range wizards for the auditor.

### 12. Settings / configuration — MEDIUM

The configuration-as-data philosophy is complete and coherent — Configuration menus for bodies,
types, jurisdictions, document types/kinds/grades, entity forms, identifier kinds, signatories
(`legal_core_menus.xml:48-113`), procedures/steps/phases/transitions/capture fields/doc
requirements/fee schedule/SLA/recurring obligations (`legal_procedure_menus.xml:75-131`),
registers/kinds/letter templates (`legal_correspondence_menus.xml:57-79`). Company-wide options
live as plain fields on `res.company` (`legal_core/models/res_company.py:14` — letterhead stack,
numeral system, Hijri toggle) with no settings panel: a manager must know to open the company
form. Target: a thin `res.config.settings` block (related fields) + defaults for the new modules
(default court, default contract review group, deadline digest hour). Low effort, worth doing for
the "professional product" impression the spec asks for.

### 13. Role dashboard — MEDIUM

What exists is architecturally right: `legal.dashboard` AbstractModel composes every figure,
colour and Arabic sentence server-side (`legal_dashboard.py` module docstring, `:60`), runs as the
calling user so record rules apply, probes models/fields before reading them, counts ageing in the
body's working days, and feeds three OWL screens — Mail Room (`get_mail_room_data:352`), My Desk
(`get_desk_data:913`), Body Desk (`get_body_desk_data:1170`) — plus role brief (`_role_brief:1398`)
and menu-level slices (My Files / Overdue / Blocking Documents / Compliance Calendar / Escalations).
Gaps vs. the spec's "role dashboard (clerk/officer/approver/manager/auditor)": no **manager**
analytics view (volumes, cycle times, fees, per-body league table — nothing aggregates), no
**approver** queue ("files waiting for my signature" = transitions whose `group_ids` include me and
whose blockers are clear — computable today from `available_transition_ids`,
`legal_case.py:377`), and no **auditor** landing (trail + registers + exceptions). Extend the same
payload composer; new modules contribute columns rather than new frameworks.

### Cross-cutting

- **Translations (critical for an Arabic-first spec).** `find` over `custom_addons/legal_*`
  returns **no `i18n/` directory and no `.po/.pot` file** (the neighbouring `gov_hr_base/i18n/ar.po`
  shows the expected pattern). Model strings are English with Arabic asides; `ar_001` is active
  and all five demo users run in Arabic — so the actual UI for the actual users is mixed-language.
  Every module needs a `.pot` export and a complete `ar.po`; new modules should be authored
  Arabic-first in `string=` with English in the po file, or ship day-one `ar.po`.
- **IQD**: covered — `base.IQD` defaulted on case, fee, fee rule, document, document grade, entity
  (`legal_case.py:299` et al.).
- **Security / read-only auditor**: covered and strong — auditor group has `1,0,0,0` on every
  model in all three `ir.model.access.csv` files; workflow fields are write-refused server-side;
  the action log refuses all writes; per-body visibility is data (`legal.gov.body.officer_ids`)
  traversed by record rules, never a group per ministry. **Every new model must replicate the
  ladder + auditor row + company rule + (where sensitive) the confidential rule.**
- **Data reality check (DB):** 6 cases, 14 correspondence entries, 17 obligation schedules,
  0 POAs, 0 court bodies, 2 jurisdictions — the demo demonstrates the engine, not the target
  product's breadth.

## Recommended module architecture

Keep all nine existing modules untouched as the foundation. Add:

| Module | Models | Reuses |
|---|---|---|
| `legal_request` | `legal.request` (+ category m2o) | 5 groups, mail thread, converts-to links |
| `legal_contract` | `legal.contract`, `legal.contract.type`, `legal.contract.party`, `legal.contract.obligation` | `legal.expiry.mixin`, document register, obligation-instance generation pattern, approver transitions |
| `legal_litigation` | `legal.court` (+ degree, governorate), `legal.lawsuit`, `legal.hearing`, `legal.judgment`; seed: 18 governorate `legal.jurisdiction` rows + court network as `legal.gov.body` type COURT | POA litigation gate, correspondence links, SLA escalations, confidential record-rule pattern, body calendars |
| `legal_opinion` | `legal.opinion` | snapshot-freeze + register-number issue from `legal.correspondence`, supersede chain from `legal.document` |
| `legal_deadline` (or in `legal_procedure`) | `legal.deadline` (`_auto=False` union) + digest cron | all five existing clocks + hearings + contract obligations via a `_deadline_sources()` hook |
| `legal_reports` | QWeb prints + pivot/graph views + wizards | existing paper format & RTL letter SCSS |
| optional `legal_property`, `legal_investigation` | registers + session rows | hearing/session pattern, document register |
| i18n pass | `ar.po` in **every** legal module | `gov_hr_base/i18n` as the template |

The procedure engine (`legal.case`) remains the host for **government transactions only**
(المعاملات); requests, contracts, lawsuits and opinions are siblings that reuse its mixins,
security ladder, correspondence integration and dashboard composer — not tenants inside it.

### Proposed Arabic menu tree (target)

```
الشؤون القانونية
├── المكتب                         (Mail Room / My Desk / لوحة المدير حسب الدور)
├── الطلبات القانونية              legal.request  ← جديد
├── المعاملات                      legal.case (الموجود: ملفاتي، المتأخرة، الوثائق المعرقلة)
├── العقود                         ← جديد
│   ├── العقود
│   ├── الالتزامات التعاقدية
│   └── أنواع العقود (إعدادات)
├── الدعاوى والقضايا               ← جديد
│   ├── الدعاوى
│   ├── جلسات المرافعة
│   ├── الأحكام والطعون
│   └── سجل المحاكم (بداءة/استئناف/تمييز/عمل/جنح وجنايات/قضاء إداري × المحافظات)
├── الآراء والاستشارات             ← جديد (قيد الإعداد / الصادرة المجمّدة)
├── سجل الصادر والوارد             (الموجود كما هو)
├── السجلات
│   ├── وثائق الشركة، تجديدات مستحقة، الكيانات، الجهات الحكومية (الموجود)
│   ├── الوكالات والتخويلات        legal.poa (الموجود + طباعة تخويل)
│   └── العقارات (اختياري)
├── المواعيد والالتزامات           ← موحّد جديد
│   ├── لوحة المواعيد الموحدة (رزنامة + قائمة)
│   ├── الالتزامات الدورية (الموجود)
│   └── التصعيدات (الموجود)
├── التقارير                       ← جديد (دفتر السجل، ملف معاملة، موقف الدعاوى، موقف العقود، الالتزام الدوري، الرسوم)
└── الإعدادات                      (الموجود + لوحة إعدادات عامة)
```
