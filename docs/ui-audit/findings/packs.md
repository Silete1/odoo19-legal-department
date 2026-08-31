# Audit — Iraq content packs & demo (KEY=packs)

Scope: `legal_iq_registrar`, `legal_iq_tax`, `legal_iq_chamber`, `legal_iq_social_security`,
`legal_iq_residency` (data packs) and `legal_iq_demo` (worked company, users, files).
Verified against the running `legal_dept` database (read-only SQL) on 2026-08-31.
All six modules are in state `installed`.

## Summary

The five content packs are the strongest part of the current suite: pure-data modules
(no models, no security objects) seeding 39 government bodies, 52 document types,
23 procedure types with 123 steps / 30 transitions, 19 obligation schedules, 24 fee
rules (all IQD), 5 working calendars and provenance (`legal_basis`, `legal_basis_url`,
`last_verified_on`) on nearly every record. Disputed figures are honestly documented
in Arabic notes (PSSO monthly deadline, Chamber fees). The demo pack delivers an
Arabic-first, plausible Baghdad company with five role users, a six-case pipeline in
different stages, a 14-entry correspondence register with real صادر/وارد numbers, a
telephone contact note, an unprompted incoming letter, and a document register that
deliberately contains an expired, an expiring and three restricted items — the demo
spec's "not uniformly green" requirement is genuinely met.

