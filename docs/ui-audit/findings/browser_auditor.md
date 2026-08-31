# Browser UI/UX + RTL Audit — Auditor Role (`auditor@legal.iq`)

**Audit date:** 2026-08-31 · **Server:** http://localhost:8090, db `legal_dept` · **Viewport:** 1366x768 (key screens re-shot at 1920x1080)
**User under test:** عبد الرحمن نوري الساعدي — lang `ar_001`, tz Asia/Baghdad, group **Auditor (read only)** (all `ir.model.access` rows `1,0,0,0` across legal_core / legal_correspondence / legal_procedure).
**Method:** Playwright/Chromium scripted walk of every reachable menu + direct URL access to every legal `ir.actions.act_window` and both OWL client actions, with `console`/`pageerror` listeners; then a controlled mutation phase (brief-granted exception) attempting every mutation surface and verifying server-side denial. Screenshots: `docs/ui-audit/before/auditor__*.png` (01–89).

## Summary

The **read-only guarantee holds for business data**: every attempted business mutation was either impossible in the rendered UI (forms read-only, chatter disabled, statusbar disabled, no inline edit) or was denied server-side with a proper `AccessError` (archive, workflow wizard buttons, dashboard buttons). The only successful write was a **personal favorite (`ir.filters`)** — Odoo-core by-design personal preference data — which was reverted through the same UI and verified gone by SQL. No residue remains (0 test messages, 0 archived records, 0 activities, 0 filters; all 14 correspondence records still `registered`).

