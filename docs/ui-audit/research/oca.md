# OSS Research: OCA `agreement` / `agreement_legal` and OCA `contract`

**Key:** research_oca · **Date:** 2026-08-31 · **Method:** actual model sources fetched raw
from GitHub (`raw.githubusercontent.com`) — `OCA/agreement` branch **16.0** (the richest
`agreement_legal`), branch listings for 15.0–19.0, and `OCA/contract` branch **18.0**
(Production/Stable) with manifest checks on 19.0. GitHub was fully reachable; every claim
below is from the downloaded source, with file:line references into the upstream files.

## Summary

Both OCA repositories are alive through Odoo 19 and are the two reference open-source
implementations of exactly the two halves our contracts module needs: **`agreement` +
`agreement_legal`** model the *legal document* (parties, signatures, clause structure,
versioning/amendments, stages, expiry notice), while **`contract`** models the *recurring
obligation engine* (period math, next-event dates, modification log, cron generation).

The decisive constraint: **every module inspected is AGPL-3** (manifests and file headers,
all branches checked). Our suite is **LGPL-3** (all nine `legal_*` manifests). AGPL-3 code
cannot be relicensed into an LGPL-3 module; incorporating it would force the module (and
arguably the suite that imports it) to AGPL-3. **Verdict: adopt the concepts and schema
shape — which copyright does not protect — and re-implement in our own Arabic-first code;
port no code verbatim.** The single piece intricate enough to tempt a verbatim port, the
~250-line recurrence date-math mixin, is small enough to re-derive from its documented
behaviour, and our existing `legal.obligation.schedule` already covers the four
Iraqi-specific deadline shapes the spec needs.

Our current suite has **no contract model at all** — the word "contract" appears only as a
`contract_value` Monetary on `legal.case` and a fee-rule percentage base — so the contracts
module is greenfield and free to adopt the best of both OCA designs from day one.

| Area | Current | Problem | Severity | Target |
|---|---|---|---|---|
| Contracts model | No contract/agreement model anywhere in the suite; only `contract_value` on `legal.case` (`legal_procedure/models/legal_case.py:294`) and a `percent_contract` fee base (`legal_fee_rule.py:49,131`) | Client spec requires a full contracts+obligations lifecycle; nothing exists to amend, renew, or report on | high | New `legal_contract` module modeled on `agreement`/`agreement_legal` concepts: coded, sequenced, mail.thread record with unique(code, partner, company) |
| License compatibility | OCA `agreement` 16.0–19.0, `agreement_legal` 16.0–18.0, `contract` 18.0/19.0 are all **AGPL-3**; our suite is **LGPL-3** | Verbatim porting would force AGPL on the combined work — a silent license violation if done casually | high | Concepts-only adoption, clean re-implementation under LGPL-3; record the decision. (Alternative: deliberately license the one new module AGPL-3 — legal but a policy decision to make explicitly, not by accident) |
| Lifecycle / stages | No stage or state machinery for contracts | Spec demands approval workflow (clerk→officer→approver→manager) and auditor visibility | high | `agreement_legal` pattern: server-side `state` selection **plus** configurable kanban `stage_id` with `fold` + `readonly` flag (`agreement_stage.py:25`); enforce read-only in `write()`, not via view hacks |
| Amendments / versioning | Nothing | Amendments (ملحق عقد) are core to Iraqi contract practice; without a version tree the register lies about what was agreed when | high | `parent_agreement_id` tree + `create_new_version()` copy-as-inactive-child pattern + monotonic `version`/`revision` counters (`agreement_legal/models/agreement.py:17,23,180,390`) |
| Renewal & notice | Generic `legal.obligation.schedule` exists (4 Iraqi deadline shapes) but nothing contract-linked | Expiry/notice deadlines will not reach the unified deadline board | high | `expiration_notice`/`change_notice` day-counts + stored computed `to_review_date` + cron creating activities (`agreement.py:48,266,281`) — but feed OUR unified deadline engine, not a parallel alert channel |
| Clause structure | Nothing | Generated Arabic contract text and a searchable clause register need structure, not one blob | medium | `agreement.recital` / `agreement.section` / `agreement.clause` / `agreement.appendix` with sequence + printed `title` vs internal `name`, `translate=True` HTML content |
| Parties & signatures | `legal.signatory` exists in legal_core but hangs off nothing contract-shaped | Two-sided signature metadata (who, which date, which capacity) is spec-required for POAs and contracts | medium | Both-sides pattern: partner + contact + signed-by + signed-date per side (`agreement.py:34-46`, company/partner signed dates and signed-by users) reusing our `legal.signatory` |
| Recurring obligation math | Our schedule model covers fixed-date/FYE-offset/monthly/expiry-offset | Contract payment/renewal schedules also need interval arithmetic (every N months, pre/post-paid, last-day-of-month) | medium | Re-derive the `contract.recurring.mixin` behaviour (`contract_recurring_mixin.py:33-110,162-254`): rule type incl. `monthlylastday`, interval, offset, `last_date_invoiced` → next-period chain |
| Modification log | Nothing | Auditors need an append-only "what changed" register independent of chatter | medium | `contract.modification` analog (`contract_modification.py:8-22`): date + description + notified flag, auto "start" entry on create |
| Signed document | n/a | OCA's own weakness: ONE `Binary` field for the signed copy (`agreement.py:232`) — no versioning | low | Do better: `ir.attachment` set with a "signed copy" role flag per version node |
| Odoo 19 porting hazard | n/a | `agreement_legal` 16.0 enforces stage read-only by rewriting view `attrs`/`modifiers` in `get_view()` (`agreement.py:469-507`) — `attrs` was **removed** in Odoo 17+ | medium | Never copy this; use `readonly="stage_readonly"` field expressions + a `write()` guard |
| Templates | Nothing | Repeated contract kinds (lease, service, supply) need templating | low | `is_template` flag + `template_id` + copy-from-template (`agreement/models/agreement.py:27`; `contract_template.py:19,47` NO_SYNC field-sync pattern) |

