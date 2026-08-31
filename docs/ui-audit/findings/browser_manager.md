# Browser UI/UX + RTL Audit — Legal Manager role (manager@legal.iq)

**KEY:** browser_manager
**Date:** 2026-08-31 · Server http://localhost:8090 db=legal_dept · Viewport 1366x768 (re-shoots at 1920x1080)
**User locale:** ar_001, Asia/Baghdad — the whole session ran on the Arabic RTL web client.
**Evidence:** `docs/ui-audit/before/manager__01..58_*.png` + console/diag dump (scratchpad `manager_diag.json`).
**Method:** full menu walk of every item under the Legal root menu (menus 114–164, actions 153–174 and 514–533), real records opened on Files, Compliance Calendar, Correspondence, Documents, Entities, Procedures and Letter Templates; search/filter panels opened; the register-incoming wizard opened and discarded; JS console and pageerror listeners active throughout. No record was created, edited or saved.

## Summary

The manager's session is defined by one hard crash and one systemic language failure. **The Files kanban — the single most important screen for a legal manager — throws an OwlError on open** (`progressbar` colors attribute is Python-dict syntax, not JSON), so both *Operations → Files* and *Operations → My Files* die with an Arabic "عذراً!" error dialog on every open, at both resolutions. Around it, the app is **English-chrome-on-Arabic-data**: not one legal module ships an `i18n/` folder, so every menu, column header, button, statusbar, group title, KPI card and empty state renders in English on the ar_001 interface, while a second, competing convention hardcodes bilingual "عربي - English" strings into field labels and menu names. Untranslated English sentences inside RTL containers get BiDi-scrambled (".Nothing is waiting for you", "before somebody needs it وكالة Record the"). For the manager specifically there is **no departmental overview at all**: My Desk shows the manager's own (empty) workload with four zero KPI cards and most of the screen blank; there is no per-officer workload, no assignment view, no overdue rollup, and login lands the manager in **Discuss**, not Legal. Configuration — the manager's own duty — has a dropdown menu taller than a 1366x768 screen with no scrolling, so its tail (Correspondence kinds/templates, the whole Entities section) is unreachable by mouse from the menubar. Positives worth keeping: RTL page direction itself is correct everywhere (no horizontal overflow on any of the 40+ screens measured), list data density is reasonable, the Mail Room/desk OWL dashboards are a genuinely custom frontend, and the Arabic operational data (procedures, letters, documents) is rich and realistic.

