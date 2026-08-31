# legal_core — end-to-end audit (BEFORE state)

Audited: models (`legal_jurisdiction`, `legal_gov_body` + type + contact, `legal_entity` + form + identifier + kind, `legal_signatory`, `legal_document`, `legal_document_type` + kind + grade, `legal_expiry_mixin`, `res_company` extension), all 7 view files, menus, the three security files, data files and the backend SCSS, against the local Odoo 19 source (`odoo-19.0/`) and the live `legal_dept` database on :8090.

## Summary

The module is architecturally strong: the data model is thoughtful (jurisdiction as an axis, identifiers as rows, two validity models, supersession instead of edits), and it uses genuine Odoo 19 idioms correctly — `<list>` everywhere, no `attrs=`, `<chatter/>`, `models.Constraint`, `res.groups.privilege` (the 19.0 replacement for `category_id`), `_read_group` aggregation, trigram indexes, `_rec_names_search`. Demo users exist for all five roles and the role ladder in `ir.model.access.csv` is coherent, with a real read-only auditor.

The problems are at the edges where the module's own stated invariants are not actually enforced, and where the spec's non-negotiables are missed:

1. **Currency**: the company runs **USD** and `base.IQD` is **inactive** in the database, while every Monetary field in the module defaults to that inactive IQD record. The spec demands IQD.
2. **Security**: `legal.signatory` (holding the **specimen signature and official seal images** — forgery-grade assets), `legal.entity.identifier` and `legal.gov.body.contact` have **no `company_id` and no record rules**; any clerk of any company can read and export every signature/seal in the system. `legal.jurisdiction.company_ids` is declared but never enforced by a rule.
3. **The "never deleted" register is deletable**: `legal.document.entity_id` is `ondelete="cascade"`, so deleting a `legal.entity` (managers hold unlink) SQL-cascades the entire document register past the `unlink()` guard.
4. **The stored expiry state never advances**: no cron recomputes `expiry_state`/`start_by_date` on `legal.document` (the legal_procedure crons cover case/obligation/POA only), so documents never transition valid→expiring→expired unless someone happens to write them — and the "Renewals Due" action, the list decorations, the search filters and the legal dashboard tile all read that stale stored field.
5. **Arabic-first is not delivered**: no `i18n/` folder at all; with `ar_001` (RTL) active, every label, menu, filter and helper paragraph renders in English.
6. **Company letterhead settings are unreachable**: the `res.company` fields the letter report prints are exposed in no view anywhere in the suite.

