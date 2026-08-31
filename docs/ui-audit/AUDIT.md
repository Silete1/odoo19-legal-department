# Legal Suite — Master Audit & Redesign Blueprint

Synthesis of 15 seat/system audits + 2 research dossiers · BEFORE state · DB `legal_dept` @ :8090 · 2026-08-31

Source findings: `findings/{core,corr,proc,security,i18n,packs,owl,mock,gap,browser_admin,browser_clerk,browser_officer,browser_approver,browser_manager,browser_auditor}.md` ·
Research: `research/{iraqi_domain,oca}.md`

---

## 0. Verdict in one paragraph

The installed suite is an **exceptionally well-engineered government-transaction tracker wearing the wrong
label**. Its spine — a data-driven procedure engine (`legal.case` walking `legal.procedure.step` rows, not a
hardcoded enum), an immutable append-only action log (write/unlink raise even under `sudo`, no group holds
`create`), idempotent crons keyed by real unique indexes, a faithful صادر/وارد register with void-not-delete
and frozen snapshots, a genuine 5-role ladder with a server-verified read-only auditor, and three
server-composed OWL screens with exemplary RTL SCSS — is worth keeping almost entirely. But against the
client spec it is **half a product**: five of thirteen target domains (contracts+obligations,
litigation+hearings+courts, legal opinions, request intake, unified deadlines) **do not exist at all**; the
Arabic-first requirement is **structurally unmet** (zero `i18n/` directories in nine modules while all five
role users run `ar_001`); the money is in **USD with IQD inactive**; the **case kanban crashes for every role**
on a one-character JSON bug; the correspondence write-lock and the engine's own "cannot be bypassed" write
guard are both **defeatable by a client-supplied context key over RPC**; official-company **signature/seal
images leak cross-company**; and there is **no PDF engine installed**, so the flagship official letter cannot
render. The redesign is therefore **mostly additive** (four new modules + a unification layer + a translation
pass + a demo/data fix), sitting on top of a spine that is repaired in a handful of surgical places — not a
rewrite.

### Contradictions reconciled across auditors