---

## 1. Repository & branch survey (verified via GitHub API)

**OCA/agreement** — branches: 15.0, 16.0, 17.0, 18.0, 19.0.

| Branch | Modules present (legal-relevant) | agreement_legal version |
|---|---|---|
| 16.0 | `agreement` (16.0.1.0.0), `agreement_legal` (16.0.2.0.4), `agreement_maintenance`, `agreement_rebate`, `agreement_sale`, `agreement_serviceprofile` | 16.0.2.0.4 |
| 17.0 | `agreement`, `agreement_account`, `agreement_legal` (17.0.3.0.1), `agreement_project`, `agreement_repair`, `agreement_sale` | 17.0.3.0.1 |
| 18.0 | `agreement`, `agreement_account`, `agreement_legal` (18.0.1.4.0), helpdesk bridges, `agreement_serviceprofile`, … | 18.0.1.4.0 |
| 19.0 | `agreement` (19.0.2.1.0), `agreement_project`, `agreement_rebate`, `agreement_sale` — **`agreement_legal` not yet ported to 19** | — |

**OCA/contract** — branches 6.1 → 19.0. `contract` is `18.0.2.5.2` **Production/Stable**
(manifest `development_status`), `19.0.1.0.3` on 19.0. Sibling modules: `contract_sale`,
`contract_variable_quantity`, `contract_payment_mode`, `subscription_oca`, etc.

**Licenses:** `agreement` 16.0 manifest → `"license": "AGPL-3"`; `agreement_legal`
16.0/17.0/18.0 manifests → AGPL-3; `agreement` 19.0 → AGPL-3; `contract` 18.0 and 19.0 →
AGPL-3. Every `.py` header carries `License AGPL-3.0 or later`. There is **no LGPL module**
among those inspected.

## 2. `agreement` base module (16.0) — the minimal core

`agreement/models/agreement.py` (89 lines):

- `_name = "agreement"`, `_inherit = ["mail.thread", "mail.activity.mixin"]`.
- `code` + `name` both required and tracked; display name `[code] name`.
- `partner_id` M2O res.partner, `ondelete="restrict"`, domain `parent_id = False`
  (commercial entities only), tracked.
- `company_id`, `active`, `is_template` (`agreement.py:27` — templates do not need a partner).
- `agreement_type_id` → `agreement.type` (name, active, sale/purchase `domain`).
- Dates: `signature_date`, `start_date`, `end_date` (all tracked).
- SQL constraint `unique(code, partner_id, company_id)` (`agreement.py:77`) — the
  register-integrity idea worth keeping.
- `copy()` suffixes the code to keep the constraint satisfied.

Small, sane, and the right skeleton for a *register* of legal documents.

