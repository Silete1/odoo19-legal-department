# legal_procedure OWL frontend — audit (KEY=owl)

Audited against the actual local Odoo 19 web framework source (`odoo-19.0/addons/web/static/src`), the running
`legal_dept` database on :8090 (read-only SQL), and the module source at
`custom_addons/legal_procedure/`. Scope: the ten components under `static/src/components/`, the
payload composer `models/legal_dashboard.py` (1452 lines), the two HOOT test files under
`static/tests/`, the asset declaration in `__manifest__.py`, and the action/menu wiring in
`views/legal_dashboard_views.xml`.

## Summary

This is, by a wide margin, the most technically literate OWL code in the audited suite. The idioms are
genuinely current Odoo 19: field registry entries with `supportedTypes: ["json"]` (valid per
`web/static/src/views/fields/field.js:20`), `standardFieldProps` / `standardActionServiceProps` spreads,
`Layout` with `display="{ controlPanel: {} }"` (same idiom as `mrp_mo_overview.xml:5`), client actions with
`static path` matched by an `ir.actions.client` `path` field (read by `action_service.js:537`), the dialogs
registry (`select_create` — exists at `select_create_dialog.js:131`, and the props passed all match),
`loadBundle("web.chartjs_lib")`, `getCustomColor(scheme, light, dark)` with the correct 3-arg signature
(`colors.js:163`), and HOOT tests in the correct `web.assets_unit_tests` bundle. The SCSS is exemplary on
RTL: logical properties throughout, `dir` stamped from a server flag, direction-tied chevrons mirrored and
nothing else, Arabic typography rules (no tracking, no italic, raised line-height), every colour a compiled
Odoo SCSS token, and Tajawal loaded from Odoo's own shipped font files (path verified:
`odoo-19.0/addons/web/static/fonts/google/Tajawal/`). Each screen is filled by ONE `orm.call` and every
domain, label and threshold is composed server-side — the right architecture for an Arabic-first system.

