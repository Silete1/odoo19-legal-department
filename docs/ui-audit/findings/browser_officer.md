# Browser UI/UX + RTL Audit — Follow-up Officer (officer@legal.iq)

**KEY:** browser_officer · **Date:** 2026-08-31 · **Instance:** http://localhost:8090 db=legal_dept
**User:** officer@legal.iq (uid 16), lang `ar_001`, TZ Asia/Baghdad, groups: Role/User, Clerk, **Follow-up Officer**, Technical Features
**Viewports:** 1366x768 full walk + 1920x1080 re-shoots · **Evidence:** `docs/ui-audit/before/officer__*.png` (34 screenshots) + JS console log (officer_events.jsonl in scratchpad, summarized here)

## Summary

The follow-up officer's question — *"my files, my deadlines, what am I chasing, what needs action today"* — **is not answered at login and cannot be fully answered at all right now**:

1. **Login lands in Discuss**, an empty chat screen, because the officer has no home action and Discuss is the first app. The purpose-built My Desk OWL screen (which answers the officer's question *well* — hero count, "needs your action" worklist with two ages per file, per-body desks with counter hours) is two clicks away behind an app switcher entry that is itself named in English.
2. **The two menu entries that list the officer's files crash.** *Operations → Files* and *Operations → My Files* both die with an OWL error dialog ("عذراً! حدث خطأ ما…") at every viewport. Root cause captured from the browser: the `legal.case` kanban `<progressbar>` `colors` attribute is a single-quoted Python dict, and Odoo 19's `KanbanArchParser` does a strict `JSON.parse` on it. One attribute breaks the entire case worklist. The same action forced to `?view_type=list` renders fine.
3. **The Arabic-first requirement is unmet at the string level.** The database has ZERO `ar_001` translations for all 164 menus, and no `legal_*` module ships an `i18n/` directory. Every screen is a bilingual collage: Arabic data and core-Odoo chrome vs. English module labels, buttons, column headers, filters, empty states and OWL dashboard strings. Where the module hard-codes bilingual "عربي - English" labels, narrow list columns truncate them into garbage ("مسجل - d…", "صادر - ing…", "…t Started").
4. RTL direction itself is mostly right (dialogs, dropdowns, group rows, statusbar all mirror correctly; no horizontal page overflow was measured on any screen), but **bidi text handling is broken wherever English sentences meet RTL containers**: scrambled empty-state text on Powers of Attorney, leading periods (".Two ages…"), and LTR reference numbers truncated from the *left* so every file shows as "…2026/0001", hiding exactly the part that distinguishes files.

Positives worth keeping: the My Desk / Mail Room information design is genuinely strong (counts that are buttons, two ages per row, per-body counter hours and notes, honest degraded-mode notices); the data model on screen is rich (SLA chips, blocking documents, rounds, counter walk); dense list layouts avoid wasted space.

Against the target spec, the officer's menu has **no litigation/hearings/courts registry, no legal opinions/consultations, no contracts+obligations register (beyond compliance schedules), no legal request intake queue** — the app today covers correspondence, procedure files, documents, entities, bodies, POA and fees only.

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Operations → Files / My Files | OWL crash dialog on open; 6 JS console errors during walk | `progressbar colors="{'on_track': 'success', …}"` is not JSON → `KanbanArchParser` throws; default kanban view of `legal.case` unrenderable; officer worklist menus dead | **critical** | Valid JSON (double quotes) in `legal_procedure/views/legal_case_views.xml:348-349`; smoke-test every action per role |
| 2 | Login landing | Officer lands in Discuss (empty chat, "لم يتم تحديد محادثة.") | Product does not answer "what needs action today" at login; res_users.action_id is NULL, Legal app sequence loses to Discuss | **high** | Default home action = My Desk (`legal_procedure.action_legal_desk`) for all legal roles; Legal app first in app order |
| 3 | Whole UI, Arabic user | 0/164 menus translated; no i18n/ dir in any legal_* module; all labels/buttons/headers/OWL strings English | Arabic-first RTL product renders as English UI with Arabic data; violates core spec | **high** | Ship complete `ar.po` for all modules (menus, views, OWL `_t()`, selection values, empty states) |
| 4 | List columns, bilingual labels | Hard-coded "عربي - English" values/labels truncate: "مسجل - d…", "صادر - ing…", "الجهة - t Body…", "…t Started" | The visible fragment is meaningless in both languages; state/direction columns unreadable | **high** | Single-language labels via translations, not concatenated bilingual strings |
| 5 | RTL bidi composition | POA empty state renders "before somebody needs it وكالة Record the"; ".Two ages…", banner "has not been provided. (and 1 more) …" | English strings inside RTL containers without dir isolation scramble word order and punctuation | **high** | Translate the strings; where mixed text is unavoidable use `dir="auto"` / bidi-isolate spans |
| 6 | Files list, File Number column | Every row shows "…2026/0001" (prefix clipped) | LTR reference truncated from the left in RTL context hides GCT-CLR/RES/VISA prefix — files indistinguishable | **high** | `dir=ltr` + ellipsis on the correct side for reference columns; widen column |
| 7 | My Desk worklist SLA chips | Chips clipped: "king day(s) Waiting on us", "day(s) With إقامة بغداد" (also at 1920x1080) | The working-days age — the officer's core deadline datum — is cut off | **high** | Fix chip min-width/overflow in `legal_worklist` SCSS; put the number outside the truncating span |
| 8 | Target-spec coverage | Menu = correspondence, files, documents, entities, bodies, POA, fees | No litigation/hearings/courts registry, no opinions/consultations, no contracts register, no request intake queue in officer's reach | **high** | Build the missing spec modules; wire them into Operations + My Desk |
| 9 | Empty states | Overdue/Escalations: stock smiley + "إنشاء مستند جديد"; Fees Paid: blank grey rows, nothing at all | Generic "create new document" is wrong and gives zero guidance; Fees Paid looks broken | medium | Per-view `help` with role-relevant Arabic guidance ("لا توجد ملفات متأخرة اليوم…") |
| 10 | Menu labels in source | "سجل الصادر والوارد / Correspondence Register", "صادر - Outgoing", "تسجيل كتاب وارد" beside English siblings | Three naming conventions in one menu tree; bilingual slash labels overflow app switcher | medium | Single-language menu names + translations |
| 11 | Search filters/group-by | One panel mixes English (Outstanding, Late, Registered, My Entries) and Arabic (بانتظار الرد، مجاب، سري) items | Filter vocabulary incoherent; group-bys all English | medium | Translate all filter/group labels; officer-first defaults (my files, due this week) |
| 12 | Apps + Technical Features for officer | Officer sees Apps app (58 install cards) and holds "Technical Features" group | Menu noise + needless technical surface for a business role (install itself is blocked → not critical) | medium | Drop Technical Features from role groups; hide Apps from non-admins |
| 13 | Compliance Calendar | "Open The File" English button ×41 rows; Obligation/For/Body/State columns all truncated | Key columns unreadable; repeated English CTA noise on Arabic screen | medium | Icon-only row action with tooltip; column priorities; translated State badges |
| 14 | Case form | Buttons "Return For Correction / Record This Step / Blocked", sections "WHO AND WHEN", banner bidi-broken; phantom empty grey rows in COUNTER WALK / Fees Paid lists | Workflow verbs untranslated at the exact point of action; disabled "Blocked" unexplained; sloppy empty-row rendering | medium | Translate; tooltip on disabled state; fix empty inner-list rendering |
| 15 | Register-incoming wizard | Labels "Their - رقم كتابهم Number", "تاريخ التسجيل - Received On" wrap mid-phrase | Bilingual label experiment breaks in RTL dialog layout; intake form is the highest-frequency task | medium | Single-language labels; keep the good Arabic placeholders |
| 16 | Duplicate menu names | Top-level "Mail Room" (OWL) + Registers → Correspondence → "Mail Room" (list); "My Desk" vs "My Files" | Same name, different screens; users can't tell which is which | medium | Distinct names (e.g. غرفة البريد vs سجل الوارد) |
| 17 | Breadcrumb/title duplication | "The Mail Room" and "My Desk" appear twice within 60px (control panel + band header); tab titles English | Wasted vertical space, giant double heading; English browser-tab titles for Arabic users | low | Suppress in-page band title when breadcrumb shows it; translate action names |
| 18 | Currency display | Entity Capital "750,000,000.00" bare | IQD-first spec: no currency symbol/code on money fields seen | low | `widget="monetary"` with IQD everywhere |
| 19 | Truncated header labels | "…cuments", "…cial Year End", "…tion Status", "…ult Responsible", "…rt Renewal By", "…emaining" | Headers clipped mid-word from the left in RTL; several columns unidentifiable | low | Shorter Arabic headers; `optional` columns; min-widths |
| 20 | Tooltips over data | Black tooltip overlapping adjacent cells (incoming list, entities, bodies) | Cosmetic occlusion during scans | low | Standard delay/offset; verify RTL placement |

## Detailed notes

### 1. The crash that removes the officer's worklist (critical)

- Repro: login as officer → Legal → Operations → Files (or My Files). Error dialog "عذراً! حدث خطأ ما…" every time; behind it an empty white content area. Screenshots: `officer__05_files_list.png`, `officer__07_my_files_list.png`, `officer__32_fhd_files_list.png`, `officer__33_fhd_file_form.png`.
- Console (captured 6×, identical): `OwlError … Caused by: SyntaxError: Expected property name or '}' in JSON at position 1 … at KanbanArchParser.parseProgressBar … View.loadView`.
- Source: `custom_addons/legal_procedure/views/legal_case_views.xml:348-349`:
  `<progressbar field="sla_state" colors="{'on_track': 'success', 'warning': 'warning', 'overdue': 'danger', 'escalated': 'danger'}"/>` — single quotes = not JSON. Odoo 19 core kanban progressbars use double-quoted JSON.
- The action itself is healthy: `/odoo/action-527?view_type=list` renders a good dense list (`officer__05c_files_forced_list.png`), and a direct record URL `/odoo/action-527/438` opens the form (`officer__06_file_form.png`). Fix is one attribute.
- Because the desk worklist rows and hero counts *also* route into these actions ("Open all my files"), the crash is reachable from the one screen that works.

### 2. Landing (high)

`officer__01_landing_after_login.png`: Discuss, empty, "لم يتم تحديد محادثة.". App switcher (`officer__02_apps_dropdown.png`): three entries — Discuss / Legal / Apps, all English. SQL: `res_users.action_id IS NULL` for uid 16. The Legal app internally lands on Mail Room (menu sequence), which suits the clerk; the *officer's* natural landing is My Desk (`officer__04_legal_mydesk_owl.png`) — which is well designed: hero "Waiting for you 4 / urgent 2", worklist of exactly the officer's 4 open files with step chips, blocking-document notes, ages; tiles "Stalled over a fortnight 0", "With the body 3", "Expiring within 90 days 5"; then per-body desks with counter hours ("٨:٠٠ - ١٤:٠٠، عطلة الجمعة والسبت"). All of its labels are English (`Needs your action`, `Your desk`, `Follow-up Officer`, `Counter notes`, `Nothing outstanding`, `Waiting to be sent`…) — the payload comes from `legal.dashboard.get_desk_data` whose `_t()` strings have no Arabic catalog to translate into.

### 3. Translation state (high)

- SQL: `select count(*) from ir_ui_menu where name ? 'ar_001'` → **0** (of 164). Action names likewise en_US-only.
- No `i18n/` folder in any of legal_core, legal_correspondence, legal_procedure, legal_iq_* (checked on disk).
- Effect on every screenshot: core Odoo is Arabic (search placeholder بحث…, chatter buttons إرسال رسالة/ملاحظة/النشاط, جديد button, error dialog), module content is English. Examples per screen: list headers `Due On, Responsible, At Counter, Sitting With, Step, Procedure` (05c/08); form sections `OUR REGISTER / THEIR REFERENCE / THE BODY / HAND-OFF` (15/17), `WHAT IT IS / VALIDITY` (21), `REGISTRATION / OBLIGATION CLOCKS` + tabs `Activity & Address / Authorised Signatories / Our Numbers At Each Body` (24); statusbar values `Registered - مسجل / Draft - مسودة` (15), `In Force / Superseded` (21); buttons `Attach Filed PDF / Void - إلغاء / Next In Thread` (15), `Return For Correction / Record This Step / Blocked` (06).

### 4-7. RTL and truncation specifics

- **Bilingual value truncation** (`officer__14_corr_outgoing_list.png`, `officer__16_corr_incoming_list.png`): State column renders "مسجل - d…" (from "مسجل - Registered"), Direction "صادر - ing…", Reply badges "Late - متأخر" fit only sometimes; header "الجهة - t Body…" is a clipped "Government Body". Compliance state "…t Started" (from "Not Started", `officer__10_compliance_calendar.png`).
- **Bidi scrambling** (`officer__26_poa_list.png`): custom help text renders as "**before somebody needs it وكالة Record the**" + body paragraph ending "**.rather than on the pavement outside the ministry**" — the intended sentence is destroyed by RTL reordering. Same class of bug: ".Two ages: at this step…" on My Desk (04/31), "has not been provided. (and N more)" blocker banners on desk rows and the case form warning ribbon (06).
- **Reference clipping** (`officer__05c_files_forced_list.png`): File Number column shows "…2026/0001" on all five rows — GCT-CLR/GCT-RET/RES/VISA/MOT-ADR prefixes hidden. The breadcrumb shows "GCT-CLR/2026/0001" fine on the form, so it is a column-width + LTR-in-RTL ellipsis-side problem.
- **Desk chips** (`officer__04`, confirmed at FHD in `officer__31`): "48 working day(s)" clipped to "king day(s)", "…day(s)" — element width, not viewport.
- Direction fundamentals are OK: `officer__29_operations_dropdown.png` (dropdown anchored correctly, items right-aligned), `officer__13_corr_register_wizard.png` (RTL dialog, footer buttons on the correct side), group rows right-aligned with counts (12/18/22), statusbar mirrored (06/15/21). Page-level metrics: no screen had `scrollWidth > clientWidth` at 1366x768.

### 8. Scope vs target spec (high)

Officer-visible tree (browser-verified): Legal → {Mail Room, My Desk, Operations{Files✗, My Files✗, Overdue, Blocking Documents, Compliance Calendar, Escalations}, Registers{Correspondence(6 items), Company Documents, Renewals Due, Legal Entities, Government Bodies, Powers Of Attorney, Fees Paid}}. Nothing for: court cases/hearings/courts registry, legal opinions/consultations, contract lifecycle, request intake, or a unified deadlines view across sources (deadlines live separately in Overdue + Renewals Due + Compliance Calendar + Reply Due).

### 9-16. Operational UX notes

- Overdue and Escalations empty states are the stock "إنشاء مستند جديد" smiley (`officer__08`, `officer__11`) — for a *legal* app the wording is wrong and there is no "nothing overdue today" reassurance; Fees Paid (`officer__28`) draws header + four blank stripe rows and no message at all (same phantom-row rendering inside the case form's COUNTER WALK tab, `officer__06b`).
- Apps app fully browsable by officer (`officer__34_apps_menu_visible.png`, 58 cards, Request Access buttons); "Update Apps List / Apply Scheduled Upgrades / Import Module" also in that tree. Officer additionally holds group 7 "Technical Features". Install is gated (Request Access), so hygiene rather than a breach.
- Register wizard (`officer__13`) is otherwise the best intake surface (good Arabic placeholders like "ك/م/١٢٣٤", "تقدير ضريبي لسنة ٢٠٢٥") — label strategy is its only real flaw.
- Duplicate names: two "Mail Room" menus (client action 532 vs list action 169) — first-click ambiguity for a new user.
- Correspondence forms (`officer__15/17`) are clean and dense; chips/threading (Round, In Reply To, Next In Thread) are strong; only language/labels betray them.
- Gov bodies register (`officer__25`) is rich (39 bodies, hours, channels, verification badges) — a real courts registry could follow this exact pattern.

### JS console summary

6 errors total in the full walk — all the same OwlError/JSON.parse kanban crash from actions 527/529 (screen attribution in the log is shifted one screen late because errors fire during navigation). No other page errors; no warnings of note. My Desk, Mail Room OWL, and all correspondence/register screens are JS-clean.

### What good looks like here (for the redesign)

Open on My Desk in Arabic; one worklist that merges files, replies due, compliance items and renewals with a single "due" ordering; the Files kanban fixed and grouped by step with SLA progressbar; every string from one ar.po; reference numbers rendered `dir=ltr` whole; empty states that state the register's meaning and the happy case.
