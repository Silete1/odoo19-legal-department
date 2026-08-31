# Cross-module Security Audit — Legal Suite (KEY=security)

Audited modules: `legal_core`, `legal_correspondence`, `legal_procedure`, and the
content packs `legal_iq_registrar`, `legal_iq_tax`, `legal_iq_chamber`,
`legal_iq_social_security`, `legal_iq_residency`, `legal_iq_demo`.

Live enforcement was tested over XML-RPC against `http://localhost:8090`, db
`legal_dept`, as `auditor@legal.iq`, `clerk@legal.iq`, `officer@legal.iq`
(password `Legal#2026`). **All 18 mutation probes behaved as expected — zero ACL
breaches.** The one authorised write that succeeded (clerk editing a case note,
an operation the ACL legitimately grants) was reverted to a byte-identical
original and verified.

## Summary

The security model is, on the whole, unusually careful and well-documented: a
short five-group ladder plus a job-not-rank Registrar group; per-body visibility
expressed as **data** (`gov_body.officer_ids`) traversed by record rules rather
than a group-per-ministry explosion; a genuinely **read-only auditor** (verified
live); an **immutable append-only** `legal.action.log` (write/unlink raise even
for admin); **server-side field-locking** of registered correspondence (not mere
`readonly`); multi-company global rules on every transactional model; and
confidentiality rules on documents, correspondence and cases. There are **no HTTP
controllers**, and every `sudo()` is narrow and legitimate.

The material weakness is **separation of duties in the case/correspondence
lifecycle**. The engine has the right hook to gate approvals and closures
(`legal.procedure.transition.group_ids`) but the shipped/demo data leaves it
**empty on all 30 transitions**, including all 10 that close a file. Confirmed
live: a **clerk is offered a case-closing transition** and can drive a file to a
granted/rejected terminal outcome with no approver or manager involvement. The
Approver group is effectively decorative for the case workflow. Several other
significant acts — voiding a numbered register entry, waiving a statutory
obligation, reopening a closed file — are likewise gated only by generic `write`
ACL, not by role.

