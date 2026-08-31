# Browser UI/UX + RTL Audit — Clerk (كاتب) perspective (BEFORE state)

Audited as: `clerk@legal.iq` (مصطفى وليد إبراهيم), groups `base.group_user` + `legal_core.group_legal_clerk`
(demo_users.xml: `custom_addons/legal_iq_demo/data/demo_users.xml:18-32`), lang `ar_001`, tz Asia/Baghdad.
Server: http://localhost:8090, db `legal_dept`. Viewport 1366x768 (key screens re-shot at 1920x1080).
Evidence screenshots: `docs/ui-audit/before/clerk__*.png`.

## Summary

The clerk is the intake role — register incoming/outgoing letters, open files, keep the registers current.
The product has the right *skeleton* for that (a Mail Room dashboard with an "arrived today / awaiting reply"
queue, a numbered-register wizard `تسجيل كتاب وارد`, a My Desk with per-body counter notes) — but the seat is
broken and unfinished in four load-bearing ways:

1. **The case registry does not open at all.** Both `Operations > Files` and `My Files` crash with an
   OwlError for every user (malformed `progressbar colors` JSON in the `legal.case` kanban arch). The clerk
   who registers a letter and clicks "Open a new file" workflow cannot reach the files list.
2. **The Arabic-first requirement is unmet.** No `i18n/` directory exists in any `legal_*` module. The UI a
   clerk sees is majority hard-coded English (dashboards, column headers, statusbars, empty states, buttons,
   menus), with a "عربي - English" concatenated-label convention that truncates to garbage
   (`صادر - ing...`, `مسجل - d...`, `...ot Expire`) in every dense list, plus genuine bidi scrambling on the
   My Desk action card and the POA empty state.
3. **Access surface is wider than the role.** The Apps manager appears in the clerk's app switcher, and
   menu-hidden actions (procedure configuration, SLA escalations, the full Action Trail audit log, the Users
   list) all open read-only via direct `/odoo/action-<xmlid>` URLs — protection is menu-hiding plus ACL reads,
   with no `groups` on the actions and no trimmed landing experience. Writes are blocked by ACL, but the spec
   demands strict, deliberate server-side scoping.
4. **A data-quality trap sits on the main register.** On the `وارد - Incoming` list the visible `جديد` button
   opens a bare form whose Direction defaults to `صادر - Outgoing` (model default `out`, no
   `default_direction` in the action context), silently bypassing the numbering wizard.