| Area | Current | Problem | Severity | Target |
|---|---|---|---|---|
| Currency / spec | Company currency = USD; `base.IQD` inactive; all Monetary defaults point at inactive IQD | Spec mandates IQD; money renders in USD, IQD unselectable in dropdowns | critical | Activate IQD, set it as company currency, keep IQD defaults |
| Security: signatory/seal | `legal.signatory` has no `company_id`, no record rule; specimen signature + seal images readable by every clerk group-wide | Cross-company leak of forgery-grade assets; violates "strict server-side security" | critical | Add `company_id` (related entity_id.company_id, stored) + company rule; restrict image read (separate model or groups) |
| Security: identifiers/contacts | `legal.entity.identifier`, `legal.gov.body.contact` unscoped, no rules | Company file numbers and personal contact data leak across companies | high | company_id related-stored + global company rules |
| Register integrity | `entity_id = Many2one(..., ondelete="cascade")` on `legal.document` while `unlink()` raises | Deleting an entity silently destroys its whole document register, bypassing the guard | high | `ondelete="restrict"` on entity_id (and archive entity instead) |
| Expiry lifecycle | `expiry_state`/`start_by_date` stored computes; no ir.cron recomputes them daily | Boards, filters, decorations and dashboard tile go permanently stale | high | Daily cron flushing `_compute_expiry_state` over open documents |
| Arabic / i18n | No `i18n/` directory; source strings English | Arabic-first RTL UI shows English everywhere | high | Ship `i18n/ar.po` (or ar_001) covering fields, menus, views, help |
| Letterhead settings | `res_company.py` adds 8 fields; no view exposes them | Manager cannot configure the letterhead/numerals without dev mode | high | res.config.settings page or company form extension |
| Supersession | `_supersede_previous()` fires on every create, no date comparison | Backfilling history retires the current card in favour of the older one; ownerless docs of a type supersede each other company-wide | high | Compare issue/expiry dates; require same owner (both empty = both empty); import-context opt-out |
| Audit trail | `expiry_date`, `notice_days`, state edits by clerks untracked (mixin fields lack `tracking=True`) | "A renewal never edits" is only a docstring: silent expiry overwrites leave no chatter trace | high | tracking on expiry fields; readonly-after-active policy or approver gate |
| UX: cancel path | `action_archive_cancelled` exists (`legal_document.py:256`) but no button in the form | Error message tells users to "mark it cancelled with a reason" — no UI path exists | medium | Header button + reason wizard |
| UX: search views | `legal.entity`, `legal.signatory`, `legal.jurisdiction` have no search view | No filters/group-bys on the entity register at all | medium | Search views with jurisdiction/form/foreign-branch filters |
| Constraints | `UNIQUE(code, company_id)` with NULL company on body/doc-type | Shared records can duplicate codes (NULLs are distinct in Postgres) | medium | Unique index with `COALESCE(company_id, 0)` or two partial indexes |
| Dead config | `legal.jurisdiction.company_ids` never read by any rule | Help text promises per-company scoping that does not happen | medium | Record rule or drop the field |
| translate=True on data | Contact `name`/`role`/`section`, entity `address`, identifier `section`, `replacement_reason`, notes | Business data (even person names) stored per-language; entered in Arabic UI, absent in English UI | medium | Remove translate from operational data fields |
| Sequences | No `ir.sequence` anywhere; documents have no reference | Register rows identified by free-text name only | medium | Document reference sequence (e.g. DOC/2026/00001) |
| Tests | `legal_core/tests/` is an empty directory | Supersession, expiry buckets, signatory defaulting untested | medium | Unit tests for the load-bearing logic |
| Deprecated API | `_check_recursion()` used twice | Deprecated since 18.0 (`odoo/orm/models.py:5686`); logs warnings | low | `_has_cycle()` |
| Dead SCSS | `.o_legal_stale` referenced by nothing | The module's only SCSS rule is dead code | low | Use it (verification_status) or delete |
| Kanban colour | `colour` field loaded, never applied; non-standard name | Cards ignore the configured colour | low | `highlight_color`/`color` wiring, rename to `color` |
| List polish | signatory `decoration-warning="valid_to != False"`; `has_grades` unused; grade_id visibility hack | Future-dated signatories flagged as warnings; Grade shown on ungraded types | low | Compare valid_to to today; use `has_grades` for visibility |

## Detailed notes

### 1. Currency (critical — spec)

- Live DB: `res_company` id 1 (`شركة الرافدين...`) has `currency_id` → **USD**; `res_currency` `IQD` is **inactive**.
- Every Monetary default in the module points at that inactive record: `legal_entity.py:30-33` (`legal.entity.form.currency_id`), `legal_entity.py:113-116` (`legal.entity.capital`), `legal_document_type.py:49-52` (`legal.licence.grade`), `legal_document.py:72-75`.
- `env.ref("base.IQD", raise_if_not_found=False)` returns the inactive record, so defaults "work", but the currency cannot be picked in any dropdown and the company's own books are in dollars. Minimum-capital figures from Article 28 (`data/legal_document_kind_data.xml:93-145`) therefore display against a currency the user cannot otherwise use. The company/currency itself is configured by `legal_iq_demo/data/demo_company.xml`, but the BEFORE state as shipped violates the IQD requirement.

### 2. Multi-company and confidentiality gaps (critical/high — security)