| Area | Current | Problem | Severity | Target |
| --- | --- | --- | --- | --- |
| Case approval/closing | 30 transitions ship with `group_ids` empty; all 10 closing transitions ungated | Any clerk (write on `legal.case`) can approve/reject/close a file; Approver role never required — verified: clerk offered closing transition on case 441 | high | Populate `group_ids` on approval/closing transitions (approver/manager); ship demo transitions gated; consider requiring a non-empty group on terminal-bound transitions |
| Correspondence void | `legal.correspondence.void.wizard` full CRUD to clerk; `action_void` writes `state=void` with only a mandatory reason | Voiding an official numbered register entry (striking the book) is available to any clerk with no elevated role | medium | Gate voiding to officer/approver/manager (or the register's `write_group_id`) server-side |
| Obligation waive | `legal.obligation.instance` clerk=`1,1,0,0`; `action_waive` sets `state=waived` with no role check | A clerk can waive a statutory obligation (e.g. skip a mandatory filing) — a compliance-significant act | medium | Gate `action_waive` (and arguably `action_mark_filed`) to manager/approver |
| Case reopen | `legal.case` clerk=`1,1,1,0`; `action_reopen` re-opens a terminal file with no role check | Any clerk can reopen a closed file; no approval or separation of duties on reversing a closure | medium | Restrict `action_reopen` to officer/manager |
| Registrar control | Shipped registers leave `write_group_id` empty; `_may_allocate` returns True when empty | Out-of-the-box the "one keeper of the book" control is OFF — any clerk allocates register numbers | low | Document as a required deployment step; consider defaulting a Registrar group on seeded registers |
| Correspondence ACL breadth | `legal.correspondence` / `legal.correspondence.line` grant clerk `perm_unlink=1` | Broader than needed; only the `unlink()` override (draft-only) prevents clerks deleting register entries — a single regression re-opens deletion of the book | low | Set clerk `perm_unlink=0` on correspondence and its lines; keep the override as defence-in-depth |
| Case confidentiality escape hatch | `rule_legal_case_confidential` OR-s `user_id = user` and `runner_partner_id = user.partner` | A confidential file is visible to its assignee/runner even if they are not an officer of the issuing body | low | Intended (handler must see the file) — document; verify assignment is itself controlled |
| Workflow method entry checks | `action_advance` etc. read/branch under caller rights and rely on the eventual ORM `write` for enforcement | Safe today (auditor blocked at the write; verified) but no explicit access assertion at method entry | low | Optional: assert `check_access('write')` at the top of state-changing methods for clarity/defence-in-depth |

## Groups (the ladder)

`legal_core` defines five `res.groups` under one privilege/category:

- `group_legal_clerk` implies `base.group_user`
- `group_legal_officer` implies clerk
- `group_legal_approver` implies officer
- `group_legal_manager` implies approver (and, via `legal_correspondence`, implies `group_legal_registrar`)
- `group_legal_auditor` implies **only** `base.group_user` (deliberately outside the ladder; read-only)

`legal_correspondence` adds `group_legal_registrar` (a *job*, implies clerk; a register points at it via `write_group_id`). `legal_procedure` deliberately defines **no** new group (per-step/per-transition ownership is data). Content packs (`legal_iq_*`) define **no models and no security objects** (verified: 0 `_name =` in each) — the intended "configured, not forked" design.

## Model x Group CRUD matrix (R/W/C/U)

Legend: `-` none, `R` read, `RW` read+write, `RWC`, `RWCU` full. Auditor is `R`
on every model listed and is omitted per-row except where notable. Config models
follow the pattern **clerk=R, manager=RWCU, auditor=R**.

### legal_core
| Model | clerk | officer | approver | manager |
| --- | --- | --- | --- | --- |
| jurisdiction / gov.body.type / entity.form / identifier.kind / document.kind / licence.grade / document.type / signatory | R | – | – | RWCU |
| legal.gov.body | R | RW | – | RWCU |
| legal.gov.body.contact | RWC | – | – | RWCU |
| legal.entity | R | – | RW (approver) | RWCU |
| legal.entity.identifier | RWC | – | – | RWCU |
| legal.document | RWC | – | – | RWCU |

### legal_correspondence
| Model | clerk | approver | registrar | manager |
| --- | --- | --- | --- | --- |
| legal.register | R | – | – | RWCU |
| legal.correspondence.kind | R | – | – | RWCU |
| legal.letter.template | R | RW | – | RWCU |
| legal.correspondence | **RWCU** | – | – | RWCU |
| legal.correspondence.line | **RWCU** | – | – | RWCU |
| *.register.wizard / void.wizard / contact.note.wizard (transient) | RWCU | – | – | – |

### legal_procedure
| Model | clerk | officer | manager |
| --- | --- | --- | --- |
| procedure.type / phase / step / step.check / field / transition / doc.requirement / fee.rule / sla.rule | R | – | RWCU |
| legal.sla.escalation | R | RW | RWCU |
| legal.poa | R | RWC | RWCU |
| legal.action.log | R (read-only by design) | – | R (read-only by design) |
| legal.case | RWC | – | RWCU |
| legal.case.subject | RWCU | – | RWCU |
| legal.case.document | RWC | – | RWCU |
| legal.case.step.check | RWC | – | RWCU |
| legal.fee | RWC | – | RWCU |
| legal.obligation.schedule | R | – | RWCU |
| legal.obligation.instance | RW | – | RWCU |
| legal.case.return / case.step.wizard(.line) (transient) | RWCU | – | – |
| legal.poa.revoke (transient) | – | RWCU | – |

Notable ACL points: `legal.correspondence(.line)` grants clerk **unlink** (see
finding); `legal.action.log` grants **no** create/write/unlink to any group
(append-only; rows are made only via `sudo()` in `_log`, and the model overrides
`write`/`unlink` to raise for everyone including admin).

## Record rules

**Multi-company (global, AND-ed):** `legal.gov.body`, `legal.document.type`,
`legal.entity`, `legal.document`, `legal.register`, `legal.correspondence`,
`legal.letter.template`, `legal.procedure.type`, `legal.obligation.schedule`,
`legal.obligation.instance`, `legal.case`, `legal.poa`, `legal.action.log`,
`legal.sla.escalation` — each `company_id in company_ids` (config models also
allow `company_id = False` shared). Good coverage; every transactional model is
company-scoped.

**Confidentiality (group-scoped, OR-ed within the model):**
- `legal.document`: clerk/officer/approver limited to `confidential = False` OR `issuing_body_id.officer_ids in [user]`; manager + **auditor** see all.
- `legal.correspondence` + `.line` (`secrecy = 'secret'`): clerk/officer/approver/registrar limited to non-secret OR `gov_body_id.officer_ids in [user]`; manager + **auditor** see all.
- `legal.case` + `legal.action.log`: clerk/officer/approver limited to non-confidential OR body-officer OR `user_id = user` (case also OR `runner_partner_id`); manager + **auditor** see all.

The auditor is placed in the manager-side "sees everything" rule for each, so it
can audit confidential records — correct for a read-only reviewer.

## sudo() review (all legitimate)
- `legal_correspondence.py:689` `self.sudo().search(...).our_number` — read-only, reads only the last allocated number so a clerk who cannot see a secret entry still can't collide with its number. Scoped, safe.
- `legal_register.py:154` / `legal_procedure_type.py:419,429` — `ir.sequence` provisioning. Safe.
- `legal_case.py:939` `legal.action.log.sudo().create(...)` — the only way trail rows are created (no group has create). Correct append-only design.
- `legal_case.py:1173,1213,1241,1416,1430,1469` — sudo to instantiate configured case lines (documents/checks/fees) and SLA escalations; reached only from case-engine methods already gated by case ACL/rules. Safe.
- `legal_dashboard.py:762` `action_record.sudo()` — reads only `name`/`res_model` of an `ir.actions.act_window` fetched by a **hardcoded** xmlid to build a wizard action dict; executes nothing user-controllable. Safe. (The dashboard also deliberately **re-raises** `AccessError` from `_safe_search`/`_safe_count`, so record rules are honoured rather than masked.)
- `legal_obligation.py:261` — sudo create of obligation instances during generation. Safe.

## HTTP controllers
None. No `http.Controller` / `@http.route` in any legal module.

## Live XML-RPC enforcement results (execute_kw)

Auditor (`auditor@legal.iq`) — **every** attempt correctly **BLOCKED**:
`legal.case.write` (note), `legal.gov.body.create`, `legal.correspondence.unlink`,
`legal.document.write`, `legal.case.message_post` (chatter), `legal.case`
`activity_schedule`, `legal.case.action_advance` (workflow), `legal.action.log.write`.
`message_post` and `activity_schedule` are blocked because `mail.thread`
`_mail_post_access` defaults to `write`, which the auditor lacks — confirming the
read-only auditor cannot even annotate a file.

Clerk (`clerk@legal.iq`): baseline `legal.case.write` (note) **ALLOWED** as
designed and then **reverted** (verified identical). Correctly **BLOCKED**:
`legal.entity.write` (approver-only), `legal.procedure.type.create` (mgr-only),
`legal.case.unlink` (mgr-only), `legal.poa.create` (clerk no-create),
`legal.register.create` (mgr-only).

Officer (`officer@legal.iq`) — manager-only attempts all **BLOCKED**:
`legal.procedure.type.create`, `legal.case.unlink`, `legal.register.create`,
`legal.jurisdiction.create`.

Non-destructive separation-of-duties probe (no mutation): reading
`available_transition_ids` as the clerk shows **10 closing transitions with
`group_ids = []`**, and the clerk is **offered** a terminal transition
("rejected by the sponsoring ministry") on case 441 — i.e. a clerk can close a
file. This is the evidence behind the top finding.

## Detailed notes (file:line)
- `legal_core/security/legal_core_security.xml` — five-group ladder; auditor implies only `base.group_user`.
- `legal_correspondence/security/legal_correspondence_security.xml` — `group_legal_registrar`; manager made to imply it.
- `legal_procedure/security/legal_procedure_security.xml` — no groups; two server actions only.
- `legal_core/security/legal_core_rules.xml:52-70` — document confidentiality + manager/auditor override.
- `legal_correspondence/security/legal_correspondence_rules.xml:47-83` — secrecy rules for correspondence and its lines.
- `legal_procedure/security/legal_procedure_rules.xml:98-140` — case/log confidentiality with `user_id`/`runner_partner_id` escape hatch (`rule_legal_case_confidential`).
- `legal_procedure/models/legal_case.py:1026-1073` `action_fire_transition` / `_fire` — guarded by `available_transition_ids`, computed per-user at `:724-746` honouring `transition.group_ids` (empty in shipped data → ungated).
- `legal_procedure/models/legal_case.py:979-1024` `action_advance`, `:1146-1160` `action_reopen` — no role gate beyond `write` ACL.
- `legal_procedure/models/legal_obligation.py:494-500` `action_mark_filed` / `action_waive` — no role gate.
- `legal_procedure/models/legal_action_log.py:122-138` `write`/`unlink` raise for everyone — immutable trail.
- `legal_correspondence/models/legal_correspondence.py:750-812` `write`/`unlink` — server-side field-lock and delete-only-draft (strong).
- `legal_correspondence/models/legal_register.py:190-214` `_may_allocate` / `_check_may_allocate` — registrar gate, off when `write_group_id` empty.
- `legal_correspondence/wizard/legal_correspondence_void_wizard.py:39-58` `action_void` — no role gate.