The auditor *experience*, however, is far from the target product: the **Files / My Files kanban crashes for every user** (malformed `progressbar colors` JSON in the `legal.case` kanban arch), the two custom OWL dashboards are **100% untranslated English rendered inside an RTL context** (leading-period bidi breakage on every sentence), the menu tree and most column/filter/status labels leak English or truncated bilingual composites on an Arabic-first UI, the auditor **lands in Discuss** with no auditor-facing dashboard at all, the **Action Trail attributes every entry to OdooBot**, and the auditor — whose job is extraction and reporting — **has no Export anywhere**. RTL *layout mirroring itself is correct* (`o_rtl` bundle active, mirrored breadcrumbs/statusbar/search); the failures are content-language and audience-awareness, not geometry. No horizontal overflow was detected on any screen at 1366x768, and the only JS console errors in the entire walk were the two kanban crashes.

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Operations → Files / My Files (`legal.case` kanban, actions 527/529) | OwlError crash dialog «عذراً! حدث خطأ ما...»; view never renders | `progressbar colors="{'on_track': ...}"` is a Python-style single-quoted dict; `JSON.parse` fails in `KanbanArchParser.parseProgressBar` → the case workspace is dead **for all roles** (Overdue survives only because its `view_mode` starts with `list`) | **critical** | Valid JSON (`{"on_track": "success", ...}`) in `legal_procedure/views/legal_case_views.xml:348-350`; smoke-test every view per role |
| 2 | My Desk + Mail Room OWL dashboards (`/odoo/legal-mydesk`, `/odoo/legal-mailroom`) | Entire dashboards in English on an `ar_001` UI; RTL container renders every English sentence with leading period (".Nothing is waiting for you.") | Zero translation of the flagship custom frontend; broken bidi typography on every line; unusable for an Arabic-first legal department | **high** | Full `ar_001` translations for `legal_desk.js` / `legal_mail_room.js` templates; Arabic-first copy, correct digit/date locale |
| 3 | Menus, columns, filters, statusbars everywhere | Menus «Operations/Registers/Files/Company Documents/…» in English; same list mixes English headers (Kind, State, Reply Due) with Arabic (رقم الصادر, م/ الموضوع); bilingual composite values truncate: «مسجل - d...», «صادر - ing...», «...t Started», «الجهة - ...nt Body» | Massive English leakage + truncated bilingual "AR - EN" composites look broken and unprofessional; violates Arabic-first spec | **high** | Single-language Arabic labels via proper translations (not "AR - EN" concatenation in source strings); English only under `en_US` |
| 4 | Auditor landing & role dashboard | Login lands in **Discuss**; Legal navbar shows only Operations + Registers; My Desk / Mail Room menus are Clerk-only; dashboards reachable by URL show clerk widgets and clerk action buttons | The spec requires a role dashboard incl. auditor; the auditor has no home, no oversight view, and the dashboards are not audience-aware | **high** | Default home = Legal for legal users; an auditor variant of the dashboard (read-only KPIs, no action buttons) |
| 5 | Registers → Action Trail (`legal.action.log`, action 530) | All 19 entries show actor **OdooBot** with one identical timestamp (٣١ أغسطس ٢:٠٨) | An audit trail whose "By" column never names a human actor is useless to an auditor (demo-seeding artifact and/or logging design that records the cron/bot user) | **high** | Log the acting user at action time; seed demo data with realistic actors/timestamps |
| 6 | Mutation affordances visible to auditor | Form cog shows «الأرشيف» (archive → confirm → AccessError); header buttons «تدوين اتصال», «إلغاء - Void», «Attach Filed PDF» enabled (click → AccessError); dashboard buttons «Open a new file / Attach to a file / Send a reminder / Log a telephone call» rendered | Enforcement is correct server-side, but the auditor is offered actions that always fail — misleading, noisy, and it invites error dialogs | **medium** | Hide archive/void/wizard buttons behind `groups=` on views and audience checks in OWL components |
| 7 | Export / Import | No Export anywhere (list cog contains only Print); Import correctly absent | An auditor's core need is extraction/reporting; with no export group the read-only role cannot pull data out | **medium** | Grant `base.group_allow_export` to the auditor group (or a dedicated report surface) |
| 8 | Empty lists | Awaiting Reply, Contact Notes, Blocking Documents, Fees Paid show a bare header row with no `o_view_nocontent` helper (Overdue, Escalations, POA, Service Levels do have helpers) | Inconsistent empty-state guidance; blank grids read as errors | **medium** | Add action `help` text to every list action |
| 9 | Compliance Calendar list (action 526) | State column truncated to «...t Started» on every row; per-row English button «Open The File»; headers all English | Key state unreadable; repeated English CTA on Arabic UI | **medium** | Wider/optional-width state column or badge widget; translate; one-click row open instead of a labelled button per row |
| 10 | Mail Room default list (action 169) | Opens grouped by Body + filter Registered with all groups collapsed → 6 header rows only | The register book the clerk/auditor expects (سجل الصادر والوارد) is hidden behind two clicks; screen looks empty | **medium** | Default expanded groups or a flat register default; keep grouping as an option |
| 11 | Favorites (`ir.filters`) — **mutation test that SUCCEEDED** | Auditor saved a favorite («حفظ البحث الحالي» → row id 1, `create_uid` 19); reverted via same UI; SQL now 0 rows | Personal-preference record, writable by Odoo core design — *not* a business-data breach; but the pencil opens the raw technical `ir.filters` form (English «Filter Name / Shared with / Default Filter / Domain») instead of a friendly dialog | **low** | Acceptable; optionally style/translate the favorite-edit surface |
| 12 | Read-only signposting | Forms render flat with no banner or ribbon saying the auditor is read-only; chatter buttons visible but disabled | Auditor cannot tell whether the form is broken or intentionally locked | **low** | A read-only ribbon/banner for the auditor group |
| 13 | Menu/ACL inconsistencies | Escalations menu hidden (Follow-up Officer group) though auditor has read ACL and the list renders fine by URL; all Configuration actions readable by URL while menus are manager-only | Harmless but incoherent visibility matrix for an oversight role | **low** | Align menu groups with the auditor's read scope deliberately |
| 14 | Polish | Company name always truncated in navbar («شركة الرافدين ... »); jokey core delete-confirm copy («وداعاً للسجل! ... أأنت واثق؟») surfaced on filter delete; dashboards at 1920x1080 show large empty card areas | Tone/density below "professional dense enterprise UI" bar | **low** | Compact header, curated Arabic terminology overrides, denser dashboard grid |

## Mutation-attempt log (controlled exception)

Before-state recorded first in every case; server DB verified by read-only SQL afterwards.

