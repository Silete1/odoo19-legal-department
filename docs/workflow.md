# Workflow

```text
Draft
  │ submit
  ▼
Memo: Concerned Department Manager
  ▼
Memo: Director General
  ▼
Memo: Administrative Department Manager
  ▼
Administrative Officer Review
  │ verify required basis + prepare/archive memorandum
  ▼
Mission Order: Administrative Department Manager
  ▼
Mission Order: Director General (stamp authorization)
  ▼
Issuance: same Administrative Officer
  │ outgoing number/date + archived stamped PDF
  ▼
Completed
```

Every routed step creates one native To Do activity for its resolved user. A decision completes the old activity and creates the next. Duplicate active activities for a step are suppressed.

Return requires a reason and creates an immutable `returned` log. A memo-phase return assigns correction to the requester; a mission-order return assigns correction to the responsible administrative officer. Resubmission increments the approval round and records `restarted`; older-round approvals remain visible and are computed as superseded rather than edited or deleted.

High-level states shown to users are Draft, Initial Approvals, Document Review, Mission Order Preparation, Final Approvals, Awaiting Outgoing Registration, Completed, Returned, and Rejected. The active step retains the precise internal position.