The problems are not idiom problems; they are **integration and truthfulness problems**. Four of the ten
components — the phase rail, the document checklist, the counter walk, and the chart wrapper — are shipped,
registered, styled, and (two of them) tested, yet are used by **no view in the source tree and no view in the
running database** (verified both by grep and by SQL over `ir_ui_view.arch_db`: 0 matches), and the JSON
fields they render (`progress_payload`, `checklist_payload`, a walk payload) **do not exist on `legal.case`**
— the case form still shows `step_id` as a stock statusbar. The dashboard's tiles compute several of their
numbers from the 8-row visible page instead of the whole queue, on a screen whose own docstring says two
disagreeing numbers destroy trust. The 1452-line payload composer has **zero Python tests** despite the
frontend's explicit contract ("the whole of the logic is testable in Python"). The read-only auditor role
required by the spec cannot see either screen. And both client actions have no error state at all — a failed
RPC is an eternal spinner.

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Phase rail / checklist / counter walk / chart | Registered field widgets + styled components + tests | Used by ZERO views (source + DB verified); payload fields don't exist on `legal.case`; case form uses stock statusbar | high | Add the Json payload fields/computes to `legal.case`, place the widgets on the case form, or delete the dead layer |
| 2 | legal_dashboard.py tests | 1452 lines of thresholds, working-day arithmetic, domains, Arabic composition | Zero Python tests; the JS tests mock the whole payload, so nothing tests the real contract | high | A Python test class per public method: payload shape, clock verdicts, domain correctness, degraded modes |
| 3 | Tile arithmetic | `_mail_room_head` / `_desk_head` derive overdue/oldest/urgent/stalled/with-body from ≤8 fetched rows | Tiles undercount the moment the queue exceeds `COLUMN_LIMIT`; hero (search_count) and tiles then disagree | high | Compute every tile with `search_count`/`read_group` over the full domain, and drill-through domains over the queue, not the visible ids |
| 4 | Auditor role | Menus gated `groups="legal_core.group_legal_clerk"`; auditor implies only `base.group_user` | The spec's read-only auditor sees neither the Mail Room nor My Desk; `_role_brief()` has no auditor notion | high | Add auditor to the menu groups (screens are read-mostly and record rules already apply) and a read-only role brief |
| 5 | Loading / error states | `load()` is `try/finally` with no catch; template shows spinner while `data` falsy | Any RPC failure (incl. the deliberately re-raised `AccessError`) = eternal spinner + unhandled rejection; no retry, no message | high | An error state in `useState`, a caught `load()`, a visible retry; distinguish no-permission from failure |
| 6 | Server fan-out per call | `get_desk_data` → 8 bodies × 3 sections × (search + count) + `get_work_duration_data(compute_leaves=True)` up to twice per row | One HTTP call (good) but O(bodies × sections × rows) queries + calendar walks on the landing screen | medium | Batch with `read_group` per section kind; compute working-day ages in one pass per calendar; cache `_rtl()` per call |
| 7 | `t-out` on server HTML | `t-out="body.counter_notes"` (a `fields.Html`) and `t-out="payload.clerk_instruction_html"` | JSON-RPC strings are not OWL `Markup`, so `t-out` escapes them — the clerk sees literal `<p>` tags in the live Body Desk | medium | Send plain text, or wrap sanitised HTML in `markup()` client-side with an explicit comment on why it is safe |
| 8 | JS test coverage & honesty | 2 of 10 components tested; phase-rail test defines `progress_payload` on a *mock* model | Tests stay green while the real model lacks the field and no view mounts the widget; desk, counter-walk save batching, checklist untested | medium | Test LegalDesk (bands/roles), counter-walk save/dirty logic, checklist toggling; a Python test asserting the real field exists |
| 9 | Manager analytics | Band C re-renders the same `data.bodies` as Band B; comments promise a "Performance screen, one click away" | The promised median/p90 screen doesn't exist; `LegalChart` (the best-built component) has zero consumers | medium | Build the Performance client action on LegalChart + `read_group`, or drop the promises and the dead chart |
| 10 | "Arrived today" column | Domain: incoming ∧ no case ∧ not-note ∧ state in (draft, registered) — no date clause | The column headed "وارد اليوم" lists every unattached incoming letter ever; heading lies as backlog grows | low | Either an `our_date`-today clause with a separate backlog count, or rename the column ("Unfiled incoming") |
| 11 | aria-expanded | `t-att-aria-expanded="state.notes"` etc. (boolean) | OWL drops falsy attrs → collapsed state renders no `aria-expanded` at all; Odoo's own idiom is `expr ? 'true' : 'false'` | low | `t-att-aria-expanded="expr ? 'true' : 'false'"` in body_desk, checklist, desk toggles |
| 12 | KPI tile semantics | `<div role="button" tabindex>` + hand-rolled Enter/Space handler | Reimplements what `<button>` gives free; also loses native disabled semantics when the tile "stops being a button" | low | A real `<button>` with `disabled` when count is zero; drop `onKeydown` |
| 13 | Clock badge dead states | SCSS ships `o_legal_clock_paused`; `isSilent` tests `"not_applicable"`; server emits only on_track/warning/overdue | Styles and guards for states the server never sends; `kind="at_us"` produced but only `at_body` styled | low | Align the state vocabulary between `_clock()` and the SCSS; delete or implement paused |

## Detailed notes

### 1. The flagship widget layer is dead code (high)

The module's most argued-for UX — the USWDS phase rail, the GOV.UK task-list checklist, the runner's
counter walk — is unreachable in the shipped product:

- Registrations exist: `legal_phase_rail` (`static/src/components/phase_rail/legal_phase_rail.js:127-139`),
  `legal_checklist` (`checklist/legal_checklist.js:144-159`), `legal_counter_walk`
  (`counter_walk/legal_counter_walk.js:144-150`), `legal_clock_badge` (`clock_badge/legal_clock_badge.js:92-110`),
  `legal_body_desk` (`body_desk/legal_body_desk.js:122-128`).
- `grep 'widget="legal' custom_addons/` matches **only** `static/tests/legal_phase_rail.test.js:91`.
- SQL over the live DB: `SELECT count(*) FROM ir_ui_view WHERE arch_db::text LIKE '%legal_phase_rail%' …` → **0**.
- The server fields the widgets render do not exist: `grep progress_payload|checklist_payload custom_addons/legal_*` →
  no hits (only `dma_accreditation`, a different suite, has one). `legal.case`
  (`models/legal_case.py`) has `capture_values` as its only Json field; the case form
  (`views/legal_case_views.xml:38`) renders `step_id` with stock `widget="statusbar"`.

