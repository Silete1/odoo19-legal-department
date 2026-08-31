# Audit — legal_correspondence (KEY=corr)

Audited: 2026-08-31, BEFORE state. Server http://localhost:8090, db `legal_dept` (module `installed`, 19.0.1.0.0; 14 correspondence rows, all `registered`, 2 registers OUT/IN, 4 templates, 4 snapshots, 0 archived).

## Summary

`legal_correspondence` is the strongest-written module in the suite: the editable-sequence mixin is a competent port of `account`'s `sequence.mixin` (savepoint-locked allocation, format deduction, year reset deduced from the number's own shape), the void-instead-of-delete design is real (unlink of a non-draft raises, the void wizard forces a reason, the number survives), and the QWeb official letter is structurally an authentic Iraqi كتاب (العدد/التاريخ block on the right, م/ subject, تحية طيبة وبعد، signature stack with the ختم rotated over the specimen, نسخة منه إلى bottom-left, page-x-of-y footer). Tests (337 lines) genuinely cover the register rules.

But the register-integrity claims in the manifest do **not** all hold against the server-side code they claim to be enforced by:

1. **The immutability lock is bypassable by any clerk over RPC** — `state` itself is not a locked field, so `write({'state': 'draft'})` on a registered entry unlocks number/date/register/direction and even `unlink()`; separately, the `legal_allocating_number` **context key disables the lock entirely and context is client-controlled** in every `call_kw` RPC. Re-registering afterwards re-runs `_after_registration` (duplicate chatter posts, duplicate `legal.document` rows).
2. **The "gap check" advertised in the manifest does not exist anywhere in the code** — the provisioned `no_gap` `ir.sequence` is never used for allocation (dead configuration), and a clerk may type any number, creating silent holes (live data already shows out-of-order typed numbers: ق/2026/0781 registered before ق/2026/0166).
3. **wkhtmltopdf is not installed on this machine** (`where.exe` empty, no Program Files install, no config/param override, zero log mentions) — the flagship deliverable, the official-letter PDF, **cannot be produced at all**; `action_snapshot_pdf` raises a UserError and Print degrades to browser HTML with the 55 mm pre-printed-paper margin lost.
4. **No i18n at all** (no `i18n/` directory in this module or `legal_core`) with `ar_001` active; every label is a hardcoded "صادر - Outgoing" bilingual composite, and `subject` is wrongly `translate=True` on business data.
5. **The reply clock has no engine** — no cron, no activity, no notification; "late" exists only while somebody is looking at the Awaiting Reply list.