| Area | Current | Problem | Severity | Target |
|---|---|---|---|---|
| Operations → Files / My Files | Kanban crashes with OwlError + error dialog; view never renders (manager__08, __09, __53) | `progressbar colors="{'on_track': …}"` is Python-dict syntax; `KanbanArchParser.parseProgressBar` does `JSON.parse` → SyntaxError. Core case workspace dead at default view, both viewports | critical | Valid JSON (`{"on_track": "success", …}`) at `legal_procedure/views/legal_case_views.xml:348-349`; smoke-test every view type per action |
| Arabic translations | 0 `i18n/` dirs in all 9 legal modules; ar_001 UI shows English menus, headers, buttons, states, empty states everywhere | Client spec is Arabic-first RTL with working translations; today only record data is Arabic, all chrome is English | high | Ship `i18n/ar.po` (or ar_001) for every module; export POT, translate all view/model/JS strings; CI check for untranslated terms |
| Bilingual hardcoded labels | "رقم كتابهم - Their Number" (`legal_correspondence/models/legal_correspondence.py:141`), "صادر - Outgoing" menus, "Registered - مسجل" statusbar, "OUR REGISTER - سجلنا" group headers | Second competing i18n convention; noisy, doubles label width, defeats real translation, inconsistent with English-only labels one field away | high | Single-language source labels (English) + proper ar.po; drop every " - " bilingual composite |
| RTL/BiDi text integrity | ".Nothing is waiting for you" (desk), "before somebody needs it وكالة Record the" (POA empty state), scrambled warning banner on case form (manager__55) | English sentences in RTL containers reorder: period jumps to line start, mixed Ar/En headings shuffle into nonsense — looks broken to users | high | Translate the strings (root fix); where mixed-language text is by design, wrap runs in `<bdi>`/`dir="auto"` |
| Manager departmental overview | My Desk for the manager = personal KPIs all 0 + "The bodies' desks"; no department workload, per-officer load, overdue rollup or assignment tools (manager__07, __52) | The brief's manager persona (departmental overview, workload, overdue, assignment) has no screen; a manager sees an empty desk and must trawl list views | high | Manager band on the desk: per-officer open/overdue counts, unassigned queue, SLA breaches, aging buckets, one-click reassign |
| Login landing | manager@legal.iq lands in Discuss (manager__02, URL `/odoo/discuss`) | Legal staff open on chat, not their work app; violates "role dashboard" spec | high | Set users' default home action to the Legal desk/action (`res.users.action_id`) or lower the Legal root menu sequence below Discuss |
| Configuration menubar dropdown | Dropdown taller than 768px viewport, clipped after "Correspondence → Registers", no scroll (manager__05) | Correspondence Kinds, Letter Templates and the whole Entities section are unreachable from the menubar at 1366x768 — manager cannot reach his own config | high | Fewer/nested sections or `max-height + overflow-y:auto` on `.o-dropdown--menu`; flatten config into a settings page |
| Menu duplication / naming | Two "Mail Room" items (client action + list), "Government Bodies" under both Registers and Configuration (same action 154), "Procedures → Procedures", "Registers" both a section and a config leaf, root item "سجل الصادر والوارد / Correspondence Register" | Technically-shaped, duplicated and over-long labels; users cannot tell the two Mail Rooms apart (`legal_core/views/legal_core_menus.xml`, `legal_correspondence/views/legal_correspondence_menus.xml`, `legal_procedure/views/legal_procedure_menus.xml`) | medium | One entry per destination, unique short Arabic labels, registers vs config strictly separated |
| Compliance Calendar list | "Open The File" link column on all 41 rows; State column truncated to "…t Started" on every row (manager__12) | Prime column wasted on a repeated action; state unreadable — the two things a manager scans for | medium | Row click opens the file (kill the column); wider state column or colored badge with short Arabic labels |
| Empty states | Escalations/Overdue: stock "إنشاء مستند جديد"; Fees Paid: blank phantom striped rows, zero guidance (manager__30); POA & Service Levels: long informal English-only prose ("cries wolf every Friday and goes berserk over Eid") (manager__29, __39) | No actionable guidance where it matters, unprofessional register where there is text, and all of it English-only on an Arabic UI | medium | Short, professional Arabic empty states: what this list is, what fills it, one primary action |
| Truncated column headers | "الجهة - nt Body…" (Mail Room list), "…st target) / …s before) / …ing days)" (Service Levels), "…ade / Class", "…t Number" (Documents) | Bilingual labels + parenthetical units make headers physically untruncatable; several are pure ellipsis garbage | medium | Short single-language headers; units in tooltip/help, not the string |
| Case form layout | Top half ~50% whitespace (right column 4 fields vs left 10); all-caps English group headers WHO AND WHEN / WHAT AND FOR WHOM / COUNTER WALK; embedded lists render phantom empty rows (manager__55, __57, __58) | Dense enterprise UI it is not: one screenful of form holds ~14 fields; visual noise from fake rows in empty x2many lists | medium | Rebalance columns, tighten groups, Arabic sentence-case section titles, suppress empty-list sample striping |
| Currency display | Entity Capital shows `750,000,000.00` bare; Fees Paid Paid/Quoted columns bare numbers (manager__27, __30) | IQD requirement: amounts carry no currency; 2-decimal format is wrong for IQD usage | medium | `monetary` widgets with IQD currency (0 decimals), currency on the records |
| Desk band navigation | Clicking the "Legal Manager" band label on My Desk re-navigates and breadcrumb becomes "غير مسمى" (Unnamed) (manager__56) | Client-action state loses its display name; content unchanged → click feels dead and the title breaks | medium | Give the client action a stable display name across internal navigation; make band switching update content visibly |
| Desk visual economy | 4 oversized KPI cards (huge numerals, heavy padding) in right rail; main column mostly blank at 1366x768 and worse at 1920 (manager__07, __52) | Wasted vertical/horizontal space; a zero-state desk fills one screen with 5 numbers | medium | Compact stat tiles in a single row; give reclaimed space to actionable lists |
| Action Trail | All 19 entries "By: OdooBot"; Action values English ("Letter", "Opened", "File opened under") (manager__31) | Audit register that cannot say who acted is not an audit register; mixed language values | medium | Log real acting user; translate action values |
| Register wizard dialog | Labels mix "From Which Body" / "تاريخ التسجيل - Received On" / values "عادي - Ordinary"; footer buttons Arabic (manager__51) | Three language conventions inside one dialog — the app's most-used data-entry surface | medium | Single-language labels + ar.po; consistent field order for a clerk's transcription flow |
| Mail Room default view | Opens grouped-by-body with all data columns empty until a group expands (manager__16) | First screen of the register is a list of six chevron rows — looks empty despite 14 letters | low | Default flat list sorted by date, grouping opt-in |
| Statusbar language | Compliance statusbar Waived/Late/Filed/In Progress/Not Started; correspondence "Registered - مسجل"/"مسودة - Draft"; case statusbar itself is Arabic step names (good) (manager__14, __20, __55) | State language flips per model; selection states untranslated | low | Translate selection values via ar.po; keep the case statusbar pattern |
| Console hygiene | Only 3 console errors across 40+ screens — all the same kanban crash; no other JS errors; docOverflowX = 0 on every screen measured | — (positive baseline worth preserving) | low | Keep zero-error, zero-overflow bar after redesign |