The failures are: **the company currency is USD and IQD is inactive** (every monetary
display contradicts the Iraqi story the data tells); **the approver logs into an empty
landing band** (no case pends approval, no transition requires a group — the "meaningful
queue for every role" spec fails for approver, and manager/auditor own no records);
the machine-readable `verification_status` flag exists **only on bodies**, so the
disputed fee/deadline figures the manifests boast about are flagged in free text only;
calendars ship 2026-only holidays while obligation instances already run to Aug-2027;
every demo date is a static literal that rots within weeks; and the flagship "stuck at
the Tax Commission since April" file shows ~0 days at step because the action log
(correctly) refuses seeded history. Finally, the demo structurally cannot show
litigation/hearings/courts, contracts lifecycle, opinions, or request intake — those
models do not exist, no court body is seeded anywhere, and the POA/fee registers are
empty (0 rows each).

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Currency | `res.company` currency = USD; `res_currency` IQD `active=False`; all 24 `legal.fee.rule` rows reference IQD via `base.IQD`; `legal.case.contract_value` uses company currency | Iraqi legal dept demo prices everything in dollars; fee amounts render against an inactive currency; spec demands IQD | critical | Activate IQD, set it as company currency in `demo_company.xml` (or a base pack), add an IQD rate; keep fee rules on IQD |
| 2 | Role queues | 6 demo cases: 4 → officer, 2 → clerk; `pending_group_id` NULL on all; 0 rows in `legal_procedure_transition_res_groups_rel`; approver landing band = "approvals" (`legal_dashboard.py:1415`) | Approver logs into an empty screen; manager and auditor own zero records — "meaningful queue for EVERY role" fails | high | Seed at least one case awaiting approval (pending_group), one manager-assigned file, and give packs approval-gated transitions |
| 3 | Demo coverage | No models/tables for litigation, hearings, contracts, opinions, request intake; body type "محكمة" exists with **zero** court bodies seeded; `legal_poa` 0 rows, `legal_fee` 0 rows, `legal_sla_rule` 0 rows | Half the client spec cannot be demonstrated at all; courts registry is an empty type; POA/fee/SLA screens open blank | high | Build the missing models (other work-streams), then extend packs: courts registry pack, POA records, worked fees, SLA rules |
| 4 | Verification flags | `verification_status` field exists only on `legal.gov.body` (`legal_gov_body.py:186`); DB: 35 verified / 3 stale / 1 not_researched; schedules & fee rules have only `last_verified_on` + free-text notes | Disputed figures (Chamber fee 131,751 vs 500,000; PSSO monthly deadline) are not machine-filterable; manifest claims "shipped with verification_status='stale'" for figures — no such field on those models | high | Add `verification_status` to `legal.obligation.schedule` and `legal.fee.rule`; surface a "needs re-check" board |
| 5 | Calendars | 5 calendars × 11 national closures, all dated 2026 only (`registrar_calendar.xml:39-117` and 4 copies); obligation instances generated to 2027-08-31 | Working-day arithmetic in 2025/2027 sees no holidays; Christmas Day (official Iraqi holiday) missing; `noupdate="1"` means a pack bump won't refresh estimated Eid dates | medium | Ship 2025–2027 closures incl. 25 Dec; provide a maintained-holidays mechanism instead of 5 duplicated noupdate sets |
| 6 | Demo date rot | Every date is a static literal anchored to Aug-2026 (expired Mar-2026, expiring 20-Sep-2026, deadlines 18-Aug/15-Sep-2026) | Perfect today; by Nov-2026 the "expiring within the month" story is gone, by 2027 everything is expired — demo decays with no refresh path (`noupdate="1"`) | medium | Compute demo dates relative to install day (`eval` with `DateTime.today()` offsets) for the state-machine records |
| 7 | Stuck-file story | All 19 `legal_action_log` rows created at install (2026-08-30 23:08); `stage_entered_on` reads install time | The flagship "at the Tax Commission since April, round 2, three chases" case shows ~0 working days at step on the ageing meter — the demo's own headline narrative is contradicted on screen | medium | Either let the desk fall back to `date_open`/letter dates for age when the log is single-entry, or accept & script the demo around it |
| 8 | Restricted items | 3 confidential docs; rule `legal_core_rules.xml:47` shows them only to issuing-body officers; passport (`demo_documents.xml:270`) has **no issuing body**, work-permit body has no `officer_ids` | The officer running the residency-renewal case cannot open the passport or work permit of her own subject; restriction demo works, workflow demo breaks | medium | Give per-person docs an issuing body whose officers include the responsible officer, or add an entity/case-based visibility leg |
| 9 | Obligations queue | 19 schedules → 41 instances auto-generated (crons live), 7 already past due, **all** `not_started`; instance has no responsible user field | First-morning demo may show a clean obligations board (mark-late cron runs 22:45); ownership only inferable via body `default_user_id` | medium | Run/mark late at install or on dashboard read; consider a responsible-user field on the instance |
| 10 | Pack purity claim | Only `legal_iq_registrar/tests/test_pack_purity.py` exists; tax/chamber/psso/residency have no tests directory | Every manifest makes the same falsifiable "data only" claim; it is enforced for 1 pack of 5 | medium | Copy the purity test to all packs (or hoist it to a shared test that iterates over installed `legal_iq_*` modules) |
| 11 | Demo credentials | 5 users, password `Legal#2026` in plaintext (`demo_users.xml:21` etc.); records load from `data/`, not `demo/` | Anyone installing `legal_iq_demo` on a real database gets 5 known-password internal users; the manifest documents the choice but nothing warns at install | medium | Keep data-loading, but force a password reset / expire the passwords, or gate on a config flag |
| 12 | Municipal placeholder | `body_amanat_baghdad` + municipal licence doctype shipped inside the demo pack (`demo_documents.xml:30`) marked `stale` | Content lives in the demo module; uninstalling the demo removes a body/doctype that real files may reference by then | low | Write `legal_iq_municipal`; demo keeps only the licence document instance |
| 13 | Letter templates | 4 professional Arabic templates, `show_qr=False` everywhere, str-substitution placeholders | None — deliberate and defensible (QR off until a verification route exists); flagged so redesign doesn't "fix" it | low | Turn QR on only with the public verification controller |
| 14 | Data accuracy | Spot-checked: return due 31 May (Law 113/1982), 10% cap 500k, WHT 15-day, PSSO Law 18/2023 (1%/mo from day 121, cap 100%, 30-day notification), Art 200 7-day, Reg 2/2017 8-month accounts as 243 days with caveat, KRG inversions noted, Eid dates labeled as estimates | No inaccuracies found in sampled figures; conflicts honestly documented in notes | low | Keep; connect notes to finding #4's machine-readable flag |

## Detailed notes

### What actually loaded (SQL, `ir_model_data` by module)

- `legal_iq_registrar`: 13 bodies, 20 doc types, 6 procedure types / 21 phases / 38 steps / 5 transitions, 22 doc requirements, 14 fee rules, 4 obligation schedules, 1 calendar + 11 leaves.
- `legal_iq_tax`: 10 bodies, 10 doc types, 6 procedure types / 21 phases / 32 steps / 10 transitions, **22 step checks** (the براءة الذمة counter-stamp round in `tax_clearance.xml`), 11 doc requirements, 4 fee rules, 4 schedules, calendar + 11 leaves.
- `legal_iq_chamber`: 3 bodies, 5 doc types, **4 licence grades**, 3 procedure types / 12 steps, 5 fee rules, 2 schedules, calendar + 11 leaves.
- `legal_iq_social_security`: 6 bodies, 6 doc types, 5 procedure types / 18 steps, 3 schedules, calendar + 11 leaves.
- `legal_iq_residency`: 6 bodies, 10 doc types, 3 procedure types / 23 steps / 11 transitions, **9 procedure fields**, 4 schedules, calendar + 11 leaves. The 13 visa states of the React prototype are present as steps (`residency_procedures.xml:107-372`).
- `legal_iq_demo`: 1 entity, 4 identifiers, 2 signatories, 5 users, 1 body + 1 doc type (municipal placeholder), 15 documents, 6 cases, 14 correspondence, 4 letter templates, 4 body contacts, 6 partners.

### 1. Currency (critical)

`SELECT c.name, cur.name FROM res_company c JOIN res_currency cur ...` →
`شركة الرافدين للتجارة والمقاولات العامة المحدودة | USD`. `res_currency` shows
`('USD', active=True), ('IQD', active=False)`. All 24 fee rules carry IQD (min 0 —
one intentionally zero-fee — max 500,000), via the default in
`legal_procedure/models/legal_fee_rule.py:66-71` (`base.IQD`, `raise_if_not_found=False`).
`demo_company.xml:24` renames the main company and sets letterhead but never touches
`currency_id`. Consequences: `legal.case.contract_value` (company-currency Monetary)
displays in $, list/kanban monetary widgets mix $ and an inactive IQD, and the client
spec's "IQD amounts" is unmet at the company level even though the *pack data* is
consistently IQD. The demo pack is the natural place to fix it (it already asserts
company-level fields).

### 2. Role queues at login (high)

- Cases by responsible: officer 4 (`GCT-CLR/2026/0001`, `GCT-RET/2026/0001`,
  `RES/2026/0001`, `VISA/2026/0001`), clerk 2 (`SSD-CLR` closed, `MOT-ADR` overdue).
- `pending_group_id` is NULL on all six; `legal_procedure_transition_res_groups_rel`
  has 0 rows — nothing in any pack demands an approver.
- `legal_dashboard.py:1415`: an approver (not manager) lands on the "approvals" band →
  empty screen with "Awaiting your approval" (`:940`) and nothing beneath.
- Manager: officer on 11 bodies (per-body desks populated) and sees everything, but
  owns no file. Auditor: read-only boards have content. Clerk: 1 open overdue file
  (good). Officer: the richest desk (good).
- The overdue item (case `MOT-ADR` deadline 2026-08-18; return case deadline
  2026-05-31 in round 2), the expiring item (municipal licence 2026-09-20, stored
  `expiry_state='expiring'` verified in DB) and restricted items (3 confidential docs)
  all exist — the per-role gap is specifically approver/manager ownership.

### 3. What the demo CANNOT show (models missing)

Confirmed against `information_schema.tables` (no `legal_litigation`, `legal_hearing`,
`legal_contract`, `legal_opinion`, `legal_request`, court-registry tables) and pack data:

- **Litigation / court cases / hearings** — no model; body type «محكمة» exists in
  `legal_core` but **no pack seeds a single court**; no hearings calendar.
- **Contracts + obligations lifecycle** — only `contract_value` on `legal.case`; no
  contract registry, no contractual-obligation records.
- **Legal opinions / consultations** — nothing.
- **Legal request intake** — no front-door request object; the mail room's caseless
  incoming letter (`corr_unprompted_assessment`) is the closest analogue.
- **Powers of attorney** — the engine model `legal.poa` exists but 0 rows are seeded;
  the demo has only a POA *document* (`doc_lawyer_poa`). The POA screen opens empty.
- **Fees** — `legal_fee` 0 rows despite `has_fee=required` procedures and 24 fee rules;
  no worked receipt/طابع in any demo case.
- **SLA rules** — `legal_sla_rule` 0 rows; `sla_due_on` NULL on every case, so the
  escalation cron ("Legal: deadline scan and escalation") has nothing to escalate.

### 4. Verification-status machinery (high)

`legal_gov_body.py:186-200` defines the three-state flag with an honest default
(`not_researched`). DB distribution: 35 verified, stale = `AMANAT-BGD` (demo municipal,
deliberate), `TRANSLATORS` (`registrar_bodies.xml:247`), `PSSO-CONTRIB`;
`GCT-KARRADA` not_researched (honest gap, `tax_bodies.xml`). Every body has
`last_verified_on=2026-08-30`. But `legal_obligation_schedule` and `legal_fee_rule`
columns (verified via information_schema) carry **no** `verification_status` — the
suite's most disputed figures live only in prose:

- `psso_obligations.xml:5` — monthly contribution due-date dispute (end of following
  month vs 15 days), shipped on the safer reading, flagged in the instruction HTML only.
- `chamber_procedures.xml:147` — registration fee 131,751 (MoT) vs "up to 500,000"
  (eRegulations); `:328` — 5,000 vs 125,000 for the Federation name letter, "غير مفسَّر".

A redesign that adds the flag to these two models makes the honesty filterable.

### 5–6. Calendars and date rot (medium)

All five calendars: Sun–Thu, correct per-body hours (Registrar 08:30–14:15, Chamber
Thu short-day 13:00). Identical 11 closures, **2026 only** (New Year, Army Day 6 Jan,
Eid al-Fitr 20–22 Mar est., Nowruz, Labour Day, Eid al-Adha 27–30 May est., Hijri New
Year, Ashura, 14 July, Mawlid, Victory Day 10 Dec). Missing: Christmas Day (25 Dec,
official since the 2018 amendment), any 2025 or 2027 rows — while `SSD-MONTHLY`/`GCT-WHT-MONTHLY`
instances already extend to 2027-08-31 and the annual-return case opened 2026-03-02.
The stated maintenance path ("corrected each year") conflicts with `noupdate="1"`.
Demo dates are all literals; the demo is at its narrative peak exactly this week
(installed 2026-08-30) and decays monotonically.

### 7. The action-log honesty problem (medium)

19 `legal_action_log` rows, all `create_date = 2026-08-30 23:08` (install). The pack's
own comments (`demo_cases.xml:8-17`) concede that "days at this step" reads install
day. For the client demo, the strongest story — `GCT-RET/2026/0001`, round 2, three
registered chases, phone note promising 2026-09-10 — shows a fresh ageing bar
(`AGE_STUCK_DAYS=14` never trips). The desk does show `since_open` (Mar-2026) beside
`at_step` (`legal_dashboard.py:_desk_row`), which partially rescues it, but the
"stuck" band and colour go off `at_step` only.

### 8. Confidential visibility (medium)

`legal_core_rules.xml:47-53`: clerk/officer/approver see a confidential document only
if they are in `issuing_body_id.officer_ids`; manager/auditor see everything (`:54-60`).
Demo: passport `AB4471902` (`demo_documents.xml:270`) has **no issuing body** →
invisible to every non-manager; work permit issued by the Labour department, which
gets no `officer_ids` in `demo_users.xml` → invisible to the officer who runs
`RES/2026/0001` for that same person. The residency permit (body
`residency_baghdad`, officer listed) is the only per-person doc she can open. Good for
demonstrating restriction (log in as clerk → 12 docs, not 15); bad for the workflow
narrative and arguably for real operations.

### 9. Obligation instances (medium)

Generator cron works: 41 instances spanning 2026-01-15 → 2027-08-31 across all 19
schedules, including document-driven ones (`DOC-113` = the expired tax clearance,
correctly due 2026-01-15, now 7 months overdue). All 41 are `not_started`; the
`_cron_mark_late` (`legal_obligation.py:503`) had not yet run at audit time (nextcall
2026-08-31 22:45 vs install 2026-08-30 23:08) — a morning demo shows no red "late"
column on the obligations board on day one. The instance model has no responsible-user
field; triage ownership exists only via `body_id.default_user_id`.

### 10–13. Smaller items

- **Purity tests**: only `legal_iq_registrar/tests/test_pack_purity.py` exists; the
  identical manifest claim in the other four packs is unenforced.
- **Passwords**: `Legal#2026` ×5 in `demo_users.xml` (`:21,36,...`); loads into any DB
  since the pack deliberately uses `data/` not `demo/`.
- **Demo images**: all four PNGs valid and generated (seal 520×520 — clean blue round
  seal with correct Arabic company name; two signature specimens; 400×400 letterhead
  emblem). Professional enough for the demo; nothing impersonates a real org.
- **Correspondence register**: 14 entries verified in DB, states all `registered`,
  numbers in proper Baghdad form (`ق/2026/0412` out, `و/2026/0188` in, their-numbers
  preserved verbatim), one internal phone note with `promised_on=2026-09-10` and no
  register number, one caseless incoming assessment with `reply_due_on=2026-08-06`
  (already overdue — a good mail-room alarm). Chases correctly modelled as one
  submission + three reminders + a return that incremented `round` to 2.
- **Users**: verified in DB — 5 users, correct single legal group each, `ar_001`,
  `Asia/Baghdad`, linked to signatories (approver = the MD who signs, manager = the
  deputy with body-scoped signing rights). Arabic names are realistic and consistent.

### Accuracy spot-checks (no defects found)

Annual return 31 May + 10%/500k cap (Law 113/1982); WHT remitted within 15 days of
following month + annual schedule 31 Mar; objection 21 days with pay-to-be-heard;
PSSO Law 18/2023 (fine 1–5M, 5× compensation, 1%/month from day 121 capped at 100%,
30-day notification under Arts 23/93); Companies Law 21/1997 Art 200 (7-day address
change, demo case filed day 6), Art 216 (100 IQD/day); foreign-branch accounts 8
months under Reg 2/2017 Art 8 shipped as 243 days **with** the non-calendar-FYE
caveat; work permit IQD 250,000 / KRG 110,000 with the federal-vs-KRG ordering
inversion named; Chamber grades as ordered `legal.licence.grade` records; electricity
bill modelled as `freshness` (60-day window) rather than expiry. Eid/Hijri dates are
plausible 1447–1448 AH astronomical estimates and every one is labelled «تقديري -
يحدد بالرؤية».
