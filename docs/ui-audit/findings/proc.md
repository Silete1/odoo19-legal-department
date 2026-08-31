# legal_procedure — Python engine audit (KEY=proc)

## Summary

`legal_procedure` is the state-machine spine of the suite and, on the whole, it is
unusually well-engineered Odoo: the "states are rows, not a Python enum" thesis is
carried through cleanly, the immutable action log is genuinely immutable (write/unlink
raise even under `sudo`, and **no group has `create` on `legal.action.log`** so clients
cannot forge entries), the escalation and obligation crons are idempotent by real unique
indexes rather than by drift-prone flags, the SLA verdict is computed live while only the
deadline is stored, the graph validator refuses always-false conditions and unreachable/
dead-end steps, and blockers/POA/document status each have a single authoritative method
that every surface reads. The data model is idiomatic 19.0 (`models.Constraint` /
`models.UniqueIndex`, `_read_group`, partial indexes, snapshots on the log and on the
counter-walk rows).

The audit nonetheless finds **one critical defect that voids the module's central
integrity guarantee**: the workflow-owned-fields write guard — the thing the docstrings
repeatedly describe as "readonly is a client hint, this is the rule that cannot be
bypassed by a client" — is gated solely on the `legal_workflow` **context key**, and
context is fully attacker-controlled over RPC. Any user with write on `legal.case`
(clerks have it) can pass `context={"legal_workflow": true}` in a `call_kw` and write
`step_id`, `outcome`, `round`, `date_closed` directly, teleporting a file past every
approval, blocker and — because the bypass never calls `_move_to` — **without writing a
single trail entry**. A second, quieter path around the same guard exists: `procedure_type_id`
is *not* workflow-owned, and editing it silently relocates `step_id` through a stored
compute, again with no log. Finally, the product's headline security posture (read-only
auditor, confidential-file rule, per-body scoping) is asserted only by static CSV/XML and
is **never exercised by a test** — every backend test runs as the admin superuser.

Fix the context guard (a thread-local/private sentinel, or `sudo()`-with-a-real-token, not
a serialisable context flag), lock `procedure_type_id` after creation (or route its change
through the engine), require a reason on reopen, and add non-admin ACL/rule tests. The rest
is medium/low polish.