## Detailed notes

### 1. CRITICAL — Files / My Files kanban crash

- Repro: login as manager → Operations → Files (`/odoo/action-527`) or My Files (`/odoo/action-529`). OwlError dialog "عذراً! حدث خطأ ما…" appears over an empty screen. Confirmed at 1366x768 (`manager__08_files_list.png`) and 1920x1080 (`manager__53_fullhd_files.png`).
- Root cause captured from the browser console:
  `Caused by: SyntaxError: Expected property name or '}' in JSON at position 1 … at KanbanArchParser.parseProgressBar`.
- Source: `custom_addons/legal_procedure/views/legal_case_views.xml:348-349`:
  ```xml
  <progressbar field="sla_state"
               colors="{'on_track': 'success', 'warning': 'warning', 'overdue': 'danger', 'escalated': 'danger'}"/>
  ```
  Odoo 19's kanban arch parser `JSON.parse`s the `colors` attribute; single quotes are invalid JSON. Compare stock usage, e.g. `odoo-19.0/addons/project/views/project_task_views.xml` (`colors='{"...": "..."}'`).
- Blast radius: the kanban is the action's first view, so the *entire Files workspace* — the manager's core operational list — is unreachable except by hand-editing the URL to a form (`/odoo/action-527/438` works, `manager__55_case_form.png`). All 3 console errors captured session-wide are this one bug.

### 2. Language & RTL system

- `find legal_* -type d -name i18n` → **0 results**. No module ships any translation. Model/JS strings do go through `env._()` (e.g. `legal_procedure/models/legal_dashboard.py:941, 1197, 1417`), so the plumbing exists — the ar.po files simply don't.
- Consequence on ar_001: every navbar section (Operations/Registers/Configuration…), every list header, every button (Advance, Return For Correction, Waive, Mark Filed, Send a reminder, Log a telephone call…), every group title (VALIDITY, WHAT IT IS, OBLIGATION CLOCKS, REGISTRATION, COUNTER WALK…), every KPI card and every empty state is English. Screens are effectively 70% English chrome around Arabic data.
- The competing convention — hardcoded bilingual strings — appears in models (`legal_correspondence/models/legal_correspondence.py:141` "رقم كتابهم - Their Number"), menus (`legal_correspondence/views/legal_correspondence_menus.xml` "صادر - Outgoing", "سجل الصادر والوارد / Correspondence Register") and statusbars ("Registered - مسجل"). These double header widths (see truncation findings) and can never be localized cleanly.
- BiDi scrambling (a direct consequence of English text in RTL flow):
  - Desk: ".Nothing is waiting for you", ".Two ages on every row: at this step, and since the file was opened" — leading periods (`manager__07`).
  - POA empty state title renders as "**before somebody needs it وكالة Record the**" (`manager__29`) — word order destroyed by the embedded Arabic token.
  - Case form warning banner: "has not been provided. (and 1 more) "البيانات…"" (`manager__55`).
- Correct today (keep): global `direction: rtl` applied on body everywhere; breadcrumbs/controls mirror properly; statusbar chevrons point the right way in RTL; **no screen had horizontal document overflow** (docOverflowX = 0 in all diags).

### 3. Manager perspective — overview, workload, assignment

- My Desk (`/odoo/legal-desk`, `manager__07`, `manager__52`): band label "Legal Manager", tab "Your desk". Content is *personal*: Needs your action 0, Waiting for you 0, Stalled over a fortnight 0, With the body 0, Expiring within 90 days 5, then per-body cards ("The bodies' desks") that are all "Nothing outstanding". With 6 open files, 41 obligations and 6 overdue-reply letters in the department, the manager's dashboard shows effectively nothing actionable and **no way to see or rebalance anyone's workload**.
- Clicking the "Legal Manager" band label re-navigates the client action and the breadcrumb becomes **"غير مسمى"** (Unnamed) with unchanged content (`manager__56`, URL stays `/odoo/legal-desk`).
- Landing after login is **Discuss** (`manager__02`), so the desk is not even the entry point.
- Escalations (Operations → Escalations, `manager__15`) — the manager's supervision list — is empty with a stock create-prompt; nothing explains when an escalation would appear.

### 4. Menus (walk map — 5 sections, 40 leaves visited)

