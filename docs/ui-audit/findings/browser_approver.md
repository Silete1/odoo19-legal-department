# Browser UI/UX + RTL Audit — Approver role (approver@legal.iq)

**KEY:** `browser_approver` · **Date:** 2026-08-31 · **Instance:** http://localhost:8090 db=legal_dept · **UI lang:** ar_001 (RTL), TZ Asia/Baghdad · **Viewport:** 1366×768 (re-shoots at 1920×1080)

**Evidence:** 46 screenshots in `docs/ui-audit/before/approver__*.png` (walk `01–38`, crash/detail probes `40–48`). Console/menu/notes dumps kept in the session scratchpad (`approver_console.json`, `approver_menus.json`, `approver_notes.json`, `approver_probe.json`).

## Summary

The approver is the role this suite serves worst. The two central menus — **Operations → Files** and **Operations → My Files** — crash with an OWL client error before any list renders (a strict-JSON regression in the case kanban's `<progressbar>` attribute), so the approver cannot open the caseload at all through the primary paths. The one approval queue that exists — the "Awaiting your approval" band on the My Desk OWL screen — is **structurally empty**: nothing in the database routes work to the approver (all 123 procedure steps have `responsible_group_id = NULL`, all 6 cases have `pending_group_id = NULL`, no transition is group-gated, and no case is assigned to the approver user). There is no other approvals list, filter, or menu. Approval **evidence** is equally thin: the Action Trail menu is hidden from approvers, the case form's Trail button produced no visible response when clicked in the probe, and no "approved by / signed by" trace exists on the file. On top of that, the login lands the approver in **Discuss**, not the Legal app; the modules ship **zero translation files** so an Arabic-first UI is saturated with English; and several mixed-language strings render bidi-mangled. The OWL desk/mail-room screens themselves are well-built (RTL-aware, whole-row targets, no horizontal overflow at 1366px) — the failure is routing, translation, and the broken case list, not the dashboard architecture.

| Area | Current | Problem | Severity | Target |
|---|---|---|---|---|
| Files / My Files menus | OWL crash dialog "عذراً! حدث خطأ ما"; list never opens (shots 09, 10, 40, 41) | `JSON.parse` fails in `KanbanArchParser.parseProgressBar` — `progressbar colors` uses a single-quoted Python dict (`legal_procedure/views/legal_case_views.xml:348-349`); Odoo 19 requires strict JSON. Both actions are kanban-first (`:442-446`, `:465-470`) so the crash blocks them entirely | critical | Double-quoted JSON in `colors`; smoke-test every view type per role |
| Approval routing | "Awaiting your approval" = 0; desk all zeros (shots 08, 09) | Queue domain is `user_id = me OR pending_group_id in my groups` (`legal_dashboard.py:989-1010`) but **nothing ever routes to the approver**: 123/123 steps `responsible_group_id NULL`, 6/6 cases `pending_group_id NULL`, `legal_procedure_transition_res_groups_rel` empty, approver in no `officer_ids`, 0 assigned cases | critical | Content packs must set step owner groups and gate signature transitions to the Approver group; demo data must stage at least one file at an approval step |
| Approvals queue discoverability | Only queue is the My Desk band; Operations menu has Files/My Files/Overdue/Blocking/Compliance/Escalations — no approvals entry; no search filter for it | An approver who misses the desk band has zero way to find work awaiting signature; with the band empty the role is blind | high | Dedicated "Awaiting my approval" action + search filter + activity type; desk band backed by a real approval-step domain |
| Approval evidence | Trail menu hidden from approver (`legal_procedure_menus.xml:68-73`: auditor+manager only); form "Trail" stat button click gave no visible response in probe (shot 47); no approved-by/signed-by fields on the file | The person who signs cannot see the trail their signature lands in; server action itself is fine (RPC returns a valid act_window and 1 log row for case 438), so the button is a UI dead-click plus a menu-rights inconsistency | high | Give approver read access path to the trail of their files (menu or working button); render approval entries (who/when/what) on the form |
| Primary buttons on a real file | "Record This Step" → clipped English toast "Missing required fields" top-left (shot 48); "Available Moves" renders as an unlabeled empty box (`available_transition_ids = []`); Advance replaced by "Blocked" | The demo file demands a Power of Attorney (`poa_usage='required'`) while the POA register holds **zero** records — every path off the first step is a dead end; the failure message is English, clipped, and misplaced for RTL | high | Demo data with a valid POA; Arabic validation messages anchored correctly in RTL; empty-state text inside Available Moves |
| Translations | No `i18n/` directory in any legal_* module; nav, list headers, statusbars, dashboard cards, buttons, toasts all English on an ar_001 UI (every shot) | Spec is Arabic-first RTL with working translations; today the UI is majority-English with Arabic data | high | Ship complete `ar.po` for all five modules; CI check for untranslated terms |
| RTL/bidi rendering | POA empty state renders "before somebody needs it وكالة Record the" (shot 33); blocker banner "…" has not been provided. (and 1 more)" reversed (shots 44-48); English sentences show leading periods ".Nothing is waiting for you" (shot 08) | Mixed-direction strings lack direction isolation, so English/Arabic fragments shuffle into nonsense | high | Translate fully (removes most mixing); wrap unavoidable mixed runs in `bdi`/directional marks |
| Login landing | Approver lands in Discuss, empty "لم يتم تحديد محادثة" (shots 01, 36) | First touch of the system for the signing role is an empty chat app, not their desk | high | Default the Legal roles' home action to the Legal desk |
| Desk band semantics | Band titled "Awaiting your approval" but uses the same "mine" domain as the clerk (`legal_dashboard.py:940,965-980,1415`) | Any file merely assigned to the approver would be presented as awaiting approval — the title over-promises what the engine records | medium | Title from a real signature-step flag, or neutral title until the flag exists |
| Menu naming/duplication | Two "Mail Room" entries (top nav + Registers submenu); "My Desk" nav vs "My Files" menu vs action 529 also named "My Desk"; Registers dropdown is a 12-item flat mix (correspondence, documents, entities, bodies, POA, fees) | Duplicate and near-duplicate names force guessing; the Registers dropdown has no grouping | medium | One name per surface; group the Registers dropdown with section headers |
| Bilingual concatenated labels | "صادر - Outgoing", "وارد - Incoming", "سجل الصادر والوارد / Correspondence Register" (`legal_correspondence_menus.xml:15,26,32,38`), "Registered - مسجل", "THEIR REFERENCE - كتابهم", "Void - إلغاء" (shot 21) | Hard-coded two-language labels instead of translations; inconsistent (some items pure Arabic, some pure English) and doubled length | medium | Single-language labels + real translations |
| Compliance Calendar list | 41 rows each with an English "Open The File" link column; State truncated to "…t Started"; Arabic cells heavily truncated (shot 14) | Redundant per-row verb column wastes the widest column while real data truncates; badges unreadable | medium | Row click opens the file (no verb column); wider state column or icon badges |
| Empty states | Escalations/Overdue show stock "إنشاء مستند جديد" smiley (shots 11, 16); Fees Paid renders phantom empty stripes and no message (shot 34) | Queue lists prompt a signing role to "create a new document"; Fees shows a broken-looking blank | medium | Role-appropriate empty states ("nothing overdue today") on all queue actions |
| This Step tab layout | Instruction box empty and unlabeled; "COUNTER WALK" English header with editable "إضافة بند" lines; moves/instruction below the fold at 1366×768 (shots 45, 46) | The tab that carries the approver's actual decision surface is half-empty, half-English, and buried | medium | Instruction and moves above the fold; translated headers; read-only counter walk for non-owners |
| Apps catalog exposure | "Apps" menu lists 58 saleable Odoo apps with "Request Access" (Sales, Studio, eCommerce…) in English (shot 05) | Stock Odoo 19 community discovery UI is pure noise for a legal approver | low | Hide `base.menu_management` from legal roles or accept the stock behavior knowingly |
| User menu | "My Preferences", "Shortcuts" untranslated; "حساب Odoo.com الخاص بي" SaaS link on-prem (shot 35) | Chrome partly English; irrelevant SaaS entry | low | Translation + remove Odoo.com entry for internal deployment |

## Detailed notes

### 1. The case list is dead for the approver (critical)

Clicking **Operations → Files** or **Operations → My Files** never leaves `/odoo/legal-desk`; Odoo's crash dialog appears (Arabic title, English stack). Reproduced deterministically by direct URL (`/odoo/action-527`, `/odoo/action-529` — shots 40, 41): `has_kanban: 0, has_list: 0, dialog_seen: true` both times. Full stack captured from the dialog:

```
OwlError … Caused by: SyntaxError: Expected property name or '}' in JSON at position 1
  at JSON.parse
  at KanbanArchParser.parseProgressBar
  at KanbanArchParser.parse
  at View.loadView
```

Root cause — `legal_procedure/views/legal_case_views.xml:348-349`:

```xml
<progressbar field="sla_state"
             colors="{'on_track': 'success', 'warning': 'warning', 'overdue': 'danger', 'escalated': 'danger'}"/>
```

Odoo 19's `KanbanArchParser.parseProgressBar` runs `JSON.parse` on `colors`; single quotes are not JSON. Every user whose entry point is the kanban (both actions are `view_mode="kanban,…"`, `legal_case_views.xml:442-446` and `:465-470`) hits it. The Overdue action (list-first, action 528) works, which is why shot 11 renders — a misleading partial survival. The form also still opens by direct record URL (`/odoo/action-527/438`, shot 44).

Server-side reads are fine as approver (XML-RPC `get_views`, `web_search_read`, `search_read` on `legal.case` all succeed), confirming the failure is purely the client-side arch parse.

### 2. The approval queue exists in code and in nothing else (critical)

`legal.dashboard._role_brief()` (`legal_dashboard.py:1398-1421`) correctly detects the role and retitles the desk worklist "Awaiting your approval" (`:940`). The domain behind it (`_my_turn_domain`, `:989-1010`) is `user_id = me OR pending_group_id ∈ my groups`. Verified in the database:

- `legal_procedure_step.responsible_group_id` — **NULL for all 123 steps** (every content pack: tax, registrar, chamber, social security, residency);
- `legal_case.pending_group_id` — **NULL for all 6 cases**;
- `legal_procedure_transition_res_groups_rel` — **0 rows** (no move requires any group, so a clerk can fire any "approval" transition the guards otherwise allow);
- the approver user (uid 17, only group `legal_core.group_legal_approver` + its implied chain) is on **no** `legal.gov.body.officer_ids` (`legal_iq_demo/data/demo_users.xml:111-162` names only officer/clerk/manager) and has **0** assigned cases (assignments: uid 15 ×2, uid 16 ×4).

The security architecture (five groups, per-body visibility as data — `legal_core/security/legal_core_security.xml:36-75`, `legal_procedure/security/legal_procedure_rules.xml:80-100`) is sound *as design*, but as delivered the approver's whole reason to log in — a queue, a signature gate — has no data behind it anywhere in the procedure library or demo set. Shots 08/09: every desk tile 0 while the mail room simultaneously shows 7 files with bodies and 6 overdue replies — the department is busy and the approver sees none of it as theirs.

### 3. Approval evidence (high)

- The append-only trail is genuinely well-built (`legal_procedure/models/legal_action_log.py` — immutable even under sudo, denormalised snapshots) and the approver *can* read it: access CSV grants read via the implied clerk chain, and RPC as approver returns the case-438 row.
- But the **Action Trail menu** is `groups="legal_core.group_legal_auditor,legal_core.group_legal_manager"` (`legal_procedure_menus.xml:68-73`) — the signer is excluded from the register of their own signatures while the clerk-readable ACL says they may read it. Inconsistent by construction.
- The form's **Trail** stat button (`action_open_log`, `legal_case.py`) returned a valid action over RPC, yet clicking it in the probe produced no navigation, no dialog, no error (shot 47, URL unchanged, 0 rows shown). Observed once, reproducible in that session — treat as a UI dead-click to verify and fix.
- Nothing on the form says "approved by X on Y". The only approver-visible privilege marker is the **Re-open** button (`legal_case_views.xml:35-37`, `groups="legal_core.group_legal_approver"`). For a legal department, a signature that leaves no visible trace on the document is a workflow gap, not polish.

### 4. A real file dead-ends under the approver's hands (high)

On `GCT-CLR/2026/0001` (shots 44-48):

- Header shows **Return For Correction / Record This Step / Blocked** (English, on Arabic UI). "Advance" correctly hides while blocked.
- **Record This Step** → red toast **"Missing required fields"**, English, clipped, rendered at the top-*left* of an RTL screen (shot 48). Cause: `poa_id` required (`poa_usage == 'required'`) and `legal_poa` holds **zero rows** database-wide — no POA can even be picked. `legal_fee` is empty too. The flagship demo file cannot take its first step.
- **Available Moves** (`legal_case_views.xml:106-121`) renders as an unlabeled empty embedded list — `available_transition_ids = []` — with no text explaining why there is nothing to press.
- The blocker banner interleaves Arabic and English into bidi soup: `"البيانات المالية المدققة (لأغراض ضريبية)" has not been provided. (and 1 more)`.
- The statusbar is correctly non-clickable Arabic step names (good design, `legal_case_views.xml:6-12`), and the 22-station tour is collapsed into one pill — good.
- "This Step" tab: **COUNTER WALK** list has English headers (Refused/Done/Reference/Stamp/Window/Name) and an editable "إضافة بند" row open to the approver.

### 5. Language and RTL (high)

No `custom_addons/legal_*/i18n/` exists — the modules ship no translations at all, so every `string=`/OWL label surfaces in source English on the ar_001 interface: top nav (Registers/Operations/My Desk/Mail Room), every list header walked (shots 11, 13, 14, 16, 18, 33, 34), the desk and mail-room cards ("Waiting for you", "Stalled over a fortnight", "Send a reminder", "Log a telephone call"…), statusbars, toasts. Where Arabic was wanted, it was **hard-coded bilingually** instead: menu names `صادر - Outgoing`, `وارد - Incoming`, `سجل الصادر والوارد / Correspondence Register` (`legal_correspondence_menus.xml:15,26,32,38`), form strings `THEIR REFERENCE - كتابهم`, `HAND-OFF - الإحالة`, statusbar `Registered - مسجل` (shot 21). Meanwhile actual record data (procedures, steps, letters, subjects) is properly Arabic — the content is localised, the product is not.

Bidi failures where English and Arabic meet: POA help title renders "**before somebody needs it وكالة Record the**" (shot 33); sentence-final periods land at line start (".Nothing is waiting for you", shot 08).

Positives: layout mirroring is broadly correct (RTL columns, breadcrumbs, chatter position, grouped-row chevrons); **no horizontal overflow** on any walked screen at 1366×768 (scrollWidth == clientWidth in all 38 measurements); Arabic-Indic numerals appear in dates while file numbers stay LTR-isolated (`dir="ltr"` spans in the OWL components — deliberate and correct).

### 6. Navigation and chrome (medium/low)

- Landing after login is **Discuss** (shots 01, 36) — the Legal root menu's sequence 45 loses to Discuss.
- Apps visible to approver: Discuss, Legal, **Apps** (`base.menu_management`) — the last opens the 58-app store catalog with "Request Access" buttons (shot 05).
- The wizard menu "تسجيل كتاب وارد" correctly opens as a dialog (shot 19) — one of the few Arabic-labelled menus.
- User menu (shot 35): "My Preferences"/"Shortcuts" English, plus an Odoo.com account link.
- Empty states: Overdue and Escalations show the stock "إنشاء مستند جديد" create-prompt for what are monitoring queues (shots 11, 16); Fees Paid draws phantom row stripes with no message at all (shot 34).
- Odoo's crash dialog itself mixes registers: "عذراً! حدث خطأ ما… خدمة الدعم الودودة" over an English-only stack — unavoidable chrome today, but the underlying crash must simply not exist.

### What is genuinely good (keep in the redesign)

- The desk/mail-room OWL architecture: one payload-driven screen per audience, server-decided domains (`_my_turn_domain` doc comment is explicit that the browser never decides "mine"), whole-row buttons with aria-labels, capped age meters with the true figure beside them, LTR-isolated numerals.
- Non-clickable statusbar on the case (writes must pass guards) and the pressable "Blocked" twin that explains itself.
- The immutable action log design.
- Correct dialog behavior for the register wizard; correct RTL mirroring of stock views.

### Verification appendix

- Crash stack: `approver_probe.json` (scratchpad), shots 40/41; root cause line `legal_case_views.xml:348-349`.
- Routing emptiness: read-only SQL over `legal_procedure_step`, `legal_case`, `legal_procedure_transition_res_groups_rel`, `legal_gov_body_res_users_rel`, `legal_poa`, `legal_fee`, `legal_sla_escalation` (counts quoted above).
- RPC-as-approver checks: `authenticate` uid 17; `legal.case` `get_views`/`web_search_read`/`search_read` OK; `action_open_log(438)` returns valid action; `legal.action.log` search_read returns the file's row.
- No `pageerror` events besides the OwlError pair; no console warnings recorded on walked screens beyond the crash.