| Area | Current | Problem | Severity | Target |
|------|---------|---------|----------|--------|
| Write guard (`legal_case.py:911`, `legal_sla_rule.py:1011`) | Workflow-owned fields refused unless `env.context.get("legal_workflow")` | Context is client-supplied over RPC (`service/model.py:89` applies `kwargs.pop('context')` verbatim). Any clerk can send `context={"legal_workflow":true}` and write `step_id`/`outcome`/`round`/`date_closed` directly — skipping blockers, approvals **and the immutable log** (`_move_to` never runs) | **critical** | Guard on a non-serialisable signal (thread-local token set only inside `_engine`, or an in-process sentinel), never on a context key a client controls |
| `procedure_type_id` editable (`legal_case.py:484`,`902`,`67`) | Field is writable (not in `WORKFLOW_OWNED_FIELDS`); `_compute_step_id` resets `step_id` when it changes | Changing the procedure relocates the file to another graph's first step, resets `outcome`/`is_closed`, and re-syncs lines — all outside `_move_to`, with **no trail entry** and no round bump. A second bypass of the step guard | **high** | Make `procedure_type_id` readonly after create (or add to the guarded set / route through the engine with a logged "procedure changed" move) |
| Reopen has no reason (`legal_case.py:1146`) | `action_reopen` writes a `reopen` log with `reason=None` | The trail is reason-strict everywhere else (return, revoke, rejection). Re-opening a *granted/closed* file — which makes every closure statistic optimistic, as the docstring itself notes — records no justification | **high** | Route reopen through a wizard that demands a reason, stored on the `reopen` log entry |
| Security is untested (`tests/*`) | All engine/graph/obligation/wizard tests run as admin | The brief's core requirements — read-only auditor, `rule_legal_case_confidential`, per-body `officer_ids` scoping, clerk cannot write the log — are never executed with a non-manager user. Combined with the critical guard hole, the server-side security story is unverified | **high** | Add `TransactionCase` tests using `with_user()` for clerk/officer/auditor asserting ACL + record-rule enforcement and the write-guard cannot be bypassed |
| `_compute_available_transitions` deps (`legal_case.py:724`) | `@api.depends("step_id","procedure_type_id")` + `depends_context uid` | A transition's `condition_domain` may read `subject_ids`, `capture_values`, `body_id` etc.; those are not in the dependency list, so conditional buttons go stale until `step_id` changes or the form reloads. The docstring claims the user is shown exactly their available moves | **medium** | Widen `@api.depends` to the fields real conditions read, or accept staleness and document it; `_fire` already re-validates so it is UX-only |
| `_search_sla_state` vs `_compute_sla_state` (`legal_case.py:578`,`594`) | Compute checks `paused` first; search "escalated" branch matches any open escalation without excluding paused | A paused file with an open escalation draws the **paused** badge but is returned by the **escalated** filter — the two disagree, contradicting "the filter cannot disagree with the badge" | **medium** | Add `('sla_paused','=',False)` to the escalated search branch (and decide the paused-vs-escalated precedence once) |
| `_produce_result_document` runs as caller (`legal_case.py:1266`) | On a terminal move the clerk's own user creates a `legal.document` (no `sudo`) | If the clerk lacks create on `legal.document`, the terminal advance raises `AccessError` mid-move and the whole close rolls back — a file that cannot be granted. Cross-module ACL dependency that is not asserted anywhere | **medium** | Create the register document with `sudo()` (it is engine-produced evidence, not user data), or assert the clerk grant in `legal_core` ACL + a test |
| `_cron_deadline_scan` stale sweep (`legal_case.py:1421`) | `Escalation.search([('resolved_on','=',False)])` iterates **all** open escalations, unbatched, before `_commit_progress` accounting begins | On a large live caseload the stale-resolve pass is unbounded work outside the scheduler's time budget; only the second loop is chunked. Not incorrect, but defeats the "safe to interrupt" design for the first half | **low** | Fold the stale check into the budgeted loop, or bound it with the same `limit`/progress commits |
| Declared-but-unused config (`legal_procedure_type.py:229`,`239`,`253`) | `has_incoming_reply`, `has_result_document`, `requires_documents` defined on the type | `_blockers`/the gate consult only `has_poa` (and the document lines directly). These three read like meaningful gating config but have no server-side effect, inviting a configurer to set `requires_documents="no"` and still be blocked by document lines | **low** | Wire them into the engine (e.g. `requires_documents` short-circuits the document blocker) or drop/mark them view-only |
| Leftover debug artifact (`models/__pycache__/_debug_reflect.cpython-311.pyc`) | Compiled `.pyc` with no matching source, not imported, not git-tracked | Harmless but indicates a `_debug_reflect` module was shipped in a build at some point | **low** | Delete the orphan `.pyc`; confirm nothing references it |

## Detailed notes

### 1. CRITICAL — the write guard is a context flag, and context is client-controlled

`models/legal_case.py:902-921`:

```python
def write(self, vals):
    if not self.env.context.get("legal_workflow"):
        forbidden = sorted(set(WORKFLOW_OWNED_FIELDS).intersection(vals))
        if forbidden:
            raise UserError(_("A file is moved by the buttons on it, never by writing to it. ..."))
    cases = super().write(vals)
    ...
```

`_engine()` (`legal_case.py:932-934`) sets the pass exactly as `self.with_context(legal_workflow=True)`. The docstrings (`legal_case.py:39-43`, `900-909`; `legal_constants.py:83-96`) state the rule "lives here, where it cannot be bypassed by a client."

It can. Odoo 19's RPC dispatch (`odoo-19.0/odoo/service/model.py:88-90`) does:

```python
kwargs = dict(kwargs)
context = kwargs.pop('context', None) or {}
recs = recs.with_context(context)
```

The client supplies `context` in every `call_kw`; it is applied verbatim before the method runs. So a `legal.case.write` invoked with `kwargs={"context": {"legal_workflow": true}}` sets `env.context["legal_workflow"] = True`, the guard is skipped, and `WORKFLOW_OWNED_FIELDS` (`step_id, phase_id, outcome, round, stage_entered_on, sla_due_on, date_closed, procedure_version`) are written directly.