- Navbar sections: Mail Room, My Desk, Operations, Registers, Configuration (`diags.navbar_sections`).
- Dupes/collisions detailed in the table; source: `legal_core/views/legal_core_menus.xml` (root, Registers, Configuration incl. Government Bodies twice via action 154), `legal_procedure/views/legal_procedure_menus.xml` (Files/My Files/Overdue…, "Procedures → Procedures"), `legal_correspondence/views/legal_correspondence_menus.xml` (bilingual names, wizard "تسجيل كتاب وارد" as a plain menu item between registers), `legal_procedure/views/legal_dashboard_views.xml:39-48` (top-level Mail Room / My Desk client actions).
- Configuration dropdown clipping at 768px height (`manager__05`): visible until "Correspondence → Registers"; Correspondence Kinds, Letter Templates and the Entities block (Legal Forms, Identifier Kinds, Signatories & Seals) are cut off with no scrollbar.

### 5. Lists

- Compliance Calendar (41 rows, `manager__12`): "Open The File" repeated per row; State pills all truncated "…t Started"; headers English; Penalty Note takes ~1/3 width for prose. Filters panel itself is healthy (Outstanding/Late/Should Have Started + group-bys, `manager__13`) but filter names English while the panel headers are Arabic.
- Mail Room register (`manager__16`): default group-by-body renders six collapsed group rows, every data column blank; bilingual truncated header "الجهة - nt Body…". Search panel (`manager__17`) mixes Arabic filters (صادر/وارد/داخلي, بانتظار الرد) with English ones (Registered, Draft, Void, Promised A Date, My Entries, This Year).
- Outgoing (`manager__18`): the best list in the app — Arabic date/number columns, colored State/Reply badges — but badges are bilingual-truncated ("مسجل - d…", "مجاب - d…") and the redundant Direction column repeats "صادر - ing…" on every row of a register that is already outgoing-only.
- Document Register (`manager__23`): solid dense list with Validity badges (Valid/Expiring/Expired English) and a working renewal traffic-light; headers truncated ("…ade / Class", "…t Number", "…rt Renewal By").
- Fees Paid (`manager__30`): renders 4 phantom striped rows with no records and no empty-state text at all.
- Action Trail (`manager__31`): every row "By OdooBot"; Action values English; Description mixes "draft"/"File opened under" fragments into Arabic text (BiDi).

### 6. Forms

- Case form (`manager__55`, `__57`, `__58`): header stat-buttons Trail/Letters/Checklist (English); workflow buttons Return For Correction / Record This Step / Blocked (English, `legal_procedure/views/legal_case_views.xml:19-40`); statusbar itself shows Arabic step names — the one fully-Arabic control on the page. Non-clickable statusbar is a *deliberate, sound* guard (comment at `legal_case_views.xml:7-8`) — keep it. Right column runs out after 7 fields leaving a large void; COUNTER WALK tab shows an empty checklist as phantom striped rows; chatter is minimal (single OdooBot entry), not overwhelming.
- Correspondence form (`manager__20`): four bilingual all-caps group headers; bilingual statusbar; "In Thread 0" stat button; buttons Void - إلغاء / Next In Thread / تدوين اتصال — three conventions in one header row.
- Compliance obligation form (`manager__14`): clean, but 5-state English statusbar, English buttons (Waive / Mark Filed / Open The File), and the sheet's left half is empty.
- Entity form (`manager__27`): good bilingual name pattern (Arabic name + English subtitle as *data*), tabs English, ".The first thing a clerk is asked…" leading-period BiDi glitch in the tab help line, Capital without IQD.
- Register-incoming wizard (`manager__51`): correct modal RTL layout; mixed-language labels as noted; footer primary "تسجيل ومنح الرقم" is Arabic — the inconsistency is the defect, not any single string.

### 7. What is genuinely good (preserve through redesign)

- Zero horizontal overflow on every audited screen at 1366x768; RTL mirroring of controls, chevrons, breadcrumbs all correct.
- Only one distinct JS defect in the whole client (the kanban crash) — the OWL dashboards themselves run clean.
- Custom OWL Mail Room dashboard (`manager__06`) is the right product idea: arrived-today, awaiting-reply with working-day ages, per-item actions. It needs translation and RTL text fixes, not replacement.
- Data model breadth visible in the UI (procedures with versions, working-day SLAs, letter threads, obligation periods) is strong raw material for the professional system the spec asks for.

### Appendix — screens visited (actions)

Mail Room 532, My Desk 533, Files 527*, My Files 529*, Overdue 528, Blocking Documents 520, Compliance Calendar 526 (+form 436), Escalations 531, Corr Mail Room 169, تسجيل كتاب وارد wizard 174, Outgoing 170, Incoming 171 (+form 117), Awaiting Reply 172, Contact Notes 173, Company Documents 162 (+form 117), Renewals Due 163, Legal Entities 156 (+form 54), Government Bodies 154, POA 524, Fees Paid 522, Action Trail 530, Config: 514(+form)/515/516/518/517/519/521/523/525/166/167/168(+form)/160/161/155/153/157/158/159, case form 438 direct. `*` = crashed.