Beyond that: the clerk lands in **Discuss** after login instead of the Legal workspace; two different screens
are both named "Mail Room"; grouped register lists open fully collapsed on a near-empty screen; empty states
are generic or misleading ("إنشاء مستند جديد" on the *Overdue* list); and none of the client-spec modules for
legal request intake, litigation/courts, legal opinions or contracts exist in this seat at all.

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Operations > Files / My Files | OwlError crash dialog "عذراً! حدث خطأ ما" (clerk__21, clerk__22) | `legal.case` kanban `progressbar colors` uses single-quoted pseudo-JSON; `KanbanArchParser.parseProgressBar` → `JSON.parse` throws; both menus dead for every role | critical | Double-quote the JSON (`colors='{"on_track": "success", ...}'`); regression-test every kanban arch attribute |
| 2 | Whole UI, ar_001 user | Dashboards, headers, buttons, statusbars, empty states, menus in English; no `i18n/` in any legal module | Arabic-first spec unmet; clerk works in a foreign language | high | Single-language Arabic source labels (or proper en source + complete `ar.po`); ship compiled translations; QA in ar_001 |
| 3 | All list views | Concatenated bilingual labels truncate: `صادر - ing...`, `مسجل - d...`, `...ot Expire`, `...t Started`, `...nt Body - الجهة` | Every register column reads as garbage at realistic widths | high | Drop the "عربي - English" concatenation convention; one language per label + translations |
| 4 | My Desk "Needs your action" card; POA empty state | Bidi scrambling: stray `12 0` numerals, clipped `q day(s)` chip, headline "before somebody needs it وكالة Record the", leading-period sentences ".Two ages…" (clerk__04, clerk__42, clerk__28) | Mixed LTR/RTL runs without isolation; broken at 1366 and 1920 | high | Arabic copy, and `dir`/bidi-isolate any Latin fragments; rebuild the card row layout for RTL |
| 5 | Login landing | Clerk lands on `/odoo/discuss` (clerk__01) | Intake user starts in chat, not the Mail Room; must find Legal by hand | high | Default the Legal app (Mail Room) as home action for legal roles |
| 6 | App switcher | "Apps" (base.menu_management) listed; opens 58-module Apps kanban (clerk__02, clerk__32) | Admin surface in the lowest role's switcher; menu group restriction not effective on this build | high | Restrict/verify Apps menu groups; clerk switcher should show Legal (+ Discuss at most) |
| 7 | Hidden actions via URL | `action_legal_procedure_type` (23 rows), `action_legal_sla_escalation`, `action_legal_action_log` (19 audit rows), `base.action_res_users` (6 users) all open read-only as clerk (clerk__34-37) | Defense-in-depth gap: config registers, the audit trail and the user list are one URL away; escalations list even shows a create-invite empty state though ACL denies create | high | Put `groups` on config/audit actions; decide deliberately what clerk may read; matching empty states |
| 8 | وارد - Incoming, `جديد` button | New form defaults Direction = `صادر - Outgoing` (clerk__08_new); model default `out` at `legal_correspondence.py:99-109` | Registering incoming mail via the visible button yields an outgoing draft and skips the numbering wizard | high | `default_direction` per action context, or route the list's New to the register wizard; hide the raw button for clerk |
| 9 | Client-spec coverage from clerk seat | Only correspondence, case files (broken), documents, POA, fees exist | No legal-request intake, no litigation/hearings/courts registry, no opinions/consultations, no contracts+obligations lifecycle, no unified deadlines view | high | Build the missing registries; give the clerk explicit intake queues for each |
| 10 | Legal menu tree | Two menus named "Mail Room" (dashboard action 532 and list action 169); naming mixes three conventions (English / Arabic / hybrid) | Clerk cannot tell which "Mail Room" is which; menu language inconsistent | medium | Unique Arabic menu names; one dashboard entry, one register entry |
| 11 | Mail Room / Awaiting Reply / Contact Notes / Renewals lists | Open grouped-by-body with all groups collapsed; 5–6 header rows on an empty 768px screen (clerk__05, clerk__12, clerk__13, clerk__16) | Clerk must expand every group to see any letter; wasted screen | medium | Expand groups by default (or default flat list sorted by date); denser rows |
| 12 | تسجيل كتاب وارد wizard | Half the field labels English: From Which Body, Section / Window, Kind, Register, Secrecy, Marked, Concerns, In Reply To, Scans (clerk__06) | The clerk's single most-used dialog is bilingual soup | medium | Full Arabic labels; group required intake fields first; keyboard-order tab flow |
| 13 | Empty states | Overdue and Escalations show generic "إنشاء مستند جديد"; Fees Paid shows blank stripes with no message (clerk__25, clerk__30); POA help is English + bidi-broken | Guidance absent or actively wrong (inviting creation on a filtered/readonly list) | medium | Per-view Arabic empty states explaining what feeds the list |
| 14 | Compliance Calendar list | Repeated "Open The File" link column, truncated `...t Started` badges, truncated penalty notes, English headers (clerk__27) | Width burned on a per-row button; states unreadable | medium | Row click opens the file; short state labels; Arabic headers |
| 15 | Forms (correspondence, document, entity, gov body) | ALL-CAPS English group titles (OUR REGISTER - سجلنا, HAND-OFF, WHAT IT IS, IDENTITY…), English tabs, superscript `?` markers on most labels, "In Thread 0" button floating detached in header, `Void - إلغاء` next to routine buttons (clerk__07_form, clerk__08_form, clerk__14_form, clerk__19_form) | Cluttered, half-translated, destructive action un-guarded visually | medium | Arabic group titles/tabs, help behind hover only, button box in standard position, danger styling + confirm on Void |
| 16 | Document Register list | "Days Left 0" for does-not-expire documents; truncated headers `...rt Renewal By`, `...ade / Class` (clerk__14) | Misleading zero reads as "expires today" | low | Blank Days Left when non-expiring; shorter headers |
| 17 | User menu / Discuss | "My Preferences", "Shortcuts CTRL+K", "حساب Odoo.com الخاص بي" mixed languages (clerk__33); Discuss menus English | Polish; stock strings untranslated because ar_001 base translations incomplete on build | low | Load base Arabic translations for stock apps |