- `legal.signatory` (`legal_signatory.py:20-78`) stores `specimen_signature` and `stamp_image` (`:45-54`). The model has **no `company_id`** and appears in **no record rule** (`security/legal_core_rules.xml` covers only gov body, doc type, entity, document). CSV (`ir.model.access.csv:28-30`) gives every clerk read. Result: in a multi-company deployment any legal clerk of any company can open Configuration → Entities → Signatories & Seals (or export via RPC) and obtain every company's seal and signature images — the exact assets that constitute an Iraqi official letter (the module's own docstring, `legal_signatory.py:7-12`). Even single-company, seal images readable by every clerk deserves a deliberate decision.
- `legal.entity.identifier` (`legal_entity.py:192-233`): no company_id, no rule — tax file numbers, registration numbers of all companies visible to all.
- `legal.gov.body.contact` (`legal_gov_body.py:33-58`): no company_id, no rule; body itself is company-scoped but its contacts are not (searchable directly via RPC even without a menu).
- `legal.jurisdiction.company_ids` (`legal_jurisdiction.py:39-43`) promises "leave empty to make available to every company" but no `ir.rule` reads it — the field is decorative.
- The rules that do exist are correct: global company rules for body/type/entity/document (`legal_core_rules.xml:10-36`), and the confidential-document pair (`:47-59`) composes correctly (group rules OR-combined; manager/auditor get `[(1,'=',1)]`). One operational hole: a clerk who *creates* a confidential document for a body they do not officer loses read access to it the moment it is saved, and a confidential document with no `issuing_body_id` is invisible to everyone below manager.

### 3. The cascade that empties the "permanent" register (high)

- `legal_document.py:44-51`: `entity_id = fields.Many2one("legal.entity", ondelete="cascade")`.
- `legal_document.py:242-254`: `unlink()` raises unconditionally — "a document that was real is archived, never deleted".
- But deleting a `legal.entity` (manager has `perm_unlink=1`, `ir.model.access.csv:20`) cascades at the SQL level; Python `unlink()` of the documents is never called. One entity delete silently destroys the register the module promises is permanent. `ondelete="restrict"` is the behaviour the docstring describes.
- Separately, the unconditional `unlink()` means a mistyped record created seconds ago can never be removed by anyone, including the admin — no context escape hatch, no grace period. Defensible, but it will also make demo/test cleanup and genuine data-entry mistakes permanent archive noise.

### 4. Stored expiry state with no clock (high)

- `legal_expiry_mixin.py:75-115`: `expiry_state` and `start_by_date` are stored computes depending on `expiry_date`, `notice_days`, `renewal_lead_days` — nothing time-based triggers them.
- legal_core ships no cron; `legal_procedure/data/legal_procedure_cron.xml` defines exactly four crons (case scan, obligation generate, obligation late, POA expire) — none touches `legal.document`.
- Consumers of the stale value: list decorations and badge (`legal_document_views.xml:8-31`), the "Renewals Due" action domain (`:170`), search filters (`:118-122`), and the dashboard tile (`legal_procedure/models/legal_dashboard.py:1157` prefers `expiry_state` when present).
- The mixin's own docstring (`:28-33`) acknowledges the hazard and keeps `_is_expired()` live for hard gates — good — but the *boards* are the product here, and they will show "Valid" forever on an untouched record. The live DB shows 0 inconsistent rows today only because the demo data was written recently. Target: a daily cron that recomputes the two stored fields over `active` documents (idempotent, `_commit_progress`-aware like the legal_procedure ones).
- Minor related inconsistency: `days_to_expiry` computes 0 for no-expiry documents but `_search_days_to_expiry` (`:122-135`) translates to a bound on `expiry_date`, which excludes NULLs — compute and search disagree on no-expiry rows (harmless in shipped filters, which guard on `expiry_state != 'no_expiry'`). The docstring claims it "inverts the operator" but the map is the identity (the code is right; the comment is wrong).

### 5. Arabic-first / i18n (high — spec)

