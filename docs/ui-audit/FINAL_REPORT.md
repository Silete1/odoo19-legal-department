# Legal Affairs Management System — Final Report

Audit → redesign → implementation of the Iraqi corporate legal-affairs suite on
Odoo 19 Community. Instance: `http://localhost:8090/odoo`, DB `legal_dept`.
Branch `audit-redesign`. Date: 2026-08-31.

---

## A. Initial audit

**What was found.** Nine custom modules forming a well-engineered
*government-liaison transaction tracker*: `legal_core` (bodies, entities,
signatories, permanent document register), `legal_correspondence` (صادر/وارد
register with void-not-delete integrity), `legal_procedure` (a data-driven
procedure engine — `legal.case` walking configurable `legal.procedure.step`
rows, immutable action log, SLA clocks, POA gate, statutory obligations),
five Iraq content packs (Registrar, Tax, Chamber, Social Security, Residency —
pure data: 39 bodies, 52 document types, 23 procedures, 19 obligation
schedules, 24 IQD fee rules) and `legal_iq_demo` (a fictional Baghdad LLC with
five role users). Three OWL client screens (Mail Room, My Desk, Body Desk)
with server-composed payloads and exemplary RTL SCSS.

**The mock.** `odoo-19-entry-visas-&-security-clearances.zip` at the repo root
— an AI Studio React 19 + Vite + Tailwind single-page lookalike for a sibling
domain (entry visas for oil companies). Audited screen by screen
(`findings/mock.md`): its *presentation* ideas were worth porting (KPI →
filtered-action drill-through, expiry countdown badges everywhere, صادر/وارد
numbers as first-class card content, the official-letter anatomy,
phase-coloured sections); its implementation was theatre (client-side "roles",
`Math.random()` document numbers, a fake pivot, an embedded Odoo-module
exporter generating substandard code). Nothing of its code was reused.

**The audit fleet.** 17 agents (9 static/code/security/i18n/domain, 6
per-role browser walks producing ~345 BEFORE screenshots, 2 research) +
synthesis → `AUDIT.md` (master severity table, P0–P4 plan, target
architecture). Findings files under `findings/`, research under `research/`.

## B. Problems discovered (highlights, full detail in AUDIT.md)

- **Functional:** five of thirteen target domains did not exist at all —
  request intake, contracts + contractual obligations, litigation + hearings +
  a courts registry, legal opinions, unified deadlines. Zero pivot/graph views
  anywhere. One QWeb report in the whole suite.
- **Broken:** the case kanban (Files / My Files) crashed for every role — the
  progressbar aggregated a deliberately non-stored field in SQL; the flagship
  official-letter PDF could not render (wkhtmltopdf absent from PATH).
- **Security:** the engine's "cannot be bypassed" write-guard keyed on a
  client-forgeable RPC context flag (verified exploitable); the correspondence
  register lock had the same hole plus an un-register path
  (`state → draft` → edit → delete); company seals and specimen signatures
  were readable across companies; all 30 shipped transitions had empty
  `group_ids`, so a clerk could close a file with no approver — verified live.
- **Arabic/RTL:** zero `i18n/` in nine modules while all five role users ran
  `ar_001` — the entire custom vocabulary rendered as an English/Arabic
  patchwork; sources were baked bilingual composites ("صادر - Outgoing"),
  untranslatable and wrong in both languages. RTL *geometry* was excellent.
- **Workflow/UX:** every role landed in an empty Discuss; approver and auditor
  had no home; dashboard tiles counted only the 8 visible rows; the phase
  rail/checklist/counter-walk components shipped registered and tested but
  mounted on no view; admin could not see the app at all; duplicate and
  misnamed menus; USD as company currency with IQD inactive.

## C. What changed