Impact, given clerks hold `perm_write=1` on `legal.case` (`security/ir.model.access.csv:63`):
- A clerk can write `step_id` to the terminal `granted` step, which via stored-related fields sets `outcome=granted` and `is_closed=True`, **skipping** every blocker (`_blockers`), every fee/document/POA gate, and every approval transition.
- Because the write bypasses `_move_to`, **no `legal.action.log` row is created** — the invariant "every move appends exactly one row" (`legal_action_log.py:138-146`) is broken, and `stage_entered_on`/`our_days`/`their_days` (all read off the log) silently desync.
- `sla_due_on`, `date_closed`, `procedure_version`, `round` can all be forged the same way.

The same hole exists on `legal.sla.escalation.write` (`legal_sla_rule.py:1002-1020`): the "frozen" fields (`case_id, step_id, round, reason, raised_on, step_code`) are protected by the identical `not self.env.context.get("legal_workflow")` test, so a client can rewrite an escalation's reason/date by supplying the context.

Note the contrast that proves the correct pattern is already understood in this very file: `legal.action.log.write/unlink` (`legal_action_log.py:254-269`) raise **unconditionally** with no context escape, and no group is granted create/write/unlink on the log — that model is genuinely tamper-proof. The case/escalation guards should be equally unconditional relative to any client-reachable signal. A minimal fix is a module-level thread-local set/reset only inside `_engine()` (never serialisable), or a private per-record token; the guard then reads that, not `env.context`.

### 2. HIGH — `procedure_type_id` is a second door around the step guard

`procedure_type_id` (`legal_case.py:67-74`) is required but not readonly and **not** in `WORKFLOW_OWNED_FIELDS`. `_compute_step_id` (`legal_case.py:484-495`) is `store=True, readonly=False, precompute=True, @api.depends("procedure_type_id")` and resets `step_id` to `procedure_type_id._first_step()` whenever the procedure changes and the current step no longer belongs to it. `write` (`legal_case.py:922-926`) then re-runs `_sync_document_lines/_sync_step_checks/_sync_fees` because `"procedure_type_id" in vals`.

Consequence: a plain `write({"procedure_type_id": other.id})` — allowed for clerks, no special context needed — relocates the file into a different state machine's first step, flips `outcome`/`is_closed`/`kind` via the stored related fields, and grows a new checklist, **all outside `_move_to` and with no trail entry and no round change.** `_check_step_belongs_to_procedure` (`legal_case.py:1365`) passes because the compute already moved the step to match. This is both a workflow-integrity gap and a second bypass of the very guard finding #1 is about. Lock `procedure_type_id` after create, or force its change through an engine method that logs a move.

### 3. HIGH — reopen records no reason

`action_reopen` (`legal_case.py:1146-1161`) bumps the round and logs a `reopen` entry with `reason=None`. Returns (`_return_for_correction:1108`), rejections (`require_reason`), and POA revocations (`legal_poa_revoke.py:251`) all *demand* a reason precisely because "a revocation nobody can explain is indistinguishable from a mistake." Re-opening a file that had reached `granted` is at least as consequential — the docstring admits "hiding it makes every closure statistic optimistic" — yet it is the one significant act with no captured justification. Route it through a small wizard like the return/revoke dialogs.

### 4. HIGH — the security model is never tested with a non-admin user

`security/ir.model.access.csv` and `legal_procedure_rules.xml` encode the brief's central controls: auditor is read-only on every model; `access_legal_action_log_*` grant clerks/managers read-only (create/write/unlink all 0); `rule_legal_case_confidential` restricts confidential files to the manager, the responsible user, the runner partner, or officers of the file's body; per-company global rules on every transactional model. None of this is exercised — `tests/common.py` and all four test modules operate as the admin superuser, which bypasses record rules and most ACLs. `test_step_id_cannot_be_written_over_rpc` (`test_case_engine.py:217`) even asserts the guard "even as a superuser," but never tests the actual RPC-context bypass in finding #1, nor a real clerk. Add `with_user()` tests: clerk cannot write the log; auditor cannot write anything; a confidential file is invisible to a clerk who is neither owner, runner, nor a body officer; and `write({"context":{"legal_workflow":True}, ...})` must still be refused after the fix.