- Active languages in DB: `ar_001` (RTL) and `en_US`. legal_core has **no `i18n/` directory** (compare `dma_accreditation/i18n` in the same addons tree), so all field strings, menu items ("Legal", "Registers", "Company Documents"…), filter labels, notebook pages, alert paragraphs and action help render in English for the Arabic user.
- The bilingual *data* design (separate `name`/`name_en` on entity, signatory, doc type; Arabic defaults like `salutation`, `legal_letterhead_line1`) is genuinely good and correct for letterheads — the missing layer is the UI terms .po file.
- Conversely, `translate=True` is applied to operational-data fields where it hurts: `legal.gov.body.contact.name` (`legal_gov_body.py:50` — a *person's name*), `role`, `section`, `note`; `legal.entity.address`/`activity_description`; `legal.entity.identifier.section`/`note`; `legal.document.replacement_reason`. Values entered under one UI language surface as source-language fallbacks in the other and diverge on edit. These should not be translatable.

### 6. Unreachable company configuration (high)

- `res_company.py:16-48` defines `legal_entity_id`, four letterhead lines, logo, `legal_numeral_system`, `legal_show_hijri`. They are consumed by `legal_correspondence/report/report_official_letter.xml:15-31`, `legal_correspondence/models/legal_correspondence.py:997,1016` and `legal_dashboard.py:174` — but **no view in any legal module** extends the company form or adds a settings page (grep over `legal_*/views/*.xml`: zero hits for res.company). Only `legal_iq_demo` sets them via XML. A manager changing the department name on the letterhead needs developer mode. The `legal.entity` docstring's promise (`legal_entity.py:56-59`) that "the company's own entity is created automatically" is likewise implemented nowhere in code — only demo data links it.

### 7. Supersession semantics (high)

- `legal_document.py:199-240`: every `create()` calls `_supersede_previous()`, which retires any other active, un-superseded document of the same type/company (narrowed by entity and/or partner *only when the new record has them*).
  - **Order sensitivity**: no comparison of `issue_date`/`expiry_date`. Backfilling the archive — precisely the "what were we operating under in March" scenario the class docstring sells — in chronological-import order is fine, but recording last year's card after this year's (the natural order when digitising a paper file: you find the old one later) marks the *current* card superseded by the *older* one, flips `is_current`, and posts a wrong chatter message.
  - **Owner symmetry**: if the new document has neither `entity_id` nor `partner_id`, the domain (`:217-227`) is just type+company+active, so it retires *every* ownerless document of that type; and a new entity-owned doc will happily supersede an ownerless one of the same type but not vice versa.
  - Target: only supersede when the new document's `issue_date`/`expiry_date` is not earlier than the old one's; match owners exactly (including both-empty); provide a context key for imports.
- `is_current` (`:88-94, 126-129`) ignores `active`: an archived-but-active-state document still counts as current for the checklist domain.

### 8. Tracking / immutability (high)

- The register's core claim is that renewals never edit. Yet: clerk has `perm_write=1` on `legal.document` (`ir.model.access.csv:40`); the mixin fields `expiry_date`, `notice_days`, `renewal_lead_days` carry no `tracking=True` (`legal_expiry_mixin.py:43-61`), so overwriting an expiry date — the exact failure the docstring names (`legal_document.py:20-24`) — is silent in chatter. `name`, `number`, `state`, `issue_date`, `document_type_id`, `issuing_body_id` *are* tracked; the one field the design document calls sacred is not. `grade_id`, `entity_id`, `partner_id`, `confidential` also untracked.

### 9. Views — convention conformance (good) and UX issues

Conventions verified against local source: all list views use `<list>`; visibility uses Python-expression attributes (`invisible="channel == 'paper'"`), never `attrs=`; `<chatter/>` used on gov body, entity, document forms; `column_invisible` used correctly in sub-lists; `optional=` used liberally; `models.Constraint` matches `odoo/orm/table_objects.py:79` API; `res.groups.privilege` + `privilege_id` matches 19.0 (`legal_core_security.xml:29-34`). No issues there.

UX findings:

- **Document form** (`legal_document_views.xml:35-104`): header has only the statusbar — no button for `action_archive_cancelled`, no "Renew" (create-superseding-copy) helper even though the whole model is built around it. `grade_id` visibility (`:56`) is `not grade_id and not document_type_id` — the Grade field shows for every typed document even when the type has no grades; the stored `has_grades` field (`legal_document_type.py:165`) exists for exactly this and is used nowhere. `days_to_expiry` in the list is non-stored, hence unsortable ("Days Left" column invites sorting).
- **Statusbar**: `statusbar_visible="active,superseded"` hides `cancelled` — a cancelled doc shows an empty-looking statusbar.
- **Entity** (`legal_entity_views.xml`): no search view at all — the register of legal persons cannot be filtered by jurisdiction, form or foreign-branch, nor grouped. Signatory and jurisdiction likewise lack search views.
- **Signatory list** (`legal_signatory_views.xml:14`): `decoration-warning="valid_to != False"` flags a signatory whose mandate runs to 2030 as a warning today.
- **Gov body kanban** (`legal_gov_body_views.xml:121-148`): `colour` is fetched but never applied (no `highlight_color=`), and the field name deviates from Odoo's `color` convention that kanban/tags machinery expects.
- **Jurisdiction form** (`legal_jurisdiction_views.xml:18-43`): no archived ribbon, no chatter (fine for config), but also no `active` toggle — archiving only via list action menu. Same for most config forms.
- **Attachments**: `many2many_binary` on `attachment_ids` works, but attachments land with `res_id=0`; combined with the confidential rule they are *not* covered by document confidentiality (ir.attachment access follows its own rules) — a confidential document's scans are less protected than the document row. Worth a deliberate design in the redesign.

### 10. Menus

- Structure is sane (`legal_core_menus.xml`): one root "Legal" (`:12-15`), Registers + Configuration (manager-gated `:48-52`). Issues: "Government Bodies" reachable twice (Registers `:40-44` and Configuration → Government Bodies → Bodies `:59-63`) via the *same action* — the config copy could open the list-only editable view instead; config child names ("Bodies", "Entities", "Documents") are terse to the point of ambiguity next to the register menus; everything English-only (see i18n). Root menu name "Legal" vs. app identity "Legal Department" — pick one for the redesign.
- Sequence 45 for the root menu will interleave with other apps; acceptable.

### 11. Data model details (mostly good, some polish)

- Good: `_parent_store` + `parent_path` + recursion constraint on jurisdiction and body; trigram indexes on searched chars; `identifier_index` stored trigram for search-by-any-number (`legal_entity.py:125-131`); `_rec_names_search` everywhere; jurisdiction-coherence constraint on identifiers (`legal_entity.py:245-270`); `_default_for` signatory selection logic (`legal_signatory.py:113-130`); `_plan_days` fallback ladder (`legal_gov_body.py:219-231`, matches `resource_calendar.py:892` signature).
- `UNIQUE(code, company_id)` on `legal.gov.body` (`legal_gov_body.py:202-204`) and `legal.document.type` (`legal_document_type.py:193-195`): Postgres NULLs are pairwise-distinct, so two *shared* bodies can share a code — and shared is the default (no `default=lambda self: self.env.company` on either). Content-pack `code` keys can silently collide. Same class of issue on `legal.document`'s `UNIQUE(number, document_type_id, company_id)` — acceptable there (number nullable is intended).
- Deprecated `_check_recursion()` at `legal_jurisdiction.py:54` and `legal_gov_body.py:208`; deprecated since 18.0 per `odoo-19.0/odoo/orm/models.py:5686-5688` (emits warnings). Use `_has_cycle()`.
- `legal.licence.grade` has a `code` but no unique constraint (unlike every other coded model) — inconsistent.
- `legal.gov.body` lacks `mail.activity.mixin` (only `mail.thread`) — no scheduled activities on a body ("chase the directorate on Sunday").
- No `ir.sequence` in the module; `legal.document` has no reference field. (A `legal.sequence.mixin` exists in `legal_procedure` — core's register predates it and never got one.)
- Empty `report/`, `wizard/`, `tests/` directories ship in the module — the tests one being empty is the finding; the other two are just clutter.

### 12. SCSS

- `static/src/scss/legal_backend.scss` contains exactly one class, `.o_legal_stale` (`:7-13`), referenced by no view, template or JS in the entire addons tree (grep: zero hits). The stated purpose (flagging unverified shipped config) is served in views by badge decorations instead. Dead asset — delete it or actually apply it to `last_verified_on`/`verification_status` renderings. For the "professional dense enterprise UI" target, expect this file to grow substantially in the redesign; today there is effectively no custom UI layer in core (consistent with the suite keeping OWL work in `legal_procedure`'s dashboard).

### 13. What is right (keep in the redesign)

- Jurisdiction as a first-class axis; identifier-per-(entity, body, kind); two validity models incl. freshness; supersession concept (fix the mechanics, keep the idea); the five-role ladder with data-driven per-body officer visibility instead of group-per-ministry (`legal_core_security.xml:4-21`); read-only auditor done with real ACLs and demo users for all five roles; `noupdate="1"` content-pack discipline with the migration rationale documented (`data/legal_jurisdiction_data.xml:3-13`); `_is_acceptable_on(date)` future-dated validity checks for tender readiness.