So a thirteen-step procedure is presented to the clerk as a statusbar of raw steps — precisely the
anti-pattern the phase rail's own docstring argues against — while the rail, its 205-line RTL-safe SCSS,
its accessibility contract and its ten HOOT tests ship as freight. The counter-walk's save path
(`legal_counter_walk.js:129-141`, `record.update({[name]: {...payload, ticks}})`) writes to a field no
model has, and no server inverse exists to consume `ticks`. Either grow the payload computes on
`legal.case` (`progress_payload` as compute over `phase_id`/`step_id`, `checklist_payload` over
`legal.case.document`, the walk over `legal.case.step.check`) and place the widgets on the form, or
delete the layer. Note also that none of the interactive field widgets consult `props.readonly` — the
counter walk would happily tick and save on a read-only (auditor) form the day it is wired.

`LegalChart` (`chart/legal_chart.js`) is the same story with no registration at all: imported by nobody,
zero template references outside its own. It is the best-engineered wrapper in the suite (correct lazy
`web.chartjs_lib` loading, destroy-before-recreate lifecycle, `getCustomColor` theming, the four RTL
options Chart.js needs) — dead.

### 2. The 1452-line payload composer has no Python tests (high)

Every component docstring makes the same promise: "every number … is composed on the server … which is why
the whole of the logic is testable in Python" (`legal_mail_room.js:34-38`), "the Python tests the only
place the clock is defined" (`legal_clock_badge.js:19`). `custom_addons/legal_procedure/tests/` contains
`test_case_engine.py`, `test_obligations.py`, `test_procedure_graph.py`, `test_wizards.py` — and no test
touches `legal.dashboard`, `get_mail_room_data`, or `get_desk_data`. The clock verdict ladder
(`legal_dashboard.py:262-319`), the working-day fallback ladder (`:230-257`), the probing/degradation
machinery (`:76-154`), the my-turn domain (`:989-1021`) — all untested. The HOOT tests cannot cover this:
they hand the component a hand-written payload (`static/tests/legal_mail_room.test.js:27-155`). The
contract between the two halves is tested on neither side.

### 3. Page-derived tile numbers (high)

`_mail_room_head` (`legal_dashboard.py:389-410`): `overdue` and `oldest` are computed from
`awaiting.get("rows")` — at most `COLUMN_LIMIT = 8` rows (`:40`) — while the tile beside them ("With the
bodies") uses the full `search_count`. With 30 letters awaiting, "Overdue replies" reports only how many of
the *first eight* are overdue. `_desk_head` (`:1077-1140`) does the same for `urgent`, `oldest`,
`stalled_ids` and `with_body`, and then builds drill-through actions as `[("id", "in", stalled_ids)]` —
so the "Stalled over a fortnight" tile opens at most 8 records whatever the real backlog. The file's own
docstring (`:393-396`) states the standard this violates: "two numbers on one screen that disagree is worse
than one number". Fix: full-domain `search_count`/`read_group` per tile, and domains (not id-lists) for the
drill-throughs.

### 4. The auditor cannot see the dashboards (high)

`views/legal_dashboard_views.xml:40-52`: both menus carry `groups="legal_core.group_legal_clerk"`.
`legal_core/security/legal_core_security.xml:68-72`: `group_legal_auditor` implies only `base.group_user`
— it is outside the clerk→officer→approver→manager chain. The client spec requires a role dashboard
including the auditor. As shipped the auditor's application menu is empty of both screens (they could still
reach `/odoo/legal-mailroom` by URL — the payload would then be record-rule-filtered correctly, which shows
the server side is already safe to open up). `_role_brief` (`legal_dashboard.py:1398-1422`) similarly knows
manager/approver/officer/clerk and nothing else.

### 5. No error, no retry, no no-permission state (high)

`desk/legal_desk.js:66-73` and `mail_room/legal_mail_room.js:71-78`:

