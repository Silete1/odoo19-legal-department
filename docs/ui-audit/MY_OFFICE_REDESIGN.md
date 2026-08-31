# مكتبي — redesign of the first screen

Redesign and implementation of the Legal Affairs landing screen, plus the
reporting workspace that was pulled out of it.

**One sentence:** مكتبي keeps its menu entry, its name and its `/odoo/legal-desk`
URL, and stops being a wall of zeros — it is now a work queue that crosses eight
registers, a five-segment attention rail, a three-week agenda off the union
deadline board, and a tabbed context strip, with the analytics moved to their own
screen.

---

## 1. What was wrong, with evidence

Measured in a real browser at 1440×900, as all six logins, against
`legal_dept`. Raw evidence: `before-office/` (120 renders + `report.json`),
compared against `after-office/`.

| Role | Cards | Tiles | Page height | Queue rows visible |
|---|---|---|---|---|
| clerk | 8 | 3 | 1,686 px | 0 |
| officer | 10 | 3 | 2,129 px | 4 |
| approver | 11 | 6 | 2,214 px | 0 |
| manager | 20 | 9 | 2,844 px | 0 |
| auditor | 11 | 10 | 2,965 px | 0 |
| admin | 20 | 9 | 2,624 px | 0 |

Nine specific faults, each one visible in the BEFORE renders:

1. **The screen led with a number, not with work.** A hero card carrying a
   ~48px numeral, then a vertical rail of three-to-nine more cards each with
   its own large numeral. On the manager's screen, *nine of the ten largest
   pieces of type were digits.* A digit is the least actionable thing on a
   legal desk.

2. **The work list only knew about one register.** `_desk_files` queried
   `legal.case` and nothing else. The department also runs requests,
   contracts, opinions, lawsuits, correspondence, statutory obligations and
   document renewals — none of which could appear in a list titled
   *يتطلب إجراءك*. A manager whose real queue was one approval plus five
   expiring documents saw **لا شيء بانتظارك** beside ~700 px of empty white.

3. **The same content was rendered twice.** Band B (*مكاتب الجهات*, 8 panels)
   and Band C (*عبء المعاملات*) both iterated `data.bodies`. Together they
   were the largest block on the page — roughly 1,200 px each — and both were
   *reference material*, not work.

4. **Bands were ordered by module, not by urgency.** desk → approvals → audit
   → bodies → manager figures → bodies again. On the auditor's screen the
   first actionable thing sat at y≈732 and the bodies ran from y≈1,894.

5. **The attention strip was inert and identical for everyone.** Exactly two
   chips for all six roles — *الجلسات خلال ٧ أيام* and *طلبات بانتظار الفرز* —
   one of which read `0` for every single role. Zero role differentiation in
   the one element whose whole job is "what needs attention".

6. **No agenda at all.** `legal.deadline` is a SQL view UNIONing eleven clocks
   and held 94 live rows. The first screen showed none of them. *"What
   deadlines are approaching"* was unanswerable from مكتبي.

7. **No quick actions.** Nothing could be created from the landing screen.

8. **Role differentiation was additive, not structural.** Every role got the
   same three bands and then extra bands were appended. The clerk (intake) and
   the auditor (read-only oversight) were shown the same *hero + tiles + file
   worklist* frame even though neither owns `legal.case` steps that way.

9. **Surface hierarchy was flat.** Hero, tile, worklist, body panel and audit
   log were all `.o_legal_card` — 1px border, 8px radius, white. Nothing
   receded, so nothing led. Empty states occupied as much space as full ones.

Plus one outright defect: reached by its own URL the screen breadcrumbed as
**غير مسمى** (Untitled), because a client action opened by path arrives with no
display name.

---

## 2. References researched

Read for *mechanics*, not for branding.