| Area | Old | New | Why |
|---|---|---|---|
| Case kanban | Dead (OWL crash) for all roles | Opens clean for all roles | Progressbar on a non-stored field removed; the per-card clock badge already carries the signal |
| Write guards | RPC-forgeable context flags | Process-local engine marker (`legal_core/models/legal_engine.py`); `procedure_type_id` locked after intake; register locked to draft→registered→void | `readonly` is a hint and a context key is client data; verified over RPC that the spoof is now refused |
| Separation of duties | Clerk could close files, void entries, waive obligations, reopen closures | Terminal moves need approver+ (hidden AND refused server-side on every path), void/reopen officer+, waive approver+ | Approval must be a role, not a button |
| Seals | Cross-company readable | `company_id` + global rules on signatory/identifier/contact | The seal is what makes a letter authentic |
| Money | USD company currency, IQD inactive | IQD active, company currency, whole dinars | Spec; `<function>` writes because `base.*` records are noupdate |
| Missing domains | Absent | Four sibling modules: `legal_request` (REQ intake→triage→officer/approver-gated lifecycle), `legal_contract` (lifecycle + parties + amendments-never-edit + recurring obligation instances), `legal_litigation` (courts registry: 18 governorates + بداءة/استئناف/تمييز/عمل/جنح/إداري; lawsuits with POA-gated filing; hearings that roll the next session; judgments with a **configurable** appeal-window engine counted from التبليغ), `legal_opinion` (draft→review→approve→**issue = freeze snapshot + real صادر register number**; revision supersedes) | The corporate-legal half of the product; each reuses the 5-group ladder, company rules, expiry mixin, correspondence links |
| Deadlines | Five separate clocks, no surface | `legal_deadline`: an `_auto=False` union of **eleven** sources (obligations, case SLA, unanswered letters, document/POA expiry, hearings, appeal windows, contract expiry + contractual obligation instances, request targets, opinion dues) with list + calendar, open-origin, read-only by construction | One control tower instead of five buried lists |
| Reports | One letter report | `legal_reports`: pivot+graph on eight models + four RTL Arabic prints (register book دفتر السجل with struck-through voids, case cover غلاف الإضبارة, lawsuit status, contract summary) | Managers could aggregate nothing |
| Arabic | 0 translations | 3,285 verified entries across nine `ar.po` files (0 empty, 0 placeholder mismatches); sources normalized to single-language English msgids with the department's own vocabulary preserved as the msgstr | The pipeline needs one source language; the Arabic the modules had baked in *became* the translation |
| Landing | Discuss for everyone | Legal is the first app; My Desk (role-composed) its first item; clerk keeps the Mail Room one click away | Odoo 19 opens the first root menu and ignores `res.users.action_id` |
| Dashboard | Tiles counted 8 visible rows; approver/manager/auditor had nothing | Full-domain counts, drill-through by domain, `{loading,error,retry}` states, role bands (manager load/unassigned/SLA-breach; approver awaiting-signature queue incl. requests/contracts/opinions; auditor read-only landing; attention strip of hearings/deadlines/triage) — still one RPC per screen | The dashboard must answer "what needs me today" honestly |
| Dead OWL | Rail/checklist/counter-walk mounted nowhere | Real payload computes on `legal.case` + mounted on the case form; counter-walk writes ticks through ordinary ACL-checked line writes | The best components in the suite shipped as freight |
| Corporate records | Stored expiry states went stale; supersession could retire the newer document | Nightly re-bucketing cron; date+owner guards + import opt-out; tracked expiry dates | A board that lies for a day is worse than none |
| Demo | Approver/auditor saw empty screens; 0 POAs/fees/SLA rules | Full queues for every seat: 5 requests, 5+1 contracts, 4+1 lawsuits with hearings/judgments (one appeal window closing in days), 5 opinions (one issued & frozen with a real register number), SLA rules, fees, an expiring POA | Every role must see meaningful work at login |

## D. Final menu architecture (Arabic labels via ar.po)

```
الشؤون القانونية                     ← the FIRST application
├── مكتبي                            My Desk (role-composed OWL desk)
├── الوارد والصادر                   Mail Room (OWL)
├── العمليات                         Operations: الملفات، ملفاتي، المتأخرة، الوثائق المعرقلة، رزنامة الالتزامات، التصعيدات
├── طلبات الشؤون القانونية           Requests: الطلبات، طلباتي، غير المسندة، بانتظار المصادقة…
├── العقود                           Contracts: العقود، بانتظار المصادقة، المنتهية قريباً، الالتزامات التعاقدية
├── الدعاوى والقضايا                 Litigation: الدعاوى، دعاواي، الجلسات (رزنامة)، الأحكام والطعون، سجل المحاكم
├── الآراء القانونية                 Opinions: الآراء، مكتبة السوابق
├── المواعيد القانونية               Deadlines (unified board: قائمة + رزنامة)
├── السجلات                          Registers: وثائق الشركة، تجديدات مستحقة، الكيانات، الجهات، سجل الصادر والوارد، الوكالات، الرسوم، سجل الوقائع
├── التقارير                         Reports: تحليلات (قضايا/مراسلات/دعاوى/عقود/طلبات/آراء/امتثال/رسوم) + دفتر السجل
└── الإعدادات                        Configuration (manager only; scroll-capped dropdown)
```