| Surface | What was attempted | Result | Evidence |
|---|---|---|---|
| Form field edit + Save | Outgoing letter ق/2026/0781 form | **Impossible** — form renders read-only: 0 editable inputs, no Save button on any of 8 forms opened | `auditor__63_outgoing_form.png` |
| Inline list edit | dblclick cell, Phases list (action 516) | **Impossible** — no editor opens (`selectedRowInputs: 0`) | `auditor__73_inline_edit_attempt.png` |
| Chatter post / attach / activity | إرسال رسالة, ملاحظة, النشاط, إرفاق الملفات on correspondence + document forms | **Blocked client-side** — all four buttons rendered but `disabled` | probe2 log `chatter_button_states` |
| Statusbar state click | «مسودة - Draft» on registered letter | **Blocked** — every statusbar button disabled | probe2 log `MUT_statusbar_click` |
| Workflow button | «تدوين اتصال» (form header) and dashboard «Log a telephone call» | **Denied server-side** — AccessError: wizard `legal.contact.note.wizard` allowed to Legal Department/Clerk only | `auditor__77_logcontact_button_attempt.png`, `auditor__75_dashboard_logcall_attempt.png` |
| Register-incoming wizard | direct URL `/odoo/action-174` | **Denied server-side** — AccessError (Clerk only); menu itself correctly hidden from auditor | `auditor__61_register_wizard_auditor.png` |
| Archive | Form cog → «الأرشيف» → confirm | **Denied server-side** — AccessError «لا يُسمح لك بتغيير سجل 'Correspondence Entry'»; list still 9 rows; SQL `active=false` count 0 | `auditor__79_archive_attempt_form.png` |
| Delete / Duplicate | Business records | **Not offered** — form cog = Print + Archive only; list cog (with selection) = Print only | `auditor__78_form_cog_full.png`, `auditor__70_list_cog_menu.png` |
| Export / Import | List selection cog | **Not offered** (see finding 7) | `auditor__69_list_row_selected.png` |
| Quick-create many2one | — | **N/A** — no editable many2one exists anywhere for the auditor (forms read-only) | — |
| Favorites | «حفظ البحث الحالي» on action 170 | **SUCCEEDED** — `ir.filters` id 1 «صادر - Outgoing», `create_uid` 19 (auditor). Personal preference record, Odoo-core by design. **Reverted via same UI** (favorite pencil → ir.filters form → cog → حذف → confirm). SQL after: `ir_filters` count **0** | `auditor__83_favorite_attempt2.png`, `auditor__88_favorite_dialog.png` |

**Post-audit residue verification (SQL, read-only):** `ir_filters` = 0 · `mail_message` containing 'AUDIT' = 0 · `legal_correspondence` with `active=false` = 0 · states unchanged (14 × `registered`) · `mail_activity` = 0.

## Detailed notes

### 1. Files/My Files kanban crash (critical)
`custom_addons/legal_procedure/views/legal_case_views.xml:348-350`:

```xml
<progressbar field="sla_state"
             colors="{'on_track': 'success', 'warning': 'warning', 'overdue': 'danger', 'escalated': 'danger'}"/>
```

Odoo 19's `KanbanArchParser.parseProgressBar` runs `JSON.parse(colors)`; single quotes are invalid JSON →
`SyntaxError: Expected property name or '}' in JSON at position 1` → OwlError → generic crash dialog (`auditor__60_files_kanban_CRASH.png`, expanded technical details in `auditor__84_files_crash_details.png`). Actions 527 (Files) and 529 (My Desk list menu "My Files") both open kanban first and die; 528 (Overdue) works because it opens list-first. This is client-side arch parsing — it affects **every** role, not only the auditor.

### 2. OWL dashboards untranslated + bidi breakage (high)
`legal_procedure/static/src/components/desk/legal_desk.js` and `.../mail_room/legal_mail_room.js` (client actions 533/532, paths `/odoo/legal-mydesk`, `/odoo/legal-mailroom`). Every string is English: "Needs your action", "Waiting for you", "Stalled over a fortnight", "With the body", "Expiring within 90 days", "The bodies' desks", "Awaiting a reply", "Arrived today", "Open a new file", "Attach to a file", "Log a telephone call", "Send a reminder", "Counter notes", "Nothing outstanding"…  Inside the RTL page each sentence renders with its full stop at the *start* (".Nothing is waiting for you"). Evidence: `auditor__03_my_desk_dashboard.png`, `auditor__04_mailroom_dashboard.png`, FHD `auditor__80_fhd_my_desk.png`, `auditor__81_fhd_mailroom.png`. At 1920x1080 the My Desk "Needs your action" card is ~90% empty space.