## Detailed notes

### 1. Files / My Files crash (critical) — the intake-to-file workflow is severed
- Repro: as clerk open `Legal > Operations > Files` (action 527) or `My Files` (529). Both show the RTL
  error dialog; the action manager renders nothing. Same behaviour observed under other roles' probes, so it
  is not record-rule related.
- Console: `OwlError: An error occured in the owl lifecycle` caused by
  `SyntaxError: Expected property name or '}' in JSON at position 1 … at KanbanArchParser.parseProgressBar`.
- Root cause: `custom_addons/legal_procedure/views/legal_case_views.xml:348-349`:
  ```xml
  <progressbar field="sla_state"
               colors="{'on_track': 'success', 'warning': 'warning', 'overdue': 'danger', 'escalated': 'danger'}"/>
  ```
  Odoo 19 parses `colors` with `JSON.parse` (see `odoo-19.0/addons/web/static/src/views/kanban/kanban_arch_parser.js`),
  which requires double-quoted keys/strings. Single quotes throw.
- Impact for the clerk: the Mail Room's "Open a new file / Attach to a file" flow lands the clerk in a broken
  destination; "Open all my files" on My Desk likewise. The kanban also declares `quick_create="false"` — even
  once fixed there is no kanban quick-create path (defensible for a numbered registry, but then the New flow
  must be a guided wizard, see #8).
- Overdue (action 528) survives because it defaults to list view.

### 2–4. Language and RTL (high) — the Arabic-first spec is structurally unmet
- No `legal_*` module ships an `i18n/` folder (only `dma_accreditation`, `gov_hr_*` have one). Every label is
  hard-coded in source, most in English, some Arabic, many as hybrids.
- The hybrid convention is in the models themselves, e.g.
  `custom_addons/legal_correspondence/models/legal_correspondence.py:99-109`
  (`("out", "صادر - Outgoing")`), `:141` (`رقم كتابهم - Their Number`), `:160` (`Section / Window`); wizard:
  `custom_addons/legal_correspondence/wizard/legal_correspondence_register_wizard.py:38-40`.
  In list cells these truncate to `صادر - ing...` / `مسجل - d...` (clerk__07, clerk__08), and statusbars render
  `Registered - مسجل` (clerk__07_form). This convention cannot be fixed by translation files alone — labels must
  be single-language and translated properly.
- Real bidi failures (not just untranslated text):
  - My Desk "Needs your action" row (clerk__04 at 1366, clerk__42 at 1920): the SLA chip renders clipped
    (`q day(s)` / `y(s)`), bare numerals `12  0` and a progressbar detach to the far edge, LTR fragments
    interleave with the Arabic step name. The card row is unreadable at any width.
  - POA empty-state headline (clerk__28): source text "Record the وكالة before somebody needs it" renders as
    "before somebody needs it وكالة Record the".
  - English sentences in RTL containers show leading periods: ".Two ages on every row…",
    ".Nothing is marked urgent" (clerk__04), ".No letter is waiting to be written" (clerk__40).
- Menus mix three conventions in one tree: `Mail Room`, `تسجيل كتاب وارد`, `صادر - Outgoing`,
  `سجل الصادر والوارد / Correspondence Register` (menu dump; clerk__02). Breadcrums/window titles English
  ("The Mail Room", "Document Register", "Renewals Due").

### 5. Landing (high)
- After login the URL is `/odoo/discuss` (clerk__01). The webclient picks the first app; Discuss sorts before
  Legal. A clerk's day starts in the Mail Room — set `action_id` on the users or re-sequence the Legal root
  menu so it is the home app for legal roles.

### 6–7. Access surface (high)
- Clerk's app switcher: Discuss / Legal / **Apps** (clerk__02). Opening Apps (action 39) renders the full
  58-module kanban with Learn More / Request Access buttons (clerk__32). Install is blocked (non-admin
  community view) but the surface itself is admin territory and, worse, indicates the menu's group guard is
  not effective for `base.menu_management` on this build.
- Direct URL probes as clerk (all opened, read-only; clerk__34-37):
  - `legal_procedure.action_legal_procedure_type` → "Procedures" list, 23 config rows.
  - `legal_procedure.action_legal_sla_escalation` → "Escalations" with a create-inviting empty state
    ("إنشاء مستند جديد") although `ir.model.access.csv` gives clerk 1,0,0,0
    (`custom_addons/legal_procedure/security/ir.model.access.csv:29`).
  - `legal_procedure.action_legal_action_log` → "Action Trail", 19 audit rows readable. The CSV marks this
    "read only by design" (`:37`) — deliberate, but combined with unrestricted actions it hands the audit log
    to the lowest rung; worth an explicit product decision.
  - `base.action_res_users` → Users list, 6 users. Stock employee read on `res.users`, but nothing stops the
    navigation either.
- None of these actions carry `groups=`; the only shields are menu visibility and ACL write-denial. The spec's
  "strict server-side security" needs `groups` on actions plus curated read ACLs, so the *screens* themselves
  are role-scoped, not just the mutations.

### 8. Incoming "New" trap (high)
- On `وارد - Incoming` (action 171) the prominent `جديد` button opens the plain form: breadcrumb `draft -`,
  Direction pre-set `صادر - Outgoing` (clerk__08_new). Model default is `out`
  (`legal_correspondence.py:106`) and the Incoming action window passes no `default_direction`.
- The correct clerk path — the numbered wizard `تسجيل كتاب وارد` (menu 134 → action 174, clerk__06) with its
  "تسجيل ومنح الرقم" button — is a *sibling menu item*, so the visible New button on the register list is the
  wrong path with the wrong default. Either context-default the direction per list and mark Our Number
  "يُمنح عند التسجيل" (it already does), or make New on these lists launch the wizard.

### 9. Spec-gap from the clerk seat (high)
- The clerk's whole world is: Mail Room dashboard, My Desk, correspondence registers, Document Register,
  Renewals, Legal Entities (1 record), Government Bodies (39), Files (broken), Overdue, Blocking Documents,
  Compliance Calendar, POA (empty), Fees Paid (empty). Missing entirely versus the client spec: legal request
  intake (no request model/menu at all), litigation cases with hearings + a courts registry, legal
  opinions/consultations, a contracts register with obligations lifecycle, and a unified deadlines view
  (Compliance Calendar covers statutory obligations only). Intake for those workstreams has nowhere to land.

### 10–14. Operational UX (medium)
- Duplicate names: `legal_procedure/views/legal_dashboard_views.xml:39` creates top-level "Mail Room"
  (dashboard) while `legal_correspondence/views/legal_correspondence_menus.xml:19` creates
  Registers > سجل الصادر والوارد > "Mail Room" (list). Same label, different screens (clerk__03 vs clerk__05).
- Grouped lists open collapsed: Mail Room list (6 groups), Awaiting Reply (5), Contact Notes (1), Renewals
  Due (3) — the clerk sees only group headers on an otherwise blank screen (clerk__05/12/13/16). Blocking
  Documents likewise shows only Latin file codes as group headers (clerk__26).
- Compliance Calendar (clerk__27): per-row "Open The File" anchor column, `...t Started` truncated badges,
  truncated penalty text, English headers; otherwise good density and real data (41 rows).
- Fees Paid (clerk__30): renders 4 empty striped rows and no message — looks broken rather than empty. IQD
  currency could not be verified anywhere in the clerk seat because both money screens (Fees, and case fees)
  are empty/broken.
- Search UX is actually decent on the registers: incoming filter panel offers صادر/وارد/داخلي, Registered/
  Draft/Void, بانتظار الرد/متأخر عن الرد/مجاب, My Entries, This Year plus sensible group-bys (clerk__08_filters)
  — but half the labels are English (`Promised A Date`, `Contact Notes`, `...t Back For Completion` truncated).

### 15–17. Form and polish notes
- Correspondence form (clerk__07_form/08_form): statusbar hybrid labels; header buttons mix languages
  (`طباعة الكتاب`, `تدوين اتصال`, `Attach Filed PDF`, `Void - إلغاء`, `Next In Thread`); the "In Thread 0"
  stat button renders detached in the header centre instead of a button box; every second label carries a
  superscript `?`; chatter is minimal (fine).
- Document form (clerk__14_form): WHAT IT IS / VALIDITY groups, English tabs (Notes, History, Scans),
  statusbar `Superseded | In Force` untranslated; Confidential flag visible and unexplained.
- Gov body form (clerk__19_form): genuinely useful clerk content (working calendar, salutation, portal URL)
  buried under English headings (HOW WE DEAL WITH IT, HOW A LETTER TO THEM IS ADDRESSED).
- Legal entity form (clerk__17): "Our Numbers At Each Body" tab is exactly what a clerk needs at a counter —
  keep it — but the helper sentence renders with a leading period and the tab/group titles are English.
- No JS console errors or warnings anywhere in the clerk walk except the case-kanban crash; `overflowX` was 0
  on every screen (no horizontal page scroll at 1366 or 1920).
- 1920x1080 reshoots (clerk__40/41/42): layouts scale without breaking, but the My Desk action-card bidi
  scramble persists and the KPI cards stretch with large whitespace.

### What is worth keeping in the redesign (clerk seat)
- The Mail Room dashboard concept: arrived-today queue with "Open a new file / Attach to a file", the
  awaiting-reply chase list with reply-due dates and one-click reminder/telephone-note actions (clerk__03/40).
- The register wizard with automatic numbering (`تسجيل ومنح الرقم`) and "يُمنح عند التسجيل" placeholder for
  Our Number.
- My Desk's "bodies' desks" cards with counter hours and outstanding buckets per government body.
- The Compliance Calendar and Blocking Documents data models — the content is right, the presentation is not.

## Screenshot index (docs/ui-audit/before/)
- clerk__01_home_after_login, clerk__02_apps_menu — landing in Discuss; switcher with Apps.
- clerk__03_mailroom_dashboard, clerk__04_my_desk — role dashboards (English, bidi issues).
- clerk__05_corr_mailroom, clerk__06_corr_register_wizard, clerk__07_corr_outgoing(+_form),
  clerk__08_corr_incoming(+_form,_new,_filters), clerk__12_corr_awaiting, clerk__13_corr_contact_notes.
- clerk__14_docs_company(+_form), clerk__16_docs_renewals, clerk__17_legal_entities(+_form),
  clerk__19_gov_bodies(+_form).
- clerk__21_files_cases (crash), clerk__22_files_crash_details (traceback expanded).
- clerk__24_my_files (crash), clerk__25_overdue_files, clerk__26_blocking_documents,
  clerk__27_compliance_calendar, clerk__28_powers_of_attorney, clerk__30_fees_paid.
- clerk__31_discuss, clerk__32_apps_menu_access, clerk__33_user_menu.
- clerk__34_probe_config_procedure_type, clerk__35_probe_res_users, clerk__36_probe_escalations,
  clerk__37_probe_action_log — URL-probe evidence.
- clerk__40_fullhd_mailroom_dashboard, clerk__41_fullhd_corr_incoming, clerk__42_fullhd_my_desk — 1920x1080.