One action per menu; the duplicate Mail-Room/Bodies/Procedures mounts removed.

## E. Final functional scope

End-to-end workflows implemented and demo-seeded: legal request intake →
triage → assignment → approval → closure; contract review → internal approval
→ signature (files the signed `legal.document`) → active → obligations →
expiry control; litigation assessment → POA-gated filing → hearings (auto
next-session) → judgment → appeal-window control → approver-gated closure;
opinion drafting → review → approval → issue (frozen snapshot + real outgoing
register number) → revision-by-supersession; correspondence register
(unchanged core, now linked from all four new domains); POAs with activation,
computed expiry and revocation; corporate document register with nightly
re-bucketing; unified deadline board; role dashboards; management analytics
and four printable Arabic reports.

## F. Custom OWL/JS (and why native was insufficient)

| Component | Justification |
|---|---|
| Mail Room / My Desk / Body Desk client actions (pre-existing, finished) | The one question — "what needs me today" — spans eight models with per-body working-day arithmetic; a native dashboard cannot compose role-specific queues in one RPC |
| Phase rail (`legal.case.progress_payload`) | A 14-step configurable procedure is unreadable as a statusbar; the rail shows phases, actors, blockers |
| Checklist widget (`checklist_payload`) | Document lines with register/expiry/producer context, shared meter with the desk |
| Counter-walk widget (`walk_payload` + inverse) | Batched tick-off at the counter; writes go through ordinary ACL-checked line writes |
| KPI tile / worklist / clock badge / chart (pre-existing) | Building blocks of the above |
| Everything else | Native `<list>/<form>/<kanban>/<calendar>/<pivot>/<graph>`, chatter, activities — deliberately not reinvented |

## G. Security (final role matrix — enforced server-side, verified by tests + RPC probes)

| Capability | Clerk | Officer | Approver | Manager | Auditor |
|---|---|---|---|---|---|
| Read all legal records (company-scoped; confidential rules apply) | ✓ | ✓ | ✓ | ✓ | ✓ (incl. confidential, for oversight) |
| Create/edit intake, letters, drafts, requests, documents | ✓ | ✓ | ✓ | ✓ | ✗ |
| Register correspondence / allocate numbers | ✓ | ✓ | ✓ | ✓ | ✗ |
| Void a numbered entry / reopen a closed file | ✗ | ✓ | ✓ | ✓ | ✗ |
| Move a file into a terminal step (close), approve requests/contracts/opinions, waive obligations | ✗ | ✗ | ✓ | ✓ | ✗ |
| Terminate a contract | ✗ | ✗ | ✗ | ✓ | ✗ |
| Configuration (procedures, types, courts, registers, SLA…) | read | read | read | ✓ | read |
| Any mutation (write/create/unlink/chatter/activity/workflow/RPC) | — | — | — | — | ✗ all blocked server-side |

Engine-owned fields (`step_id`, outcomes, register numbers…) are refused for
*every* client path — the trusted marker is process-local and cannot arrive in
an RPC payload. Admin holds Legal Manager (maintenance path).

## H. Testing

- **Backend:** 192 tests across 10 modules — **0 failed, 0 errors** (run with
  `--test-enable --test-tags` against `legal_dept`, i.e. against live demo
  data). The suite covers security (auditor read-only, wrong-role refusals on
  close/void/reopen/waive/approve), state machines, appeal-window arithmetic,
  POA-gated filing, generator idempotency, dashboard payload honesty
  (tile numbers asserted against direct `search_count`s per role), and the
  deadline union board. Getting to green surfaced four real production bugs
  (empty phase rail payload, stale walk-payload cache, a crashing `_order`,
  an uncatchable search exception) — fixed, not worked around.
- **Frontend:** HOOT unit tests for the mail room (error-state retry,
  read-only affordance withholding) and phase rail (markup rendering) in
  `web.assets_unit_tests`.
- **Browser UAT:** six §51 scenarios (request end-to-end, contract, litigation,
  correspondence, POA, auditor mutation sweep) executed by browser agents as
  the real role users — results below (§H-UAT).
- **RTL/resolution:** all browser work at 1366×768 with 1920×1080 re-shoots.

### H-UAT results