Menus 163/164 (`legal_dashboard_views.xml:40,47`) are Clerk-group-only, so the auditor never sees them in the navbar — but the client actions themselves are not group-guarded: by URL the auditor gets the full clerk UI with actionable-looking buttons whose wizards then raise AccessError.

### 3. English leakage and bilingual composites (high)
- `ar_001` menu translations equal the English source for almost every menu (`Operations`, `Registers`, `Files`, `Company Documents`, `Renewals Due`, `Legal Entities`, `Government Bodies`, `Powers Of Attorney`, `Fees Paid`, `Action Trail`, `Awaiting Reply`, `Contact Notes`…).
- Labels hard-code both languages in one string: menu `سجل الصادر والوارد / Correspondence Register` (`legal_correspondence_menus.xml:15`), actions/menus «صادر - Outgoing», «وارد - Incoming», selection values «مسجل - Registered», «باستلام... ». These composites truncate in badges and narrow columns: «مسجل - d...», «صادر - ing...», «متأخر الر...», column header «الجهة - ...nt Body» (`auditor__09_outgoing_list.png`, `auditor__82_fhd_outgoing_list.png` — still truncated even at 1920px).
- Search panel mixes languages: filters «صادر/وارد/داخلي» beside «Registered/Draft/Void/Promised A Date/Contact Notes», all group-bys English (`auditor__49_mailroom_filters_panel.png`).
- Forms: labels 100% English (Name, VALIDITY, Issue Date, OBLIGATION CLOCKS, HOW WE DEAL WITH IT, SALUTATION…) over Arabic values — e.g. `auditor__19_company_documents_form.png`, `auditor__24_government_bodies_form.png`.
- Statusbars English: «Superseded | In Force», «Waived | Late | Filed | In Progress | Not Started».

### 4. Auditor journey (high)
Login → **Discuss** (`auditor__02_home_after_login.png`); no Legal home action for the role. Navbar in Legal shows only two sections (Operations, Registers). There is no oversight/dashboard surface for the auditor at all, while the spec calls for a role dashboard including the auditor. The Action Trail — the one auditor-specific menu (groups: Auditor + Legal Manager) — shows OdooBot as actor on all 19 rows with an identical logged-on timestamp (`auditor__27_action_trail.png`), so the trail currently answers neither *who* nor *when*.

### 5. RTL layout itself: correct (positive)
`o_rtl` class + RTL asset bundle active; navbar, breadcrumbs, statusbar arrows, search facets, list pager and chevrons all mirror correctly; Arabic-Indic digits render in dates. No horizontal overflow on any of the 47 screens measured at 1366x768 (`hscroll: 0` everywhere). Only genuine RTL defect found is the bidi punctuation of untranslated English strings (finding 2).

### 6. Console/JS health
Across the full walk: 0 `pageerror`s; the only console errors were the two OwlErrors from the `legal.case` kanban (actions 527/529). No warnings of note.

### 7. Enforcement summary (positive)
Server-side security for the auditor is real: model ACLs are read-only, and every server round-trip mutation attempt returned a well-formed Arabic AccessError naming the allowed groups. Client-side, Odoo correctly renders forms read-only (no Save, no editable fields, disabled chatter/statusbar). The gaps are cosmetic (finding 6: affordances that should be hidden) — not security holes.

## Screenshot index (before evidence)
`docs/ui-audit/before/auditor__01..50` — login, home, dashboards, menu dropdowns, every list + representative forms, filter panel, webclient root.
`auditor__60..79` — crash evidence, wizard AccessError, Legal menu dropdowns, outgoing form (full page), mutation attempts (log-note, activity, selection cog, archive, favorites, dashboard button).
`auditor__80..89` — 1920x1080 reshoots (My Desk, Mail Room, Outgoing list), favorite-cleanup evidence.