### 5. MEDIUM — stale conditional-move buttons

`_compute_available_transitions` (`legal_case.py:724-746`) recomputes only on `step_id`/`procedure_type_id`/`uid`, but `_matches` (`legal_procedure_transition.py:1143-1156`) evaluates the transition's `condition_domain` against the file's live values (`subject_ids`, `capture_values`, `body_id`, `confidential`, …). A move whose condition depends on those fields will not re-offer/withdraw its button until the step changes or the form reloads. Server-side firing is safe (`action_fire_transition:1037` re-checks membership, `_fire:1061` re-runs blockers), so this is UX correctness, not a hole — but it contradicts the "a clerk is shown exactly the moves they may make" claim.

### 6. MEDIUM — search/compute disagreement for paused + escalated

`_compute_sla_state` (`legal_case.py:578-592`) returns `paused` first, before the escalation check. `_search_sla_state` (`legal_case.py:594-643`) "escalated" branch is `[("escalation_ids","any",[("is_open","=",True)])]` with no `sla_paused=False` guard. A paused file that still has an open escalation therefore draws the **paused** badge but is returned by an **escalated** filter — the exact disagreement the method's docstring says is impossible. Add `('sla_paused','=',False)` to the escalated branch (or decide the precedence deliberately and mirror it in both).

### 7. MEDIUM — result-document creation is not `sudo`

`_produce_result_document` (`legal_case.py:1266-1298`) does `self.env["legal.document"].create(...)` as the acting user during a terminal move. If a clerk lacks create on `legal.document` (defined in `legal_core`), granting a file raises `AccessError` and the close rolls back. The document is engine-produced evidence filed in the shared register, so `sudo()` is appropriate here (as `_log`, `_sync_*` already use); at minimum add a test asserting a clerk can close a producing procedure.

### What is genuinely good (so a redesign preserves it)

- **Log immutability done right**: `write`/`unlink` raise unconditionally, no group has create on `legal.action.log`, and rows snapshot `step_code/step_name/body_name/group_code` at write time (`legal_action_log.py:237-269`) so reconfiguration cannot rewrite history. `test_the_trail_cannot_be_edited_or_deleted` / `..._snapshots_the_configuration_of_the_day` cover it.
- **Cron idempotency is structural**: escalations keyed by `UniqueIndex(case,step,round,level)` (`legal_sla_rule.py:979`), obligation periods by `(schedule,period_key,company)` (`legal_obligation.py:407`), both crons walk oldest-first and `_commit_progress` after each record (`legal_case.py:1440-1457`, `legal_obligation.py:311-325`). Re-runs write nothing — asserted by `test_generation_is_idempotent` and `test_the_deadline_scan_raises_one_escalation_and_no_more`.
- **Single source of truth for "blocked"/"satisfied"/POA validity**: `_blockers` (`legal_case.py:789`), `LegalCaseDocument._is_satisfied`/`_blocking_reason` (`legal_case_document.py:906-923`), `LegalPoa._blocking_reason` (`legal_poa.py:715`) — each returns sentences, read by gate, meter, rail and desk alike.
- **Graph validation refuses the symptomless fault**: always-false `condition_domain` is rejected at write time and re-reported by `action_validate` (`legal_procedure_transition.py:1109-1141`, `legal_procedure_type.py:559-584`), plus unreachable/dead-end detection via a real reachability walk.
- **Live SLA verdict, stored deadline**: `sla_state` is computed on read with a matching `_search_sla_state` that stays on stored/indexed deadline columns; `stage_entered_on`, `our_days`, `their_days` are all derived from the immutable log, not hand-written timestamps.
- **Version snapshotting** (`procedure_version` frozen at open) and the hand-remapped graph copy in `_copy_graph_into` (`legal_procedure_type.py:351-404`) correctly avoid the naive-one2many-copy trap where a new version's transitions point back into the old steps.