Six scenario agents drove the real workflows as the real role users
(~200 evidence screenshots in `uat/`). First pass: **C (litigation), E (POA)
and F (auditor) passed outright**; A, B and D surfaced eleven genuine defects,
**all fixed the same day and re-verified**:

| Scenario | First-pass findings → resolution |
|---|---|
| A — Request | Approved response stayed editable → server-side freeze (`write` override refusing subject/response edits on decided requests, RPC-verified); urgency was a display-only badge → editable through triage; English decision label inside Arabic chatter → translated `_description_selection`; "(CONTRACT)" code suffix on category names → dropped from display_name |
| B — Contract | One-off obligations never reached the Deadlines board → a twelfth union arm; legal roles couldn't create a counterparty → officer now implies contact-creation; signed-document copy duplicated the contract expiry row → excluded from the board |
| C — Litigation | PASSED: filing gate refused without number/POA, hearings rolled forward exactly once, clerk cannot close, approver can. Cosmetics fixed: hearing calendar titles no longer raw ISO timestamps |
| D — Correspondence | The reply clock never cleared — the substantive-reply rule excluded outgoing letters, i.e. every actual reply → rule corrected + stored flags recomputed, RPC-verified `answered`; register-locking held (number edit refused); origin links (case/request/contract/lawsuit/opinion) added to the form — the fields existed on the model but no view exposed them; void button hidden from clerks (server already refused) |
| E — POA | PASSED: activation, expiring decoration, approver-gated revocation with reasons, delete-guard. One mangled Arabic msgstr repaired |
| F — Auditor | PASSED: zero successful writes by any path (UI + XML-RPC battery), clean AccessError messages, desk audit band with zero mutation controls, reads everywhere |

Post-fix: full backend suite re-run **green (0 failed, 0 errors of 192)** with
the freeze/SoD additions in force. The board's synthetic ids were also shrunk
to stay inside XML-RPC's 32-bit marshalling (found by the probe itself).
The English demo values the leak sweep caught (request subjects, contract
titles, obligation names, departments) were re-authored in Arabic in both the
data files and the live rows.

## I. Screenshots

- BEFORE: `docs/ui-audit/before/` (~345 shots, six roles — includes the dead
  kanban, English patchwork, empty approver desk).
- AFTER: `docs/ui-audit/after/` (six roles × 13 screens — Arabic desk with
  role bands, lawsuit kanban, deadline board, reports).
- UAT evidence: `docs/ui-audit/uat/`.

## J. Research sources

- **Reachable and used:** Iraqi Supreme Judicial Council (court hierarchy),
  Ministry of Justice notaries directorate (Law 33/1998 POA practice), Fao
  General Engineering Co. internal bylaw Art. 7 (state-company legal-dept
  functions), Companies Law 21/1997 structure, OCA `agreement`/
  `agreement_legal`/`contract` (16.0–19.0, fetched raw from GitHub — concepts
  adopted, no AGPL code copied into this LGPL suite). Details:
  `research/iraqi_domain.md`, `research/oca.md`.
- **Unreachable/not found directly:** Iraq Oil Exploration Company and
  Ministry of Planning legal-department pages; their functions were covered by
  the Fao bylaw + general sources. Statutory appeal windows (10/15/30/7 days)
  ship as **configurable data flagged for verification**, not hardcoded law.

## K. Remaining limitations

1. The five Iraq content packs and the demo keep Arabic-only record *values*
   (procedure names, bodies) under the `en_US` jsonb key — correct for the
   Arabic-first demo; an English-first deployment would want `name_en` policy
   work.
2. The official-letter QWeb body and the four report bodies are deliberately
   Arabic-only artifacts (documented exception to English-source policy).
3. `legal_procedure`'s statutory-obligation generator shares the (now fixed in
   `legal_contract`) archived-row idempotency edge — latent, tests green,
   flagged for a follow-up.
4. Approver "awaiting signature" queue does not evaluate per-case
   `condition_domain`s (documented in the method; a count would need a
   per-row walk).
5. Properties (الأملاك) and investigations (اللجان التحقيقية) — optional
   domains per spec §19–20 — were not built; the hearing/session pattern and
   confidential record rules are ready for them.
6. Demo dates are static 2025–2026 literals; the showcase will read stale in a
   few months (the expiring POA is seeded install-relative).
7. Multi-DB server: unrelated databases (dma_*) produce mail-cron noise in the
   shared server log; `legal_dept` itself is clean.