Year reset: **verified genuinely implemented and tested** (deduced from number shape, borrows previous period's format). Void/renumber protection: **verified** against straightforward writes. Number/date immutability: holds only against naive writes (see finding 1).

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Register integrity — write lock | `write()` refuses changes to `_LOCKED_ONCE_REGISTERED` unless `state == 'draft'` or ctx `legal_allocating_number` | `state` is not locked: clerk writes `{'state':'draft'}` → edits number/date/book/direction → deletes or re-registers; context key is client-settable over RPC; un-void (`void`→`registered`) also unguarded | critical | Lock state transitions server-side: registered may only go to void (via reason), void is terminal; replace the context flag with an internal-only mechanism (e.g. `self.env.su`-guarded or a private attribute), and block unlink for any row that ever had a number |
| 2 | Printable letter — PDF engine | `qweb-pdf` reports + two paperformats; `action_snapshot_pdf` button | wkhtmltopdf absent on this machine: no PDF can be rendered; the 55mm pre-printed top margin only exists in the paperformat, so HTML fallback prints over the letterhead band | critical | Install wkhtmltopdf 0.12.6 (or move the suite to a host that has it) and verify Arabic output end-to-end; surface engine status on the letter form |
| 3 | Register integrity — gap check | Manifest: "it is gap-checked". Code: nothing; `no_gap` ir.sequence provisioned but never consumed | Clerk-typed numbers create silent holes and out-of-order chains (live rows prove it); the claim a redesign will be judged against is false | high | Either implement a real gap/continuity report (per register, per year: missing numbers, date-vs-number order violations) or delete the claim; remove or actually use the dead ir.sequence |
| 4 | Register integrity — archiving | `active` Boolean, default True, not in the locked list | Any clerk archives a registered entry: it vanishes from every board, list and chase with no void, no reason, no trace in the book | high | Forbid `active=False` on non-draft entries (or on any numbered entry); archiving a book row is exactly the "deleted row" the module's own prose forbids |
| 5 | Registration bypass | `action_register()` runs `_check_ready_to_register()`; but `create(state='registered')` / `write({'state':'registered'})` do not | RPC/import can register a non-contact-note without a register book; `_get_starting_sequence` on an empty register yields `2026/0001` — numbered entries that belong to **no book**; re-registration re-runs `_after_registration` duplicating chatter + `legal.document` rows | high | Call `_check_ready_to_register` from `_after_registration` (both create and write paths); make `_after_registration` idempotent |
| 6 | Arabic / i18n | No `i18n/` dir anywhere in the suite; labels hardcoded as "وارد - Incoming"; `subject` and register/template `name` `translate=True` | Spec demands Arabic-first RTL **with working translations**; ar_001 users get a mixed bilingual UI that cannot be corrected via PO files; `translate=True` on `subject` makes a business fact language-dependent (search/reporting differ per active lang) | high | Ship real ar.po/en.po, single-language source labels; drop `translate=True` from business-data fields (subject) |
| 7 | Reply-deadline mechanics | `reply_due_on` stored compute (working days via body calendar, moved by telephone promises — good design); `reply_state` computed+searchable | No cron, no `mail.activity`, no notification when an entry turns late; the module's own selling point ("the chase") never fires; also no integration with any suite-wide deadline model (none exists) | high | Daily cron creating/updating activities for the responsible on late entries; feed a unified deadline surface for the role dashboard |
| 8 | Arabic PDF correctness | SCSS: `font-family: "Segoe UI", Tahoma, Arial`; `dir="rtl"` + `/*rtl:ignore*/` guards (correct); letterhead from company fields; العدد/التاريخ block present; optional Hijri, optional Arabic-Indic digits | No embedded Arabic font (`@font-face`) — glyph shaping depends entirely on the server host's fonts; on a Linux deploy without Tahoma the letter degrades to tofu/unshaped forms | medium | Embed a proper naskh face (Amiri/Noto Naskh Arabic) in `web.report_assets_common` with `@font-face`, keep system fallbacks |
| 9 | Direction consistency | `direction` on both register and entry; `_onchange_kind_id` always overwrites direction from kind | No constraint that `entry.direction == register_id.direction`; kind onchange can silently flip an IN-book entry to `out`; the book can mix directions and the immutable `direction` may be frozen wrong | medium | `@api.constrains('register_id','direction')` equality check (contact notes exempt); stop the kind onchange overriding a direction implied by the chosen book |
| 10 | XSS surface | `body_html`, `snapshot_html`, `body_template` all `sanitize=False`; report renders them via `t-out` (Markup) | Any clerk stores arbitrary HTML/JS in `body_html` that renders in other users' browsers (form + snapshot page); template body is manager-edited but letter body is clerk-writable | medium | `sanitize_attributes`/style-preserving sanitize on `body_html`/`snapshot_html`; keep `sanitize=False` only where the print pipeline truly needs it and strip scripts on render |
| 11 | Secrecy lifecycle | `secrecy` editable at any state; auditor group sits in the "sees everything" rule (legal_correspondence_rules.xml:114) | An officer can downgrade سري→عادي post-registration exposing the entry to all clerks (tracked, but not gated); read-only auditor sees all confidential entries incl. chatter — a decision that should be explicit | medium | Lock `secrecy` after registration (or gate the downgrade to manager); document/confirm the auditor-sees-secret decision with the client |
| 12 | Issued-document side effect | `_create_issued_document` creates `legal.document` at registration | `legal.document` has UNIQUE(number, type, company): a second letter carrying the same their_number of the same type aborts the whole registration with a raw constraint error; plus duplicates on re-registration (finding 5) | medium | Pre-check existence; link the correspondence to the found/created document instead of blind create |
| 13 | Search view usefulness | Good filter set (direction/state/reply/promised/returns/secret/mine/this-year, 7 group-bys, combined number-or-subject field) | Missing: due-date range filters ("due this week/overdue N days"), group-by responsible, group-by reply_state; `body_reference`/`portal_ref` not searchable; list header hardcodes "رقم الصادر" which is wrong for وارد rows | medium | Add due-date filters + the missing group-bys and searchable fields; neutral column label (الرقم في سجلنا) |
| 14 | Mail-room wizard data slot | `action_register` stores the reception remark in `body_html` ("Letter Text") | An incoming letter's mail-room note masquerades as the letter's body text — wrong slot; would print as body if the entry ever became outgoing in a thread copy | low | Post the remark to chatter or a dedicated `reception_note` field |
| 15 | Void wizard edge | Wizard only refuses already-void entries | RPC can void a draft (no number — nonsense row in the book); `replacement_id` is not validated to be a live entry | low | Require `state == 'registered'`; validate replacement is registered and not self |
| 16 | Report details | QR guarded by `t-if=...verification_token` yet src falls back to `o.our_number` (dead code); `gov_body_id` optional so a letter can print with an empty addressee block and default salutation | Dead fallback confuses; a letter with no addressee should not print | low | Require gov_body for printing outgoing; drop the dead fallback |

## Detailed notes

### 1. The immutability lock and its three bypasses (critical)

`custom_addons/legal_correspondence/models/legal_correspondence.py:750-792` — `write()` checks `_LOCKED_ONCE_REGISTERED = ("our_number", "our_date", "register_id", "direction")` (line 77) but:

- **State flip**: the guard is `if record.state == "draft": continue` (line 763). `state` is not itself locked, and there is no transition guard anywhere, so `entry.write({'state': 'draft'})` succeeds on a registered entry. After that every locked field is editable and `unlink()` (line 794, refuses only non-draft) deletes the row. The docstring's claim "the refusal has to be here [because readonly stops nothing over RPC]" (lines 753-757) is defeated by a two-step write available to the same RPC caller.
- **Context key**: line 758 `allocating = self.env.context.get("legal_allocating_number")` — the whole lock stands aside when this key is present. Odoo passes the client's `context` dict verbatim into `call_kw`; any authenticated clerk can send `{"context": {"legal_allocating_number": true}}` and rewrite the number/date/book of any registered entry in one call.
- **Un-void**: `write({'state': 'registered'})` on a void entry is accepted; it also re-triggers `_after_registration` (line 790) → duplicate "Registered as..." chatter and, for issued-document kinds, a second `legal.document` row (`_create_issued_document`, lines 890-913).

Tests cover only single-field writes on a registered entry (tests/test_legal_correspondence.py:141-151), which is why this passes CI.

### 2. wkhtmltopdf absent (critical)

- `where.exe wkhtmltopdf` → nothing; no `C:\Program Files\wkhtmltopdf`; nothing in `.venv_odoo19/Scripts`; `odoo19_legal.conf` has no override; `ir_config_parameter` has no `report.url`/`webkit` key; `odoo_legal.log` (the live 8090 server, PID 18012, started 2026-08-30 23:18) contains zero wkhtmltopdf mentions.
- Consequences: both `ir.actions.report` records (report/legal_correspondence_reports.xml:51-73) are `qweb-pdf` and will fall back to HTML-in-browser; the two paperformats (report/legal_correspondence_paperformat.xml) — whose 55 mm top margin **is** the pre-printed-letterhead feature — never apply in HTML fallback; `action_snapshot_pdf` (models/legal_correspondence.py:1063-1098) raises its wrapped UserError. The module even anticipates this ("a department whose server has no PDF engine must still be able to register letters") but the audited product spec requires a working printable letter.

### 3. Gap check: claimed, not implemented (high)

- `__manifest__.py:18` — "it is gap-checked, because a register with a hole in it is a register somebody has been editing". `grep -rn gap` over the module finds only prose. Neither the mixin (`legal_sequence_mixin.py` — which explicitly **dropped** upstream's `_is_end_of_seq_chain`, line 50) nor the model nor any view/report inspects continuity.
- `legal_register._provision_sequence` (models/legal_register.py:144-166) creates a `no_gap`, `use_date_range` `ir.sequence` per book — but allocation never touches it (`_set_next_sequence` runs the mixin chain); `sequence_id` contributes only `padding` to `_get_starting_sequence` (legal_correspondence.py:710). Dead configuration that *looks* like the integrity feature.
- Live evidence (SQL, read-only): register 1 (OUT) contains typed numbers ق/2026/0166 (id 119, created after id 114's ق/2026/0781), 0412, 0498, 0611, 0655, 0702, 0738, 0744, 0781 — hundreds of silent holes, none reported anywhere.

### 4. Archiving = uncontrolled soft delete (high)

`active = fields.Boolean(default=True)` (legal_correspondence.py:412) is writable by any clerk (ACL row `access_legal_correspondence_clerk` = 1,1,1,1) and is not in `_LOCKED_ONCE_REGISTERED`. Archived entries drop out of every action, board, chase and default search. Numbering safety happens to survive (the `_get_last_sequence` raw SQL ignores `active`), but the visible register — the thing the module calls "evidence" — silently loses rows. 0 archived rows in the DB today; the hole is structural.

### 5. Registration without validation (high)

`_check_ready_to_register` (legal_correspondence.py:817-840) runs only inside `action_register`. `create(vals with state='registered')` (used legitimately by both wizards) and `write({'state':'registered'})` skip it. A non-contact-note without `register_id` then reaches `_after_registration` → `_set_next_sequence` → `_get_last_sequence_domain` returns `WHERE FALSE` → `_get_starting_sequence` on the empty register recordset builds `"%s/%s" % (year, "0000")` → a numbered entry (`2026/0001`) in **no book**, invisible to every per-register chain.

### 6. i18n (high)

No `i18n/` directory in `legal_correspondence` (or `legal_core`); `res_lang` shows `ar_001` + `en_US` active. All selection labels, view strings, menu names are bilingual composites ("صادر - Outgoing", "مسودة - Draft") baked into source (e.g. legal_correspondence.py:100-115, 372-382; menus XML). This is un-fixable by translators, doubles every label's width in dense lists, and `subject`/`name` `translate=True` (legal_correspondence.py:192-194, legal_register.py:35) put business data behind the translation machinery.

### 7. Reply-deadline mechanics (high, with genuine strengths)

Verified working and well-designed: `reply_expected/reply_days` are stored computes overridable per entry (correct rationale at lines 275-278); `reply_due_on` plans through `gov_body_id._plan_days` (working calendar) and is moved by the **max registered promise** from contact notes (lines 452-483) — the promise mechanic is real and tested (tests:100-123); `is_substantive_reply` correctly excludes receipts/reminders/contact notes so a وصل never closes the clock (tests:207-236); `_search_reply_state` (lines 523-557) expresses the volatile state as stored-column domains — the "late" filter is real SQL, not in-memory.

Missing: any *active* consequence. No `ir.cron` in the module, no activity scheduling, no escalation, no digest. Late entries surface only in `action_legal_correspondence_awaiting`. For the target product's unified-deadlines + role-dashboard requirement, this board is an input, not a solution.

### 8. The QWeb letter and Arabic PDF (medium once the engine exists)

`report/report_official_letter.xml` + `static/src/scss/legal_letter.scss`:

- Structure is right: rtl page div (`dir="rtl"`, scss `/*rtl:ignore*/` guards against rtlcss double-flip — correct technique), العدد/التاريخ right block + كتابكم المرقم left (lines 153-170), letterhead only on the `drawn` variant (paperformat pair is the correct wkhtmltopdf approach), draft watermark page for unregistered entries (141-147), ت table, signature stack with stamp overlay, نسخة منه إلى, footer صفحة x من y with `span.page/span.topage`.
- Fonts: `"Segoe UI", Tahoma, Arial` — host-dependent; no `@font-face`. Works on this Windows host (once wkhtmltopdf exists), tofu-risk on Linux deploys. Embed Amiri or Noto Naskh Arabic.
- Numerals/Hijri: `_localise_numerals` (company setting, western default) and `_format_letter_date` with arithmetic Hijri (validated by tests:328-336) are thoughtful and correct.
- `letterhead` letterhead uses `company.legal_letterhead_*` fields (exist in legal_core/models/res_company.py:22-34) — but nothing in this module's UI edits them; if legal_core's settings view doesn't expose them the drawn letterhead is unreachable configuration (check under legal_core audit).

### 9-12. Model-level mediums

- Direction: no `entry.direction == register_id.direction` constraint; `_onchange_kind_id` (lines 571-584) unconditionally overwrites direction after `_onchange_register_id` set it.
- `sanitize=False` trio: legal_correspondence.py:195, 220-229; legal_letter_template.py:70-77.
- Secrecy: not locked post-registration; auditor in the see-everything rule (security/legal_correspondence_rules.xml:111-116). Note the *good* part: the sudo sequence lookup + rule asymmetry (rules file comment, lines 96-101) is correct — hidden secret numbers still block reuse.
- `legal.document` UNIQUE(number, document_type_id, company_id) (legal_core/models/legal_document.py:119) vs `_create_issued_document` blind create.

### 13-16. UX / lower severity

- Search view (views/legal_correspondence_views.xml:229-274): solid foundation (see table); the `filter_domain` combined number/subject field is good practice. Missing items listed in the table. The kanban card is minimal but serviceable; calendar view on `our_date` exists. No pivot/graph views despite the module's statistics rhetoric (rounds, returns) — nothing aggregates `round` anywhere.
- Mail-room wizard (wizard/legal_correspondence_register_wizard.py:296-328): excellent six-field flow, correct defaulting; only the `body_html: self.note` slot misuse.
- Menus hang under `legal_core.menu_legal_registers` — coherent single-app structure.
- ACLs: sensible ladder (clerk full CRUD on entries — guarded by Python; config models manager-only; auditor read-only everywhere; wizards clerk-level). Registrar group (`group_legal_registrar`) + `write_group_id` Python check (`legal_register.py:191-213`) is genuinely enforced at allocation time and tested (tests:254-271).

### Verified claims scorecard (manifest vs code)

| Claim | Verdict |
|---|---|
| Void instead of delete | **Holds** (unlink guard + reason constraint + number kept; tested) — but see archiving (finding 4) and state-flip (finding 1) |
| Number/date immutability after registration | **Holds only against naive writes** — bypassable via state flip and via client-supplied context key (finding 1) |
| Year reset | **Holds** — deduced from number shape, format borrowed across periods, tested incl. typed-number continuation |
| Gap check | **Does not exist** (finding 3) |
| Clerk-typed number continues the chain | **Holds** (tested) |
| Concurrent allocation safe | **Holds in design** (unique constraint + savepoint UPDATE lock; `init()` even warns if the unique index is missing) |