1. **"Officer/Approver hit Access-Error walls" (browser_admin #14) vs. "officer/approver reads succeed"
   (browser_officer, browser_approver).** RESOLVED against browser_admin. The five business groups use
   `implied_ids` (`legal_core_security.xml:40-64`): officer→clerk, approver→officer, manager→approver — so
   each inherits clerk's `legal.case 1,1,1,0` ACL (`ir.model.access.csv:40`). browser_admin counted only ACL
   rows *naming* those groups (officer 4, approver 2) and missed inheritance; the live officer/approver walks
   confirm case/correspondence reads work. **The only genuinely locked-out principal is `admin`** (member of
   no legal group). Fix is scoped accordingly (grant admin/support a role or hide the menu tree from
   non-members — not "re-grant officer/approver everything").
2. **"IQD covered — keep" (gap.md) vs. "IQD critical" (core, packs, browser_admin).** RESOLVED: both true at
   different layers. The *fee/model defaults* correctly point at `base.IQD` (keep). The *company currency* is
   USD and the IQD currency record is **inactive** — so every amount renders in dollars and IQD is
   unpickable. The defect is activation + company setting, not the defaults.
3. **"Read-only auditor verified, zero ACL breaches" (security.md, browser_auditor) vs. "auditor sees
   nothing / dashboards blocked" (owl.md).** Both true, not contradictory: the auditor *is* genuinely
   read-only (18/18 live mutation probes denied), AND the auditor is *locked out of the dashboards* by
   `groups="clerk"` on the menus while the spec wants an auditor oversight view. Different problems.
4. **"Security is the strongest part" (security.md, gap.md) vs. three named holes (proc.md context bypass;
   core.md signatory leak; security.md empty transition gates).** RESOLVED: the *ladder design and the ACL/
   record-rule layer* are strong and live-verified; the holes are specific and real — (a) the workflow
   write-guard keys on a client-controllable context flag, (b) `legal.signatory`/identifier/contact have no
   `company_id` and no record rule, (c) all 30 transitions ship with empty `group_ids` so a clerk can close a
   file. The live XML-RPC probe suite in security.md did **not** exercise (a) — proc.md found it by reading
   the dispatch path. All three stand.

---

## 1. Master severity table

Columns: **Area | Current | Problem | Severity | Target | Implementation**

| Area | Current | Problem | Severity | Target | Implementation |
|---|---|---|---|---|---|
| **JS/OWL — case kanban** | `legal_case_views.xml:348-349` `<progressbar colors="{'on_track':'success',…}">` single-quoted Python dict | Odoo 19 `KanbanArchParser.parseProgressBar` runs `JSON.parse` → SyntaxError → OwlError; **Files + My Files dead for every role** (Overdue survives, list-first) | **P0/critical** | Every case list opens | Double-quote the JSON: `colors='{"on_track":"success","warning":"warning","overdue":"danger","escalated":"danger"}'`; add a per-role smoke test that mounts every view type of every action |
| **Reports — PDF engine** | `wkhtmltopdf` not installed (where.exe empty, no Program Files/venv, no ir_config_parameter, 0 log mentions); reports are `qweb-pdf`; `action_snapshot_pdf` raises | The official كتاب — the crown-jewel deliverable — **cannot render**; HTML fallback loses the 55 mm pre-printed letterhead margin | **P0/critical** | Arabic letter PDF renders end-to-end | Install wkhtmltopdf 0.12.6 on the host (or move to a host that has it); embed Amiri/Noto Naskh Arabic `@font-face` in `web.report_assets_common`; surface engine status on the letter form |
| **Security — write guard** | `legal_case.write` refuses `WORKFLOW_OWNED_FIELDS` only when `env.context.get("legal_workflow")` is falsy (`legal_case.py:902-921`); same on `legal_sla_escalation` (`legal_sla_rule.py:1002-1020`) | Context is client-supplied (`service/model.py:88-90` applies it verbatim); a clerk sends `context={"legal_workflow":true}` and writes `step_id`→terminal, forging closure **with no `legal.action.log` row** — voids the central integrity invariant | **P0/critical** | Guard cannot be reached from any client signal | Replace the context flag with a module-level thread-local token set/reset only inside `_engine()` (never serialised), mirroring the *unconditional* log guard the same file already ships; add `with_user()` tests proving the bypass is refused |
| **Security — signatory/seal leak** | `legal.signatory` (specimen signature + `stamp_image`), `legal.entity.identifier`, `legal.gov.body.contact` have **no `company_id` and no record rule** (`legal_signatory.py:20-78`) | Any clerk of any company can read/export **every company's official seal and signature** — the assets that constitute an Iraqi official letter; cross-company leak + over-broad in-company | **P0/critical** | Seal/signature scoped and confidential | `company_id = related('entity_id.company_id', store=True)` + global company rule on all three models; move seal/signature read behind officer+ or a dedicated group; drop the decorative `jurisdiction.company_ids` or enforce it |
| **Correspondence — register lock** | `write` guards `_LOCKED_ONCE_REGISTERED` only when `state!='draft'` and no `legal_allocating_number` ctx (`legal_correspondence.py:750-812`); `state` itself is unlocked; un-void re-runs `_after_registration` | Clerk writes `{'state':'draft'}` → edits number/date/book → edits/unlinks; the `legal_allocating_number` ctx key disables the lock over RPC in one call; un-void duplicates chatter + `legal.document` rows | **P0/critical** | Register is tamper-proof server-side | Add a state-transition guard (registered→void only, via reason; void terminal); replace the ctx flag with an internal sentinel; block `unlink`/`active=False` for any row that ever held a number; make `_after_registration` idempotent |
| **Currency — IQD** | Company currency USD; `res_currency.IQD` **inactive**; fee data denominated IQD via `base.IQD` defaults | Spec mandates IQD; money renders in $, IQD unpickable, Article-28 minimum-capital shows against a currency the user can't use | **P0/critical** | IQD is the company currency, 0-decimals | Activate IQD + set as company currency in `legal_iq_demo/data/demo_company.xml` (add a rate); keep the IQD model defaults; `widget="monetary"` with IQD everywhere money shows |
| **Arabic / i18n** | **Zero `i18n/` dirs** in all 9 modules; 0/164 menus and 0/157 actions carry `ar_001`; source is mixed EN + baked `"صادر - Outgoing"` composites + Arabic-as-msgid | All 5 role users run `ar_001`; entire custom vocabulary renders English or truncates to garbage (`صادر - ing…`, `مسجل - d…`); bidi scrambles English-in-RTL (".Nothing is waiting", "before somebody needs it وكالة Record the") | **P1/critical** | Arabic-first, zero leakage | Normalise sources to single-language English `string=`; export `.pot`; ship complete `ar.po` per module (msgstr = the existing Arabic); load with `ar` mapped to `ar_001`; CI: fail on any Arabic codepoint in py/js/views + 0 untranslated entries; keep letter-body Arabic + numeral helpers as documented exceptions |
| **Contracts + obligations** | Absent; only `contract_value` Monetary on the case + a fee-rule percentage base | Core spec domain wholly missing: no lifecycle (draft→review→approve→sign→active→renew), no parties, no renewal control, no contractual obligations feeding deadlines | **P3/critical(scope)** | Full `legal_contract` module | New module modelled on OCA `agreement`/`agreement_legal`+`contract` **concepts only** (all AGPL-3; suite is LGPL-3 → re-implement, no verbatim port): `legal.contract` (+type, parties, version tree, recitals/sections/clauses), `legal.contract.obligation` materialised as dated instances feeding the unified deadline layer; reuse `legal.expiry.mixin`, signed PDF into `legal.document`, signed letter through the register |
| **Litigation + hearings + courts** | Absent; `COURT` body type exists with **0 rows**; POA has `litigation` scope; jurisdiction has 2 rows (fed/KRI), **no governorates**; engine has no repeating-session child | Second core spec domain wholly missing; no statutory appeal-period engine (fatal 10/15/30/7-day windows from التبليغ) | **P3/critical(scope)** | New `legal_litigation` module | `legal.court` registry (degree بداءة/استئناف/تمييز/عمل/جنح وجنايات/قضاء إداري × محافظة, parent appeal court), `legal.lawsuit` (capacity, opponents, court number, required valid litigation POA), `legal.hearing` one2many (date/purpose/decision/next-date auto-creating the next row + a deadline), `legal.judgment` + appeal-window engine computed from tabligh date & court degree; seed 18 governorate jurisdictions + the SJC court network as `legal.gov.body` type COURT |
| **Legal opinions / consultations** | Absent; the exact issue-then-freeze mechanic already exists in correspondence (`snapshot_html`) | No opinion record, no draft→review→issue→frozen lifecycle, no precedent register | **P3/high(scope)** | New `legal_opinion` module | `legal.opinion` reusing the snapshot-freeze + register-number-on-issue pattern from `legal.correspondence` and the supersede chain from `legal.document`; requester link to `legal.request`; legal-basis citation triple already idiomatic in the suite |
| **Request intake / triage** | Absent; intake today = clerk registers an incoming letter or opens a case directly | Business departments cannot submit a طلب; no triage/accept/reject/convert lifecycle, no requester visibility | **P3/high(scope)** | New `legal_request` module | `legal.request` (requester, classification استشارة/عقد/دعوى/معاملة, priority, attachments) with triage actions that **create+link** the downstream object (case/contract/opinion/lawsuit) and close with a pointer; reuse the 5 groups; do not overload `legal.case` (its per-procedure version snapshot is meaningless for intake) |
| **Unified deadlines** | Five separate clocks: obligation instances, SLA due/warn/escalate, correspondence `reply_due_on`, document/POA expiry, case `date_deadline`; Compliance Calendar shows obligations only | No single control tower; hearings + contract obligations will add a 6th and 7th source | **P2/high** | `legal.deadline` union model | `_auto=False` SQL union (company- and record-rule-safe) with list+calendar+filters (mine / my bodies / this week / overdue), a daily digest cron, one لوحة المواعيد menu, and a `_deadline_sources()` hook so new modules register their columns |
| **Menus** | One "Legal" app; "Mail Room" appears twice (dashboard 532 vs list 169), "Procedures" twice, "Government Bodies" twice (same action 154 under Registers + Config), "My Files" opens an action titled "My Desk"; three naming conventions in one tree; Config dropdown taller than 768 px with no scroll | Ambiguous breadcrumbs/command-palette; manager cannot reach the tail of Configuration (Correspondence kinds, Entities) from the menubar at 1366×768 | **P2/medium→high** | One entry per destination, Arabic, sectioned | Rebuild the tree per §4 Arabic menu; unique short Arabic labels; `max-height + overflow-y:auto` on config dropdown or flatten config into a settings page; remove the duplicate action-154 mount |
| **Dashboard / role home** | Two OWL client actions (Mail Room, My Desk); payloads 100 % server-composed and role-aware; but tiles derive overdue/oldest/urgent from the ≤8-row visible page; no error/retry state; auditor menus gated to clerk; no manager analytics, no approver signature queue, no auditor landing; **all roles land in Discuss** | Tiles undercount past `COLUMN_LIMIT=8` on a screen whose own docstring forbids two disagreeing numbers; any failed RPC = eternal spinner; three of five roles have no real home | **P1/high** | One role-aware desk per audience, honest numbers | Compute every tile with `search_count`/`read_group` over the full domain, drill-through by domain not id-list; add `{data,error}` state + retry + no-permission message; open dashboards to the auditor; add manager (per-officer load, unassigned queue, SLA breaches) + approver (awaiting-my-signature) + auditor (trail/registers/exceptions) bands; set `res.users.action_id` = the desk for legal roles |
| **Cases (engine)** | `legal.case` is a government-transaction file; strong engine; `procedure_type_id` editable relocates `step_id` with no log; reopen records no reason; conditional-move buttons go stale; result-document create not `sudo`; security never tested with a non-admin user | Second write-guard bypass via `procedure_type_id`; reopen has no justification though every other act is reason-strict; clerk lacking `legal.document` create → close rolls back | **P1/high** | Engine invariants hold under RPC | Lock `procedure_type_id` after create (or route through a logged engine move); route reopen through a reason wizard; `sudo()` the result-document create; add `with_user()` ACL/rule/guard tests; widen `_compute_available_transitions` deps or document staleness |
| **Corporate records / licences** | Strong: `legal.entity`+identifiers+signatories, `legal.document` supersede chains, grades, freshness, Renewals Due | `entity_id ondelete="cascade"` empties the "permanent" register past the `unlink` guard; `expiry_state` is a stored compute with **no cron** so boards go stale; supersession has no date/owner comparison; sacred `expiry_date` untracked; letterhead `res.company` fields exposed in no view; no board-resolution/capital-change register | **P1/high→P2** | Register truly permanent + self-updating | `ondelete="restrict"` on `entity_id` (archive entity instead); daily cron recomputing `expiry_state`/`start_by_date` over open documents; date+owner guards in `_supersede_previous` + import opt-out; `tracking=True` on expiry fields; `res.config.settings` exposing company letterhead/numerals/hijri; add `legal.entity.resolution` + capital-change lines |
| **POAs** | `legal.poa` good bones (who/body/when gate, litigation scope, bar fields, revocation wizard, cron expiry); **0 rows seeded** | Free-text `notary_office`; no عامة/خاصة typing tied to authority; no formal إنذار وعزل instrument trail; no lawsuit link; no تخويل print; whole gate un-demonstrated | **P2/medium** | Keep model, complete it | Type the POA (عامة/خاصة/دوائر الدولة); link notary office to the body registry; model عزل as a notarised instrument with its تبليغ; add `lawsuit_ids`; add a تخويل QWeb report; seed demo POAs so the blocking gate demonstrates |
| **Forms** | Half-translated ALL-CAPS EN group titles; `?` help markers on most labels; "In Thread 0" stat button floats detached; `Void - إلغاء` beside routine buttons; phantom empty striped rows in empty x2many lists; top-half ~50 % whitespace; document form has no cancel/renew button though `action_archive_cancelled` exists | Cluttered, half-Arabic, destructive action unguarded; "dense enterprise UI" not met | **P2/medium** | Dense, Arabic, guarded | Arabic sentence-case section titles; help behind hover; button-box in standard position; danger styling + confirm on Void; suppress empty-list striping; rebalance columns; add header buttons for cancel/renew wired to the existing methods |
| **Lists** | Bilingual composite values truncate to garbage in every dense list; LTR reference numbers clipped from the *left* (`…2026/0001` hides the prefix); grouped registers open fully collapsed on a near-empty screen; "Days Left 0" on non-expiring docs; per-row English "Open The File" column wastes the widest column; no suite-wide expiry-badge convention | Register columns unreadable; files indistinguishable; wasted screen; misleading zeros | **P2/medium** | Readable dense registers | Single-language labels (fixes truncation); `dir="ltr"` + right-side ellipsis on reference columns; expand groups by default or flat date-sorted; blank Days-Left when non-expiring; row-click opens the file (drop the verb column); one shared expiry-countdown badge + list decorations reused everywhere |
| **Search** | Good filter foundations (direction/state/reply/mine/this-year + group-bys); combined number-or-subject field; but filter vocabulary mixes EN+AR; entity/signatory/jurisdiction have **no search view**; missing due-date-range filters and group-by responsible/reply_state | Incoherent filter panel; the register of legal persons cannot be filtered/grouped at all | **P2/medium** | Coherent Arabic search everywhere | Translate all filter/group labels; add search views to entity/signatory/jurisdiction; add due-date-range filters + missing group-bys; role-first `search_default_*` (my files, due this week) |
| **JS/OWL — dead layer** | Phase rail, checklist, counter-walk, chart are registered + styled + (2) tested but used by **zero views**; the payload fields they render (`progress_payload`, `checklist_payload`, walk) **don't exist on `legal.case`**; the case form still shows a stock `step_id` statusbar; `t-out` on server HTML renders escaped `<p>` in the live Body Desk; no interactive widget checks `props.readonly` | The most-argued-for UX ships as freight; a 13-step procedure is a raw statusbar; the 1452-line composer has **zero Python tests** | **P1/high** | Wire and finish, don't rewrite | Grow `progress_payload`/`checklist_payload`/walk computes on `legal.case`, mount the rail/checklist/walk on the case form; wrap sanitised HTML in `markup()` client-side; gate interactive widgets on `props.readonly`; add a Python test class per `legal.dashboard` public method |
| **Demo data** | Company USD; approver lands on an **empty** approval band (all 123 steps `responsible_group_id` NULL, all 6 cases `pending_group_id` NULL, transition-group rel empty); 0 POAs/fees/SLA rules/court bodies; calendars 2026-only while instances run to 2027; every date a static literal (rots in weeks); action-log all created at install (stuck-since-April file shows ~0 days) | Two of five roles land on empty screens; half the spec is undemonstrable; "meaningful queue for every role" fails; demo decays monotonically | **P2/high** | Every role a real queue; nothing decays | Activate IQD in demo; seed ≥1 case at an approval step with `pending_group_id`, one manager-assigned file, group-gated closing transitions; seed POAs/fees/SLA rules/court bodies; compute demo dates relative to install day; extend calendars 2025–2027 + 25 Dec; add `verification_status` to schedule/fee-rule models |
| **Reports** | One QWeb report (official letter ×2 variants); **zero pivot/graph views anywhere**; empty `report/` dirs on core+procedure; Action Trail shows "By: OdooBot" on all 19 rows | Managers can aggregate nothing; no register-book print, case cover sheet, lawsuit/contract/compliance reports; audit trail names no human actor | **P2/high** | Professional reports + analytics | New `legal_reports`: register-book print, case file cover, lawsuit-status (with hearings), contract summary, compliance-for-period, fee ledger; pivot+graph on case (our_days/their_days/fee_total), correspondence, fees, obligations, future lawsuits/contracts; fix action-log to record the real acting user; reuse the RTL letter SCSS + paperformat |
| **Security — separation of duties** | All 30 transitions ship `group_ids` empty incl. all 10 closing transitions; void/waive/reopen gated only by generic `write`; registrar `write_group_id` empty on shipped registers | Verified live: a clerk is **offered a case-closing transition** and can drive a file to a terminal outcome with no approver; voiding a numbered entry, waiving a statutory obligation and reopening a closure are all clerk-reachable | **P1/high** | Roles actually required | Populate `group_ids` on approval/closing transitions in the content packs; consider requiring a non-empty group on terminal-bound transitions; gate `action_void`/`action_waive`/`action_reopen` to officer/approver/manager server-side; default a registrar group on seeded registers |
| **Security — admin lockout & action groups** | `admin` is in no legal group → every legal screen is an Access-Error modal; the Legal app is invisible in admin's app switcher; config/audit actions carry no `groups=` so a clerk reads procedure config, the full audit trail and the user list by direct URL | The system administrator has no support/maintenance path to the app or its data-shipped config; defence-in-depth gap on read surfaces | **P1/high→P2** | Admin can support; screens are role-scoped | Give admin/system an explicit legal support role (or a global read rule); put `groups=` on config/audit actions; decide deliberately what the clerk may read; localise the denial dialog |
| **Responsive / RTL geometry** | RTL layout mirroring is **correct everywhere** (o_rtl bundle, mirrored breadcrumbs/statusbar/chevrons, logical-property SCSS, Tajawal from Odoo's own files); **no horizontal overflow** on any screen at 1366 or 1920; the only geometry defects are LTR-reference left-clipping, clipped desk chips, and the config dropdown height | Geometry is a strength to preserve; the failures are content-language + a few overflow-container widths | **low (mostly keep)** | Keep the RTL engineering | Preserve the logical-property SCSS discipline; fix chip min-widths and reference column ellipsis side; scroll-cap the config dropdown |

---

## 2. Prioritized implementation plan (P0 → P4)

### P0 — Broken / dangerous (ship first, days not weeks)

1. **Un-break the case kanban.** `legal_case_views.xml:348-349` → double-quoted JSON in `colors`. Add a
   per-role view-mount smoke test (every action, every `view_mode`). *(unblocks Files/My Files for all 6
   roles — the single highest-leverage fix.)*
2. **Close the workflow write-guard bypass.** Replace the `legal_workflow` context flag with a thread-local
   token set only inside `_engine()` on both `legal.case` and `legal.sla.escalation`; lock `procedure_type_id`
   after create. Add `with_user()` tests that the bypass and the `procedure_type_id` door are both refused.
3. **Lock the correspondence register.** Server-side state-transition guard (registered→void only, via
   reason; void terminal); replace the `legal_allocating_number` context key with an internal sentinel; block
   `unlink`/`active=False` on any ever-numbered row; make `_after_registration` idempotent.
4. **Scope the seal/signature assets.** Add stored-related `company_id` + a global company rule to
   `legal.signatory`, `legal.entity.identifier`, `legal.gov.body.contact`; put seal/signature read behind
   officer+.
5. **Fix `entity_id ondelete`** cascade → `restrict` so a manager delete cannot empty the permanent document
   register.
6. **Activate IQD** and set it as the company currency (demo pack); add the rate.
7. **Install wkhtmltopdf 0.12.6** on the host and verify the Arabic letter renders end-to-end; embed a naskh
   `@font-face`. *(Environment task — flag if the host cannot take it; the letter is the crown-jewel
   deliverable.)*

### P1 — Core workflow correctness & the Arabic-first mandate

1. **Translation pass, all nine modules.** Normalise sources to single-language English `string=` (split every
   `"صادر - Outgoing"`, de-Arabic the msgids in `legal_constants.py:56`, menus, wizard action names, ~150
   view attrs); export `.pot`; ship complete `ar.po` (msgstr = the existing Arabic wording); load with `ar`→
   `ar_001`; add the CI guardrails. Keep the letter-body Arabic + numeral helpers as documented exceptions.
2. **Role home + role-aware dashboards.** Set `res.users.action_id` to the desk for legal roles (stop landing
   in Discuss); fix the tile arithmetic to full-domain `search_count`/`read_group`; add `{data,error}`+retry;
   open the dashboards to the auditor; add manager/approver/auditor bands.
3. **Wire the dead OWL layer.** Add `progress_payload`/`checklist_payload`/walk computes to `legal.case`,
   mount the rail/checklist/counter-walk on the case form, `markup()` the Body-Desk HTML, gate interactive
   widgets on `props.readonly`; add the `legal.dashboard` Python test suite.
4. **Separation of duties.** Populate `group_ids` on approval/closing transitions in the packs; gate
   void/waive/reopen to officer+; route reopen through a reason wizard; `sudo()` the result-document create.
5. **Admin support path + action groups.** Give admin/system a legal role (or a global read rule); put
   `groups=` on config/audit actions.
6. **Corporate-record self-update.** Daily cron recomputing document `expiry_state`; date+owner guards in
   supersession; `tracking=True` on expiry fields.

### P2 — Operational UX & the unification layer

1. **`legal_deadline`** — the `_auto=False` union control tower (list+calendar+filters+digest cron+
   `_deadline_sources()` hook) and the لوحة المواعيد menu.
2. **Menu rebuild** to the §4 Arabic tree; kill duplicates; scroll-cap the config dropdown; one entry per
   destination.
3. **List/form/search polish suite-wide**: single-language labels (fixes truncation), `dir="ltr"` reference
   columns, expand groups by default, one shared expiry badge + decorations, row-click opens file, search
   views on entity/signatory/jurisdiction, danger-styled Void with confirm, suppress phantom striping,
   rebalance form columns, `res.config.settings` for company letterhead/numerals/hijri.
4. **`legal_reports`** — register-book print, case cover, compliance-for-period, fee ledger; pivot+graph on
   case/correspondence/fees/obligations; fix the action-log actor.
5. **Demo/data fix** — real queue for every role, group-gated transitions, seeded POAs/fees/SLA/court bodies,
   install-relative dates, calendars 2025–2027, `verification_status` on schedule/fee-rule.

### P3 — Corporate-coverage build-out (the missing half)

1. **`legal_request`** — intake front door that converts+links to the downstream object.
2. **`legal_contract`** — the largest single build (OCA concepts, LGPL re-implementation): contract lifecycle,
   parties, version/amendment tree, recital/section/clause structure, contractual obligations materialised
   onto the deadline board, bond/penalty tracking per Instructions 2/2014.
3. **`legal_litigation`** — courts registry (18 governorates + SJC hierarchy), lawsuit, hearing (auto next-
   date + deadline), judgment + **statutory appeal-window engine** (10/15/30/7 days from tabligh, marked
   non-extendable) feeding the deadline board; required valid litigation POA.
4. **`legal_opinion`** — request→study→issue→freeze with register-number-on-issue and a searchable precedent
   library.
5. Extend `legal_correspondence` with origin links (m2o) to request/contract/lawsuit/opinion, mirroring how
   `legal_procedure` adds `case_id`.

### P4 — Polish & optional scope

1. Read-only ribbon for the auditor; localise the denial dialog; company-name truncation in the navbar.
2. Optional `legal_property` (real-estate transactions) and `legal_investigation` (committees under Law
   14/1991) reusing the hearing/session pattern and the confidential rule.
3. Deprecated-API sweep (`_check_recursion`→`_has_cycle`), dead SCSS/`.pyc`/empty-dir cleanup, kanban `color`
   wiring, unused config flags (`has_incoming_reply`/`has_result_document`/`requires_documents`) wired or
   dropped, secrecy grades (سري وشخصي, عاجل) + إضبارة reference on correspondence, POA typing.
4. Silence irrelevant stock crons; trim Enterprise-store noise from the admin Apps view; drop Technical
   Features from the officer role.

---

## 3. Target architecture — one recommendation

### 3.1 Module layout

**Keep all nine existing modules as the foundation** — they are the spine, not the problem. The redesign is
four new domain modules + one unification module + one reports module + a suite-wide i18n pass. The procedure
engine (`legal.case`) **stays the host for government transactions only** (المعاملات); requests, contracts,
lawsuits and opinions are *siblings* that reuse its mixins, security ladder, correspondence integration and
dashboard composer — never tenants inside it.

| Module | Status | Models / content |
|---|---|---|
| `legal_core` | **keep + refactor** | activate IQD; `company_id`+rules on signatory/identifier/contact; `entity_id` restrict; expiry cron; supersession guards; expiry tracking; `res.config.settings`; search views; add `legal.entity.resolution` + capital-change lines; i18n |
| `legal_correspondence` | **keep + refactor** | lock state transitions; internal sentinel; gap/continuity report; `active` guard; idempotent `_after_registration`; origin m2o to new objects; secrecy grades; i18n |
| `legal_procedure` | **keep + refactor** | thread-local write-guard; lock `procedure_type_id`; reopen reason wizard; `sudo` result-document; wire the OWL rail/checklist/walk (grow payload fields); full-domain tile arithmetic; dashboard error states; auditor menu access; manager/approver/auditor bands; Python tests; i18n |
| `legal_iq_*` (5 packs) | **keep + extend** | populate transition `group_ids`; add `verification_status` where disputed; 2025–2027 calendars; seed court bodies + 18 governorates; copy purity test to all packs |
| `legal_iq_demo` | **keep + fix** | IQD; real per-role queues; group-gated transitions; seeded POAs/fees/SLA; install-relative dates; password-reset guard |
| `legal_request` | **new (P3)** | `legal.request` (+ category) — intake/triage/convert |
| `legal_contract` | **new (P3)** | `legal.contract`, `.type`, `.party`, `.clause`/`.section`/`.recital`/`.appendix`, `.obligation`, version tree, modification log |
| `legal_litigation` | **new (P3)** | `legal.court` (+degree, governorate, parent), `legal.lawsuit`, `legal.hearing`, `legal.judgment`, appeal-window engine; seed governorates + court network |
| `legal_opinion` | **new (P3)** | `legal.opinion` (snapshot-freeze + register-number issue + supersede chain) |
| `legal_deadline` | **new (P2)** | `legal.deadline` (`_auto=False` union) + digest cron + `_deadline_sources()` hook |
| `legal_reports` | **new (P2)** | QWeb prints + pivot/graph views + date-range wizards |
| optional `legal_property`, `legal_investigation` | **new (P4)** | registers + session rows reusing the hearing pattern |

### 3.2 Model list (new + notable extensions)

- **Intake:** `legal.request` (+`legal.request.category`).
- **Contracts:** `legal.contract`, `legal.contract.type`, `legal.contract.party`, `legal.contract.clause`,
  `legal.contract.section`, `legal.contract.recital`, `legal.contract.appendix`, `legal.contract.obligation`,
  `legal.contract.modification`.
- **Litigation:** `legal.court`, `legal.lawsuit`, `legal.hearing`, `legal.judgment` (appeal-window engine on
  the judgment); seed rows: 18 governorate `legal.jurisdiction`, court network as `legal.gov.body` type COURT.
- **Opinions:** `legal.opinion`.
- **Deadlines:** `legal.deadline` (`_auto=False` union view).
- **Corporate records extension:** `legal.entity.resolution` + capital-change lines on `legal.entity`.
- **Reuse everywhere:** `legal.expiry.mixin`, `mail.thread`, `mail.activity.mixin`, the 5-group ladder +
  auditor row + company rule + (where sensitive) the confidential rule, the snapshot-freeze pattern, the
  obligation-instance generation pattern, the per-body record-rule pattern, `legal.signatory`, the register.

### 3.3 Arabic menu tree (target)

```
الشؤون القانونية
├── لوحتي (مكتبي حسب الدور: كاتب/متابع/مصادِق/مدير/مدقّق)
├── غرفة البريد                    (الصادر/الوارد — لوحة)
├── الطلبات القانونية              legal.request            ← جديد
├── المعاملات الحكومية             legal.case (ملفاتي، المتأخرة، الوثائق المعرقلة)
├── العقود                         ← جديد
│   ├── العقود
│   ├── الالتزامات التعاقدية
│   └── أنواع العقود               (إعدادات)
├── الدعاوى والقضايا               ← جديد
│   ├── الدعاوى
│   ├── جلسات المرافعة
│   ├── الأحكام والطعون
│   └── سجل المحاكم                (بداءة/استئناف/تمييز/عمل/جنح وجنايات/قضاء إداري × المحافظات)
├── الآراء والاستشارات             ← جديد (قيد الإعداد / الصادرة المجمّدة)
├── سجل الصادر والوارد             (الموجود — أُعيدت تسميته وتوحيد لغته)
├── السجلات
│   ├── وثائق الشركة، تجديدات مستحقة، الكيانات، الجهات الحكومية
│   ├── الوكالات والتخويلات        legal.poa (+ طباعة تخويل)
│   └── العقارات                   (اختياري)
├── المواعيد والالتزامات           ← موحّد جديد
│   ├── لوحة المواعيد الموحدة       (رزنامة + قائمة)
│   ├── الالتزامات الدورية
│   └── التصعيدات
├── التقارير                       ← جديد (دفتر السجل، ملف معاملة، موقف الدعاوى/العقود، الالتزام، الرسوم)
└── الإعدادات                      (config-as-data + لوحة إعدادات عامة)
```

Rules for the tree: one action per menu (kill the duplicate Mail Room / Procedures / Government-Bodies
mounts), single-language Arabic labels resolved through `ar.po`, config strictly separated from registers,
and a scroll-capped Configuration dropdown.

### 3.4 Keep / refactor / drop — the existing engine & OWL suite

**KEEP (verbatim or near):**
- The data-driven procedure engine thesis (states are rows), the **immutable action log** (unconditional
  write/unlink raise, no `create` ACL, denormalised snapshots), **cron idempotency by unique index**, live
  SLA verdict with stored deadline, version snapshotting + hand-remapped graph copy, the graph validator.
- The **5-role ladder with implied groups** + the **server-verified read-only auditor**, per-body visibility
  as data (`officer_ids`) traversed by record rules, the confidential rules, the narrow legitimate `sudo()`s.
- The correspondence **void-not-delete** design, editable-sequence mixin, year-reset, frozen snapshots, the
  QWeb official letter structure (العدد/التاريخ block, signature+seal stack, نسخة منه إلى, Hijri/numeral
  localisation) and the paperformat pair.
- The **OWL architecture**: single-RPC server-composed payloads, registry usage, bookmarkable client actions,
  and the **exemplary RTL SCSS** (logical properties, Tajawal from Odoo's own files, pinned `dir="ltr"`
  numerals, visually-hidden status words) — this is the template for all new OWL work.
- The five **content packs** (39 bodies, 52 doc types, 23 procedures, 19 schedules, 24 IQD fee rules) with
  their provenance discipline — the strongest existing asset.

**REFACTOR:**
- The two write-guards (context flag → thread-local token); `procedure_type_id` (lock after create); reopen
  (add reason); the correspondence state lock; supersession (date/owner); the dashboard tiles (full-domain);
  add dashboard error states + auditor access + manager/approver/auditor bands; grow the `legal.case` payload
  fields so the **already-built rail/checklist/counter-walk mount** instead of shipping dead.
- The whole label layer → single-language + `ar.po` (the biggest single refactor by surface area).
- Menus, forms, lists, search per §2.P2.

**DROP:**
- The AI-Studio mock in its entirety (React SPA, the substandard **module-code exporter**, client-side
  "roles", `Math.random()` numbers, fake Enterprise branding) — **port its *concepts* only** (KPI→filtered-
  action drill-through, suite-wide expiry countdown badges, صادر/وارد as first-class card content, the
  official-letter presentation, phase-coloured form sections, per-state colour tokens).
- `legal_backend.scss`'s dead `.o_legal_stale`; the orphan `_debug_reflect.cpython-311.pyc`; empty
  `report/`/`wizard/`/`tests/` dirs; the dead `no_gap` `ir.sequence` in correspondence; `jurisdiction.
  company_ids` if not enforced; the `LegalChart` component only if the manager Performance screen is not
  built (otherwise wire it — it is the best component in the suite).
- **Do not port any OCA `agreement`/`contract` code verbatim** (all AGPL-3; suite is LGPL-3) — adopt the
  schema/lifecycle/date-math *behaviour* and re-implement Arabic-first under LGPL-3.

---

## 4. Appendix — evidence density & confidence

- **Unanimous, live-reproduced (highest confidence):** kanban crash (all 6 browser walks + verified line);
  no `i18n/` anywhere (disk + SQL: 0/164 menus, 0/157 actions in `ar_001`); IQD inactive + company USD (SQL +
  Settings screen); missing five domains (schema + pack data); five roles run `ar_001` (SQL).
- **Read-verified in source (high confidence):** write-guard context bypass (`legal_case.py:902-921` +
  `service/model.py:88-90`); correspondence state-flip/context bypass (`legal_correspondence.py:750-812`);
  signatory/identifier/contact unscoped (no `company_id`, absent from rules file); `entity_id ondelete=
  cascade`; empty transition `group_ids` (SQL: 0 rows in the rel table) with a clerk offered a closing
  transition (live XML-RPC).
- **Environment fact (verify on target host):** wkhtmltopdf absent on *this* machine — re-check on the
  deployment host before treating as a permanent P0.
- **Corrected during synthesis:** browser_admin's "officer/approver hit ACL walls" — refuted by the
  `implied_ids` ladder + the officer/approver walks; only `admin` is truly locked out.