```js
async load() {
    this.state.busy = true;
    try {
        this.state.data = await this.orm.call("legal.dashboard", "get_desk_data", []);
    } finally {
        this.state.busy = false;
    }
}
```

No catch; the templates render the spinner whenever `!data` (`legal_desk.xml:387-390`,
`legal_mail_room.xml:527-530`). A network failure, a server error, or the `AccessError` that
`_safe_search` deliberately re-raises (`legal_dashboard.py:114-139` — a *correct* server decision) leaves
the landing screen of the application spinning forever, plus an unhandled rejection from `onWillStart`.
The `busy` flag is set and never read by any template. Needed: `{data, error}` state, a caught load, a
visible retry button, and a distinct message for the permission case. (Same applies to `attach()`'s
`onSelected` — an ORM failure there dies silently inside the dialog callback,
`legal_mail_room.js:100-113`.)

### 6. Server-side fan-out per landing call (medium)

The one-call-per-screen design is right, and the browser side is efficient. The server side of
`get_desk_data` is not: `get_body_desk_data` (`legal_dashboard.py:1169-1199`) runs, per body (≤8), three
sections each doing a `search(limit=5)` **and** a `search_count` (`:1288-1311`), and every case row costs
two `_working_days_since` calls, each a `calendar.get_work_duration_data(..., compute_leaves=True)` walk
(`:230-257`, `:1038-1039`). Worst case ≈ 48 search/count queries + ~250 calendar computations + a
`res.lang` lookup per `_clock` call (`_rtl()` at `:159-169` is re-evaluated per row via `:318`). It is
bounded, but it is the screen every user opens first, and it grows with configuration. Batch the sections
with `read_group(groupby="body_id")`, hoist `_rtl()` into a per-call cache, and compute ages per distinct
calendar rather than per row.

### 7. `t-out` renders server HTML as escaped text (medium)