## 3. `agreement_legal` (16.0.2.0.4) — the legal-document layer

`agreement_legal/models/agreement.py` is a 507-line `_inherit = "agreement"` extension.
Manifest: depends `contacts, agreement, product, web`; data includes `data/cron.xml`,
`data/ir_sequence.xml`, stage/type seed data, a QWeb PDF report, and a create wizard.

### 3.1 Versioning & amendments (the best idea in the repo)

- `version` Integer (default 1) + `revision` Integer (default 0), both `copy=False`
  (`agreement.py:17,23`).
- `write()` override auto-increments `revision` on every save (`agreement.py:444-455`).
- `create_new_version()` (`agreement.py:390`): copies the current record with
  `_get_old_version_default_vals()` → name suffixed "- OLD VERSION", `active=False`,
  `parent_agreement_id=self`, `code = "{code}-V{version}"`; then bumps `version`, resets
  `revision`. History browsable via `previous_version_agreements_ids` (One2many on
  `parent_agreement_id` with `active_test: False`) and `child_agreements_ids`
  (`agreement.py:180,205-220`).
- `parent_agreement_id` doubles as the **amendment** link ("if this agreement is an
  amendment to another agreement" — its own help text).

**Adopt:** the whole pattern, with one improvement — snapshot as an *immutable* child rather
than a mutable copy, and make "amendment" (ملحق) a distinct child kind rather than
overloading the same link for both old-versions and amendments.

### 3.2 Structured document body

Four sibling models, all `_order = "sequence"`, all with internal `name` vs printed
`title` ("The title is displayed on the PDF. The name is not."), HTML `content`, and a
computed `dynamic_content` rendered through `mail.template._render_template()` in the
partner's language:

- `agreement.recital` (`agreement_recital.py:8`) — the "whereas" preamble.
- `agreement.section` (`agreement_section.py:8`) with `clauses_ids`.
- `agreement.clause` (`agreement_clause.py:8`) with `section_id`, `ondelete="cascade"`.
- `agreement.appendix` (`agreement_appendix.py:8`).

Every one of them repeats a 5-field "placeholder builder" (`field_id`, `sub_object_id`,
`sub_model_object_field_id`, `default_value`, `copyvalue`) — copy-paste boilerplate we
should NOT reproduce; one shared mixin (or dropping the builder UI entirely) is cleaner.

**Adopt:** the recital/section/clause/appendix shape with `translate=True` content —
this is exactly what an Arabic-first generated contract needs. **Skip:** the per-model
placeholder-builder field cluster.

### 3.3 Parties, contacts, signatures

Two symmetric party blocks (`agreement.py:34-46, 84-140`):

- Counterparty: `partner_id`, `partner_contact_id` (+related phone/email),
  `partner_signed_user_id` (a res.partner), `partner_signed_date`.
- Own side: `company_id`/`company_partner_id`, `company_contact_id` (+related
  phone/email), `company_signed_user_id` (a res.users), `company_signed_date`.
- `notification_address_id` — a distinct *service address* for notices; a genuinely good
  legal-practice detail.
- `parties` HTML block with a Jinja default (`_get_default_parties`) + `use_parties_content`.
- `res_partner.py:8-30`: partner smart button + `agreements_count` via read_group.

**Adopt:** symmetric party/signature metadata + notification address; wire to our
existing `legal.signatory` (legal_core) instead of bare partner links.

### 3.4 Lifecycle: state + stage + read-only stages

- `state`: draft / active / inactive — the hard server-side axis.
- `stage_id` → `agreement.stage` with `group_expand` for kanban, default from XML ref
  (`agreement.py:357-380`); the stage model (`agreement_stage.py`) has `sequence`, `fold`,
  `stage_type`, and a `readonly` Boolean (`agreement_stage.py:25`) that freezes the record.
- Enforcement is a `get_view()` override that rewrites every field's `attrs`/`modifiers`
  JSON in the form arch (`agreement.py:469-507`). **This is a 16.0-only hack** — `attrs`
  died in Odoo 17; on 19 use `readonly="stage_readonly"` expressions plus a `write()`
  guard. Do not port.

### 3.5 Renewal / notice / review mechanics

- `expiration_notice` + `change_notice` Integer day-counts (`agreement.py:48-56`).
- `termination_requested` + `termination_date` Dates (`agreement.py:74-80`).
- `reviewed_date`/`reviewed_user_id`, `approved_date`/`approved_user_id` — lightweight
  four-eyes metadata.
- `to_review_date` = `end_date - agreement_type_id.review_days`, stored computed,
  manually overridable (`agreement.py:266-279`).
- Daily cron `_alert_to_review_date` (`agreement.py:281-303`, `data/cron.xml`): when
  `to_review_date == today`, schedules a `mail.activity`
  (`agreement_legal.mail_activity_review_agreement`) for `agreement_type_id.review_user_id`
  unless one already exists.
- `agreement.type` extension (agreement_legal `agreement_type.py`): `review_days`,
  `review_user_id`, `agreement_subtypes_ids`; `agreement.subtype` is a plain name+type.

**Adopt:** notice-days on the contract + review-days defaulted per type, but emit into
our **unified deadline engine** (`legal.obligation.schedule` shape
`offset_before_expiry`, `legal_procedure/models/legal_obligation.py:70-77` already models
"N days before a document expires") so contract renewals appear on the same board as
licence renewals — not on a second, parallel activity-only channel.

### 3.6 Attachments, products, sequence

- Signed copy: single `signed_contract` Binary + filename (`agreement.py:231-232`).
  Weak — replace with role-flagged `ir.attachment`s per version node.
- `agreement.line` (`agreement_line.py:8-20`): product/qty/uom — trivially thin; our
  contract "lines" should instead be **obligation lines** (payments, deliverables,
  notices) since we bill nothing.
- Code from `ir.sequence` "agreement" in `_fill_create_vals` (`agreement.py:427-438`).

## 4. `contract` 18.0 (Production/Stable) — the recurrence engine

Model architecture (`contract.py:22-29`, `contract_template.py:13-15`,
`contract_line.py:27-31`): `contract.contract` **inherits the real model**
`contract.template` (plus portal.mixin, mail.thread, activity); `contract.template`
inherits abstract `contract.recurring.mixin`; `contract.line` inherits
`contract.template.line` + `analytic.mixin`. Clean template→instance field sync in
`_onchange_contract_template_id` with a `NO_SYNC` exclusion list
(`contract_template.py:19`, `contract.py:246-280`).

### 4.1 The recurrence mixin — the one genuinely intricate artifact

`contract_recurring_mixin.py` (258 lines, abstract):

- `recurring_rule_type`: daily / weekly / monthly / **monthlylastday** / quarterly /
  semesterly / yearly (`:33-46`); `recurring_interval`; `recurring_invoicing_type`
  pre-paid vs post-paid (`:52`); computed `recurring_invoicing_offset`.
- Chain of stored/computed dates: `last_date_invoiced` (`:72`) →
  `next_period_date_start` (+1 day) → `next_period_date_end` → `recurring_next_date`
  (`:76-158`), all clamped by `date_end`.
- Pure `@api.model` calculators: `get_relative_delta` (`:162`),
  `get_next_period_date_end` (`:180`), `get_next_invoice_date` (`:222`) — including the
  back-calculation of a period from a *forced* next date. This is the part that takes
  three attempts to get right when written from scratch; the behaviours to replicate are
  fully visible in these ~90 lines.

### 4.2 Modification log

`contract_modification.py:8-22`: `contract.modification` — `date` (required),
`description` (required Text), `sent` Boolean, cascade M2O to contract,
`_order = "date desc"`. `contract.contract.create()` seeds an automatic **"Contract
start"** entry (`contract.py:394-416`), and changed logs trigger a follower notification
via a dedicated `mail.message.subtype` + template (`contract.py:418-436`), with a
`bypass_modification_send` context to suppress. An append-only-by-convention change
register — precisely the auditor-facing artifact our spec wants.

### 4.3 Generation cron & markers (concept only)

- `_cron_recurring_create` (`contract.py:673-705`): search by
  `recurring_next_date <= date_ref`, group by company, generate, advance dates — the
  correct shape for *any* "generate the next obligation instance" cron, invoices or not.
- Description markers `#START#`, `#END#`, `#INVOICEMONTHNAME#` localized via `res.lang`
  date_format (`contract_line.py:266-285`) — a nice touch for Arabic period labels.
- Line-vs-header recurrence toggle `line_recurrence` (`contract_template.py:47`);
  sections/notes as `display_type` lines; `monthly_recurring` normalized Monetary
  (`contract_line.py`, `_compute_monthly_recurring`) for comparable reporting.
- Everything else (journals, pricelists, fiscal positions, portal `/my/contracts`,
  `account.move` creation) is accounting machinery **we do not want** — our legal
  department tracks obligations and IQD amounts, it does not issue invoices.

## 5. License analysis — can we port code?

- **Facts:** all inspected modules are AGPL-3 (manifests, §1; every file header). Our nine
  modules declare LGPL-3.
- AGPL-3 → LGPL-3 relicensing is **not permitted** (only the copyright holders — dozens
  of OCA contributors — could). LGPL-3 → AGPL-3 is the only compatible direction.
  Porting OCA code verbatim into `legal_contract` while its manifest says LGPL-3 would
  misstate the license of derived code.
- **Options:**
  1. **Concepts only (recommended).** Schema shapes, field semantics, lifecycle ideas and
     date-math *behaviour* are ideas, not protected expression. Re-implement in our own
     code, Arabic-first, with our naming (`legal.contract`, `legal.contract.clause`, …).
     Cost is low: apart from the recurrence math (~90 real lines) the OCA code is plain
     ORM boilerplate we would rewrite anyway for Odoo 19 and RTL.
  2. Deliberately publish the new contracts module as AGPL-3 and port. Odoo licensing is
     per-module, and LGPL modules may depend on an AGPL one — but this is a suite-policy
     decision the owner must make explicitly; do not drift into it.
- Scope note: the standing "port mature copyleft code, relicense if needed" policy in
  project memory is scoped to the *workshops* project, not this suite; here the brief
  fixes LGPL-3 as the baseline, so option 1 stands unless the owner says otherwise.

## 6. Concept adoption map for `legal_contract`

| # | Concept | Source | Verdict |
|---|---|---|---|
| 1 | Register skeleton: code+name, sequence-assigned, `unique(code,partner,company)`, mail.thread | agreement base | adopt |
| 2 | Type/subtype registries with per-type review defaults | agreement.type / agreement.subtype | adopt |
| 3 | `state` (server axis) + configurable stage (kanban axis) with fold/readonly | agreement_legal + agreement.stage | adopt; enforce in `write()`, not view hacks |
| 4 | Version tree + revision counter + copy-as-inactive-child; amendments as typed children | agreement_legal | adopt (immutable snapshots; amendment = ملحق kind) |
| 5 | Recital/section/clause/appendix, `title` vs `name`, translated HTML, sequence | agreement_legal | adopt; drop per-model placeholder builder |
| 6 | Symmetric parties + signed-by/on both sides + notification address | agreement_legal | adopt; bind to `legal.signatory` |
| 7 | Expiration/change-notice days + computed review date + cron | agreement_legal | adopt; route into unified deadline engine |
| 8 | Recurrence rule vocabulary + next-period date chain + pure calculators | contract.recurring.mixin | re-derive behaviour (no verbatim port) |
| 9 | Modification (amendment) log with auto "start" entry + notify subtype | contract.modification | adopt |
| 10 | Template→instance field sync with NO_SYNC list | contract.template | adopt |
| 11 | Cron shape: search due → group by company → generate → advance | contract | adopt for obligation instances |
| 12 | Localized period markers in generated labels | contract.line | adopt (Arabic month names) |
| 13 | Invoicing / journals / pricelists / portal | contract | skip |
| 14 | Single-Binary signed document | agreement_legal | improve: role-flagged ir.attachments |
| 15 | `get_view()` attrs rewriting | agreement_legal 16.0 | reject (attrs removed in 17+) |

## 7. Fetched sources (upstream paths; local copies kept in session scratchpad)

- `OCA/agreement@16.0`: `agreement/{__manifest__.py, models/agreement.py, models/agreement_type.py}`;
  `agreement_legal/{__manifest__.py, models/agreement.py (507 l), agreement_clause.py,
  agreement_recital.py, agreement_section.py, agreement_appendix.py, agreement_stage.py,
  agreement_line.py, agreement_subtype.py, agreement_type.py, res_partner.py}`
- `OCA/agreement@{17.0,18.0,19.0}`: root listings + `agreement_legal/__manifest__.py`
  (17/18) + `agreement/__manifest__.py` (19)
- `OCA/contract@18.0`: `contract/{__manifest__.py, models/contract.py (706 l),
  contract_line.py, contract_recurring_mixin.py, contract_modification.py,
  contract_template.py, contract_tag.py}`; plus `contract/__manifest__.py` @19.0