| Source | What was taken |
|---|---|
| [Linear — how we redesigned the UI](https://linear.app/now/how-we-redesigned-the-linear-ui) and [a calmer interface](https://linear.app/now/behind-the-latest-design-refresh) | Surfaces defined as an elevation ladder rather than shadows; hierarchy from weight and alignment; navigation *recedes* so the work area leads; a small fixed set of theme variables instead of per-component colour |
| [ServiceNow — building great workspace experiences](https://www.servicenow.com/community/developer-blog/building-great-workspace-experiences-in-servicenow-ui-ux-tips/ba-p/3421765) and [Horizon workspace](https://horizon.servicenow.com/workspace/overview) | High-priority work items placed top/inline-start; progressive disclosure; split working area with a quick-reference column; per-persona page variants rather than one page with different numbers |
| [Pencil & Paper — enterprise data tables](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-data-tables), [Stéphanie Walter — complex data tables](https://stephaniewalter.design/blog/essential-resources-design-complex-data-tables/), [Setproduct — data table UI 2026](https://www.setproduct.com/blog/data-table-ui-design) | Compact row height 40–44px; 1px low-contrast dividers once past ~20 rows; drop vertical rules; cap default columns at six to eight |
| [Fuse Lab — enterprise UX 2026](https://fuselabcreative.com/enterprise-ux-design-guide-2026-best-practices/), [Designing for data density](https://paulwallas.medium.com/designing-for-data-density-what-most-ui-tutorials-wont-teach-you-091b3e9b51f4) | Density *with* clarity: a strict grid plus a firm type ramp is what lets a screen be dense without being noisy |
| [Legal workflow / matter management round-ups](https://gc.ai/blog/best-legal-workflow-software), [LawNext matter-management directory](https://directory.lawnext.com/categories/matter-management/) | The domain pattern that mattered: intake is triaged into a *single* prioritised queue, and turnaround/volume analytics live away from the operational queue |
| Odoo 19 source (`web/static/src`) | `Layout` control-panel slots as the compact header; `loadBundle("web.chartjs_lib")`; `computeViewClassName` as the scoping mechanism for native-view styling |

**Skills used:** the `dataviz` skill for the analytics screen — its form
heuristic, its two-series cap reasoning, and its palette validator (below).

---

## 3. Design principles adopted

1. **The largest type on the screen is a subject line, never a digit.** Counts
   are set at 17px in the rail; the queue subject is the visual lead.
2. **Colour is earned.** ~90% neutral ramp. Five semantic tones, each meaning a
   *state of the work*: critical, warning, waiting, calm, neutral. Brand colour
   appears on exactly two things — the primary create control and the focus
   ring. No gradients, no glass, no tinted panels, and one shadow rule that is
   never used outside overlays.
3. **Depth from structure.** Hairlines, a 3px inline-start state spine per row,
   sticky headers, alignment and weight. A bigger radius is not more important.
4. **Every count opens the records it counted.** Never a chart, never a summary.
   A count at zero stays visible and goes inert — "no overdue work" is
   information, and hiding it would make the strip change width under the reader.
5. **The reason is a column.** *Why is this on my desk* is composed on the
   server from the record and is the single most useful thing on the screen.
6. **Empty is good news, written in two lines** inside normal padding — not a
   300px illustration in the working area.
7. **Roles differ in structure, not in numbers.** Different registers feed
   different desks.
8. **Spacing is logical, always** — `margin-inline-*`, `padding-inline-*`,
   `border-inline-*`, `text-align: start`. Odoo pipes compiled CSS through
   rtlcss over *physical* properties, so a physical margin gets mirrored once by
   rtlcss and again by the `dir` the payload stamps.

---

## 4. Libraries and components — and their licences

The deliberate outcome: **zero new runtime dependencies.** Everything needed
was already inside Odoo 19 and correctly licensed.

| Component | Origin | Licence | Why |
|---|---|---|---|
| OWL 2 | Odoo 19 | LGPL-3 | The framework the backend already is |
| `Layout` + control-panel slots | `@web/search/layout` | LGPL-3 | The compact header **is** Odoo's control panel, filled through its slots — a screen that draws its own title bar under the breadcrumb has two headers |
| `Dropdown` / `DropdownItem` | `@web/core/dropdown` | LGPL-3 | The compact `+ جديد` split control |
| **Chart.js 4** | bundled at `web/static/lib/Chart` | **MIT** | Analytics only, lazily via `loadBundle("web.chartjs_lib")` — مكتبي never pays for it |
| `LegalChart` wrapper | `legal_procedure` (this suite) | LGPL-3 | Already owned lazy-loading, canvas lifecycle, theme ink and RTL legend/tooltip. Reused rather than rewritten |
| Font Awesome 4 icon set | Odoo 19 | SIL OFL 1.1 / MIT | One icon language across the suite |
| Tajawal | Odoo's own font files | SIL OFL 1.1 | Already the suite's Arabic face |

**Rejected, with reasons.** A dedicated data-grid (AG Grid, TanStack) — the
queue is capped at 40 rows and a `<table>` with a sticky header does the job
without a framework. A timeline library (vis-timeline, FullCalendar Timeline) —
FullCalendar ships with Odoo, but a month grid spends most of its pixels on
empty squares and is illegible at the agenda's width; a day-grouped rail reads
in the order the reader will meet the events. A command palette — Odoo 19
already has one on Ctrl-K.

### `eh_board` — evaluated, and the decision

`eh_board-19.0.6.0.1.zip` (Dashboard Builder, ERP Heritage) was extracted and
read: 42 Python modules, 38 JS modules, ~6 MB, original OWL/SVG chart engine,
20+ chart types, pivot/cross-tab, choropleth, cross-model joins, drill-down,
snapshots, alerts, kiosk mode.

**Its licence is `OPL-1`** — the Odoo Proprietary Licence — declared in its
manifest at `"license": "OPL-1"` (listed at `price: 0.0`). That is the decisive
fact and it produced three rules:

- **No code, markup, layout or naming from `eh_board` is copied into this
  suite.** OPL-1 permits use on the licensee's own database; it does not permit
  redistribution or derivation into an LGPL-3 module. Nothing was taken.
- **It is not used for مكتبي**, and not only for licence reasons. It is a
  *dashboard builder* — the answer to "what is happening", assembled by
  dragging tiles. مكتبي answers "what requires my action now", which is a queue
  you empty, not a board you watch. This is the separation the task asked for
  and it is the right one on the merits.
- **It remains available for management reporting**, which is where a board
  builder genuinely earns its place: a manager who wants a cross-model pivot or
  a choropleth should install it and build one. `legal_office` deliberately
  takes **no dependency** on it, so the suite works identically with or without
  it, and no LGPL-3 module in this repository is bound to a proprietary one.

The reporting need in §7 of the brief was met natively instead — fourteen panels
across four sections, every one drilling through — so the department gets its
analytics whether or not the proprietary module is licensed.

---

## 5. Layout

```
┌ control panel ─────────────────────────────────────────────────────────────┐
│ [+ جديد ▾]  مكتبي · مسؤول المتابعة · ٣١/٠٨/٢٠٢٦ · [اطّلاع فقط]      [⟳]    │
├────────────────────────────────────────────────────────────────────────────┤
│ ⚠ ١٠ متأخر │ ١ يستحق اليوم │ ٣ خلال ٧ أيام │ ٣ لدى الجهة │ ٨ الرد متأخر   │  ← rail, 40px, one line
├──────────────────────────────────────────────┬─────────────────────────────┤
│ ما يحتاج إجراءً مني                   ٢٥     │ الأجندة القادمة        ٣٧   │
│ [الكل ٢٥][معاملات ١][طلبات ٢][عقود ١]…       │ ── متأخر ───────── ١٩ ──    │
│ ┌──────────────────────────────────────────┐ │  ⚖ ٢٠٢٥-٠٥-٢٥ أحقية…       │
│ │▎نوع│ الرقم │ الموضوع │ الحالة │ السبب │ ⏱│ │  ⚖ ٢٠٢٥-١١-٠٥ نفاذ…        │
│ │▎…  44px rows, hairline, 3px state spine  │ │ ── اليوم ──────── ١ ──      │
│ └──────────────────────────────────────────┘ │  📅 …                       │
│              ~2.15fr                          │        minmax(19rem, 1fr)   │
├──────────────────────────────────────────────┴─────────────────────────────┤
│ [لدى جهة خارجية] [عاد إليك] [سُجِّل حديثًا]      ← tabs, 28px rows, 3 columns │
└────────────────────────────────────────────────────────────────────────────┘
```

Below `lg` the two columns stack; the queue keeps its six columns and the state
column narrows before the subject does, because the *why* column is the reason
the screen works.

**Queue columns (six, fixed):** kind icon + state spine · reference (pinned
`dir="ltr"`, tabular figures) · subject (largest type; truncated, never
wrapped, so every row is the same height) · stands at · **why** · due.

**Keyboard:** ↑/↓ move, Home/End jump, Enter/Space open. A clerk works this
list forty times a day.

---

## 6. Role differences — structural

Not one screen with different numbers. Different registers feed each desk, and
the plan is asserted by a test (`test_queue_composition_differs_by_role`).

| Role | Rail | Queue is fed by | Secondary |
|---|---|---|---|
| **كاتب** clerk | بانتظار التسجيل · غير مربوط بمعاملة · بلا مسؤول · مستندات ناقصة · تجديدات ٣٠ يومًا | correspondence intake, unrouted requests, blocked files, expiring documents | registered recently · answers still in time · recently opened |
| **متابع** officer | متأخر · يستحق اليوم · خلال ٧ أيام · لدى الجهة · الرد متأخر | my cases (excluding *at body*), my requests, my opinions, dated litigation, my contracts, letters to chase, obligations | with an external body · came back to you · recently registered |
| **مصادِق** approver | بانتظار توقيعك · طلبات للبتّ · عقود للمصادقة · آراء للمراجعة · أُعيدت إليك | signature-step cases, `ready_for_approval` requests, `internal_approval`/`to_sign` contracts, `review`/`approval` opinions | you decided recently · sent back · recently in force |
| **مدير** manager | متأخر بالدائرة · بلا مسؤول · طلبات غير مسندة · دعاوى عالية المخاطر · عقود تنتهي ٦٠ يومًا | unowned or SLA-breached cases, unassigned/overdue requests, risky or unlawyered litigation, risky/expiring contracts, unfiled statutory periods | load per officer · demand by department |
| **مدقّق** auditor | متأخر · المعاملات المفتوحة · الإجراءات هذا الأسبوع · قيود ملغاة | open cases, live requests, live contracts — **read-only** | latest recorded moves · service level |

The auditor's read-only guarantee is **server-side**: `_office_create` returns
`[]` when `can_write` is false, so the payload contains no create action at all
rather than a hidden one. Asserted by
`test_auditor_payload_carries_no_create_affordance`.

---

## 7. The analytics screen

`legal.analytics` → **التقارير والتحليلات**, first item under التقارير,
`/odoo/legal-analytics`. Fourteen panels in four sections; **every panel states
its management question in words** above the chart and carries its figures as a
table where each row drills through to the records behind it.

| Section | Panels |
|---|---|
| **الحِمل** | open files per officer · live requests by requesting department · live requests by type |
| **الالتزام بالمواعيد** | deadlines by register (overdue vs open) · ageing of live requests · average days request→decision · open files by service level |
| **دورة الحياة** | contracts by lifecycle stage · lawsuits by stage · open files by phase · opinions by stage |
| **ما هو قادم** | contract expirations next 12 months · hearings by week (next 8) · registered correspondence per month (in/out) |

**Colour was computed, not chosen.** Every palette was run through the
`dataviz` validator against Odoo's own surfaces:

```
#2a78d6,#eb6834  light on #ffffff  → ALL CHECKS PASS  (CVD ΔE 24.7, normal 33.6)
#3987e5,#d95926  dark  on #1e2129  → ALL CHECKS PASS  (CVD ΔE 26.8, normal 31.8)
#2a78d6,#d03b3b  light on #ffffff  → ALL CHECKS PASS  (CVD ΔE 23.8, normal 31.6)
#0ca30c,#fab219,#d03b3b            → FAILED (amber L 0.811 outside band; 1.83:1)
```

That last failure is why **every chart is capped at two series** — asserted by
`test_analytics_panels_all_state_a_question_and_drill_through`. A three-way
status stack would have put an unreadable amber on a white surface. Two series
always ship a legend, so identity is never carried by colour alone.

---

## 8. The design system

`legal_office/static/src/scss/legal_ds.scss` — one file, seven decisions, no
component may invent a value outside it.

- **Spacing** — 4px base: 4 · 8 · 12 · 16 · 24 · 32.
- **Type** — 11 (micro) · 12 (meta) · 13 (body) · 15 (lead) · 18 (title), each
  one step larger in Arabic (12/13/14) because naskh needs it; weights 400/500/600
  only; `letter-spacing: 0` and never italic, because Arabic letters connect and
  tracking breaks the joins; line-height 1.65 RTL vs 1.45 LTR.
- **Surfaces** — three levels only: ground · panel · sunken. A fourth would
  have to be invented before it could be used.
- **Borders** — hairline (rows) · rule (regions) · the 3px inline-start spine,
  which is the only border in the system carrying colour as information.
- **Rows** — 44px queue · 32px agenda · 28px secondary · 28px controls.
- **Tones** — five, each a state of the work. `waiting` is a desaturated slate,
  not a blue: the ball being with the Tax Commission is not an alert, and a
  screen that paints it like one teaches people to ignore alerts.
- **Focus** — one ring, everywhere, never removed without a replacement.

### Native views brought into the same vocabulary

`legal_native.scss` gives the ordinary Odoo list, form and kanban the same row
height, hairlines, badge treatment, section-label voice, empty state and focus
ring — so clicking a queue row does not land you in a different product.

It is scoped to **`.o_legal_view`**, a class stamped on the arch root of this
suite's own views by `scripts/legal_stamp_view_class.py` (123 roots across 48
files, idempotent, `--check` mode for CI). Odoo copies a view root's `class`
onto the rendered controller (`computeViewClassName`), which is the framework's
own mechanism for saying *this view, not every view*. A legal module has no
business restyling `.o_list_view` globally — the accounting list is not ours to
change. `calendar` and `activity` roots are excluded: their RelaxNG schema
rejects a `class` attribute (found the hard way — it fails the registry load).

---

## 9. Implementation architecture

```
custom_addons/legal_office/            depends: legal_deadline, legal_reports
├── models/
│   ├── legal_office.py       legal.office    — get_office_data()
│   └── legal_analytics.py    legal.analytics — get_analytics_data(months)
├── views/  legal_office_views.xml · legal_office_menus.xml
├── static/src/
│   ├── scss/  legal_ds.scss · legal_native.scss
│   ├── office/    legal_office · work_queue · agenda · secondary  (.js/.xml)
│   └── analytics/ legal_analytics (.js/.xml/.scss)
├── i18n/ar.po      262 entries, 0 untranslated
└── tests/test_office.py
```

**مكتبي is not a new screen.** `legal_office` re-points the *existing*
`legal_procedure.action_legal_desk` — same record, same name, same menu entry,
same `/odoo/legal-desk` URL — at the `legal_office` tag. No second action, no
second menu item. Every bookmark and every link already sent still opens the
first screen.

What مكتبي used to *also* carry — one panel per government body with its
opening hours and counter notes — was reference material sitting on top of the
day's work. It keeps its component and its payload, and moves to its own
**مكاتب الجهات** screen at `/odoo/gov-desks`, third on the menu.

**Why one module, one dependency line.** `legal_deadline` already depends on
procedure, litigation, contract, opinion, request and correspondence, so a
single `depends` pulls the whole suite in and the queue can query every register
directly rather than through soft-dependency gymnastics.

**Why `_inherit = "legal.dashboard"`.** Prototypal inheritance for the proven
helper layer — soft model lookup, degrading search/count, numeral rendering,
working-day arithmetic, drill-through builders, `_role_brief`,
`_my_turn_domain`, `_signature_queue_domain`. Duplicating them would have meant
two implementations of "which digits does this company use" that could disagree.
It also means the existing `test_dashboard.py` suite guards this code too.

**Ownership is a server question.** `_my_turn_domain` resolves "mine" as
*assigned to me* **or** *standing at a step whose owning desk is a group I
hold* (`legal.case.pending_group_id`) — which is how a clerk covering for a
colleague sees the queue without anybody reassigning sixty records. A browser
cannot evaluate that, and one that guesses produces a queue the server would not
agree with.

**Ordering is `(bucket, -priority, date, -age)`.** Bucket dominates priority
and priority dominates date, so an overdue ordinary matter outranks a critical
one that is not yet due — the first is already costing the company something.
Asserted by `test_queue_is_ordered_by_when_it_hurts`.

**Everything is composed as the reader.** No `sudo()` anywhere; record rules
and the read-only auditor ACLs apply untouched.

### Defects found and fixed on the way

| Defect | Fix |
|---|---|
| `.o_legal_rail` collided with `legal_phase_rail.scss`, which sets `flex-direction: column` — the attention strip rendered as five stacked full-width rows, 221px tall | Renamed to `o_legal_signals`; a collision scan now covers `o_legal_pill`, `o_legal_blank`, `o_legal_note` too |
| A client action opened by URL breadcrumbs as **غير مسمى** | `env.config.setDisplayName()` in `setup()` |
| `class` on a `calendar` view root fails RelaxNG and aborts the registry load | `calendar`/`activity` excluded from the stamping script |
| The stamping and rename left `Government Desks` → `مكتبي` in the DB (Odoo keeps a stored translation when the source term changes), so two menu items read مكتبي | Catalogues regenerated from the DB export; `fill_po.py` now carries prior translations forward so regeneration can only add, never drop |
| The first `fill_po.py` used a line-oriented regex and silently skipped every multi-line `msgid` — i.e. the longest, most visible strings | Replaced with a multi-line-aware reader (`po.py`); audit re-run |
| `wait_until="networkidle"` never resolves against Odoo (the bus long-polls forever); `/web/login` lands on the database manager on a multi-DB server, so the login input is never visible | `scripts/legal_ui_capture.py` uses explicit selector waits and `?db=` |

---

## 10. Verification

Everything below was run against the live instance — `legal_dept` on port 8090,
Odoo 19 community from the source checkout — not against a fixture.

**Upgrade.** `-u` across all ten legal modules: **0 errors, 0 warnings** (the
only line in the log is the pre-existing PostgreSQL-12-below-minimum notice,
which predates this work). Three warnings *were* introduced during the work and
all three were fixed rather than tolerated:

- `class` on a `calendar` view root fails RelaxNG and aborts the registry load;
- one compute method serving both a stored and an unstored field
  (`legal.case.document`) — Odoo warns it will rewrite the stored fields on
  every read of the unstored one, so the method was split in two;
- `legal.dashboard could not aggregate legal.case` ×5 — a `_read_group` on
  `sla_state`, which is computed on read with a `search` method and no column.
  Replaced with per-value counts.

**Tests.** `--test-enable` across the ten modules:

```
205 post-tests in 19.9s, 18,647 queries
0 failed, 0 error(s) of 205 tests
```

That is the previous 192 plus 13 new ones in `legal_office/tests/test_office.py`,
which assert the things the redesign actually claims: every seat gets a complete
payload; the queue plan differs by role rather than by number; the auditor's
payload contains no create action; every queue row carries a reason and opens
its record; the ordering is by bucket; a signal at zero is not clickable; every
analytics panel states a question, caps at two series and carries a legend when
it has two.

Two of those tests exist because they caught live bugs:

- `test_department_wide_secondary_tabs_are_not_silently_empty` — the
  `sla_state` group-by above degraded to an empty list and only logged, so the
  auditor's service-level tab looked like a quiet week rather than a broken
  query. It is scoped to the department-wide seats, because an officer's tabs
  are all *mine*-scoped and a fresh test user legitimately owns nothing.
- `test_every_sla_state_referenced_is_a_real_selection_value` — the manager's
  queue spent a draft filtering on `("sla_state", "in", ("breached", "late"))`.
  Neither value exists in `SLA_STATE_SELECTION`, the domain raised nothing, and
  the queue therefore never surfaced a single service-level breach.

**Browser, all six logins, three viewports (1366×768, 1440×900, 1920×1080).**

```
clerk    : 3 screens, 0 console errors
officer  : 3 screens, 0 console errors
approver : 3 screens, 0 console errors
manager  : 3 screens, 0 console errors
auditor  : 3 screens, 0 console errors
admin    : 3 screens, 0 console errors
```

**Payload, per seat** (composed as the reader, over JSON-RPC):

| Seat | Signals | Queue | Scopes | Agenda | Tabs | Create |
|---|---|---|---|---|---|---|
| clerk | 5 | 12 | 5 | 25 | 3 | 6 |
| officer | 5 | 25 | 8 | 37 | 3 | 6 |
| approver | 5 | 7 | 5 | 18 | 3 | 6 |
| manager | 5 | 13 | 5 | 46 | 2 | 6 |
| auditor | 4 | 16 | 4 | 46 | 2 | **0** |
| admin | 5 | 13 | 5 | 46 | 2 | 6 |

`degraded` is empty for every seat, and the auditor's zero create actions is the
read-only guarantee holding in the payload rather than in the markup.

**Arabic.** Ten catalogues, **0 untranslated entries** in every one:

```
legal_office 262 · legal_procedure 1,072 · legal_core 405 · legal_correspondence 414
legal_request 249 · legal_contract 334 · legal_litigation 441 · legal_opinion 165
legal_deadline 48 · legal_reports 195
```

Technical tokens the extractor picks up from group-by arguments (`state`,
`is_closed`, `today`) carry an identity translation, which is the convention the
suite already used — so "0 untranslated" stays a meaningful check rather than a
list of known exceptions.

**RTL.** `dir="rtl"` stamped from the payload on every screen; zero inline
`margin-left`/`padding-left` in the rendered DOM; references, dates and counts
pinned `dir="ltr"` with tabular figures. Labels no longer hardcode Arabic-Indic
digits, which had put ٣٠ beside a Western 5 on the same strip — the company is
configured for Western figures and `_digits()` follows that setting.

**Server log** since the clean restart: 0 `ERROR`, 0 `CRITICAL`, 0 warnings
other than the PostgreSQL version notice.

### Known and deliberate

- `legal.dashboard.get_desk_data` is no longer rendered by any screen. It is
  kept because its seven tests guard the shared helper layer that
  `legal.office` inherits — `_role_brief`, `_my_turn_domain`,
  `_signature_queue_domain`, the degrading search/count. Deleting it would
  delete that coverage.
- A client action reached by its own URL still needs `setDisplayName()` to
  breadcrumb correctly; both new screens call it, and so does the government
  desks screen, which had shown *غير مسمى* for its whole life as the landing
  page.

---

## 11. Evidence

| Path | What |
|---|---|
| `before-office/` | 120 renders, 6 roles × 5 screens × 3 viewports + `report.json` |
| `after-office/` | The same sweep against the redesign |
| `scripts/legal_ui_capture.py` | The harness, re-runnable |
| `scripts/legal_stamp_view_class.py` | The view-class stamper, `--check` for CI |