OWL 2's `t-out` only injects markup for `Markup` instances; strings from JSON-RPC are plain strings and are
escaped (Odoo's own pattern is `markup(renderToString(...))`, `core/utils/render.js:69`). Two places rely
on the opposite:

- `body_desk/legal_body_desk.xml:34-36` — `t-out="body.counter_notes"`, fed from `legal.gov.body.note`,
  a translated `fields.Html` (`legal_core/models/legal_gov_body.py:169`). **This path is live** (Band B of
  My Desk; 39 bodies in the DB): a note saved in the rich-text editor displays as literal `<p>…</p>`.
- `phase_rail/legal_phase_rail.xml` (`clerk_instruction_html` block) — dead today (finding 1) but the same
  bug the day the rail is wired.

Either compose plain text server-side, or return the sanitised HTML and wrap it in `markup()` in a getter
with a comment stating the sanitisation guarantee.

### 8. JS tests: excellent craft, thin and self-deceiving coverage (medium)

What exists is model HOOT usage — current imports (`@odoo/hoot`, `@odoo/hoot-dom`, `@odoo/hoot-mock`),
`mountWithCleanup(WebClient)` + `getService("action").doAction` for a real action mount,
`defineModels`/`mountView` for the field widget, and the assertions are behavioural and unusually good
(empty states, zero-hero not a button, `dir` flip from the payload flag, `aria-current` uniqueness,
`dir="ltr"` pinning of counters). Two gaps:

- **Coverage**: 2 of 10 components. Untested: `LegalDesk` (role gating, band C disclosure, degraded notes),
  `LegalCounterWalk` (the only client-side write logic in the module — pending-tick batching, dirty
  marking, save), `LegalChecklist` (section toggling), `LegalKpiTile` (keyboard activation), `LegalChart`.
- **Honesty**: `legal_phase_rail.test.js:24-27` declares `progress_payload = fields.Json()` on a *mock*
  `legal.case`. The suite therefore passes while the real model has no such field and no view mounts the
  widget (finding 1). A widget test should be paired with a Python assertion that the real field/widget
  pairing exists, or the green suite certifies a feature that does not ship.

### 9. Promised analytics are absent; Band C is a duplicate (medium)

`legal_desk.xml:470-487` (Band C) re-iterates `data.bodies` — the same records Band B just rendered —
showing only label + outstanding count, while comments in both files (`legal_desk.xml:471-476`,
`legal_desk.js:36-44`) promise "the heavier analytics — median and p90 per step, our delay against theirs —
are the Performance screen, one click away". No such action, menu, or screen exists anywhere in the module,
and the chart wrapper built for it is unused (finding 1). For the manager role the spec demands, this is
the missing half of the dashboard. Either build the Performance client action (LegalChart +
`read_group` over `legal.action.log` / `stage_entered_on` deltas) or cut Band C and the comments.

### 10–13. Smaller items (low)

- **"Arrived today" without a date filter** (`legal_dashboard.py:486-507`): the domain is
  direction=in ∧ case_id=False ∧ ¬contact-note ∧ state∈(draft,registered) — no date leaf. With 14
  correspondence rows today it reads fine; after a month of backlog the heading is false. Rename or filter.
- **`aria-expanded` dropped when false**: `t-att-aria-expanded="state.notes"`
  (`legal_body_desk.xml:22-28`), `isOpen(section)` (`legal_checklist.xml:137-140`), `state.load`
  (`legal_desk.xml:463-467`). OWL omits falsy attributes, so the collapsed state announces nothing. Odoo's
  own components write `expr ? 'true' : 'false'` (`core/autocomplete/autocomplete.xml:15`,
  `core/dropdown/accordion_item.xml:9`). Also `aria-expanded` on the phase buttons
  (`legal_phase_rail.xml`) is arguably the wrong relationship (they select, not disclose) — `aria-pressed`
  or a radio pattern fits better.
- **KPI tile as `div role="button"`** (`kpi_tile/legal_kpi_tile.xml:498-503`, `legal_kpi_tile.js:53-58`):
  works, but a native `<button>` removes the hand-rolled keydown and gives focus/disabled semantics free.
  The other components got this right — every other target in the module is a real `<button>`.
- **Clock badge state drift**: `_clock()` (`legal_dashboard.py:285-307`) emits `on_track|warning|overdue`;
  the SCSS additionally styles `o_legal_clock_paused` (`legal_clock_badge.scss:83-85`) and the JS guards
  `state === "not_applicable"` (`legal_clock_badge.js:59-62`) — neither is ever sent. `kind="at_us"` is
  emitted but only `at_body` has a kind style. Harmless today; vocabulary drift between the three files is
  exactly what the module's own comments warn about.

## What is genuinely right (keep on redesign)

- **Asset wiring** (`__manifest__.py` assets block): one `components/**/*` glob into `web.assets_backend`
  (templates, SCSS, JS all picked up — correct Odoo 19 mechanics), tests into `web.assets_unit_tests`
  (the real bundle, `web/__manifest__.py:471`).
- **Registry usage**: actions + fields registries, `static path` bookmarkable client actions mirrored by
  the `path` field on the `ir.actions.client` records, dialogs registry lookup instead of a hard import.
- **Single-RPC screens with server-composed payloads** — the right shape for RTL/i18n and for the
  read-only-auditor security model (browser never composes a domain; `link_correspondence` is the single
  write and goes through the ORM as the user, `legal_dashboard.py:1427-1452`).
- **SCSS RTL-safety**: logical properties exclusively (the only `left/right` hits in the entire tree are
  comments and deliberate `scaleX(-1)` chevron flips guarded by `[dir="rtl"]`); compiled theme tokens, no
  invented CSS variables; Tajawal loaded from Odoo's shipped copy with the fonts.odoocdn.com pitfall
  explicitly avoided (`_common/legal_fonts.scss`); Arabic typography constraints enforced.
- **Accessibility intent**: real buttons nearly everywhere, whole-row targets, visually-hidden status words
  beside every colour, `<details>` table fallback for the rail, `role="progressbar"` with values, pinned
  `dir="ltr"` on every number/reference against bidi reordering.
- **`_t` discipline**: literal msgids in static lookups so the .pot extractor sees them; every business
  string arrives translated in the payload.

The redesign should therefore *wire and finish* this layer, not rewrite it: grow the payload fields on
`legal.case`, mount the rail/checklist/walk on the case form, fix the tile arithmetic, add the error
states, open the menus to the auditor, and put a Python test suite behind `legal.dashboard`.
