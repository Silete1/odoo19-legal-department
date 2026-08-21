# Architecture

## Decision

The implementation uses two Community-safe addons:

- `gov_hr_base`: reusable case, route, step, immutable decision log, basis/document metadata, organizational role resolution hooks, company settings, return wizard, security groups, and activity routing.
- `gov_hr_deputation`: a single deputation business record, participant snapshots, deputation validation, reports, analytics, UI, and default configuration.

`gov.hr.deputation` uses delegation inheritance (`_inherits`) to `gov.hr.case`. This keeps one user-facing deputation record while giving future modules a real common case identity and shared approval/document history. It is preferable here to copying a mixin because logs, basis lines, activities, sequence identity, and archived document metadata belong to the common case. Deputation-specific ACLs and record rules remain on the user-facing model; direct common-case mutation is additionally protected by server methods and restricted menus.

## Runtime dependencies

`gov_hr_base` depends on `mail` and `hr`. `base` is transitively mandatory in every Odoo database; `mail` is explicit for thread/activity APIs; `hr` is explicit for employee and department organization. `gov_hr_deputation` depends only on `gov_hr_base`. There are no Enterprise imports, inherited Enterprise models, Enterprise assets, or third-party Python/JavaScript packages.

## Core model

```text
gov.hr.case.type ──< gov.hr.approval.route ──< gov.hr.approval.step
        │
        └──< gov.hr.case >── gov.hr.deputation
                  ├──< gov.hr.case.basis >── gov.hr.basis.type
                  └──< gov.hr.approval.log

gov.hr.deputation ──< gov.hr.deputation.participant >── hr.employee
```

The route is configuration, while an approval log is immutable evidence. A case stores the active step and resolved user so list domains and native activities remain efficient. Dynamic roles are resolved at routing time from the case's company, department, and assigned officer. Public workflow actions re-resolve and validate authorization to prevent RPC bypass.

## Document integrity

Draft actions never cache. The final memorandum and mission-order report actions use deterministic names and Odoo's `attachment_use`; guarded report models reject premature render attempts. Issuance stores the generated attachment ID on the case. Reprint serves that attachment rather than re-rendering with current employee/department/stamp data. Participant and organizational display snapshots preserve report context in addition to the authoritative PDF.

## Frontend decision

Odoo 19 forms, relational autocomplete, attachment-backed Binary fields, notebook/list editors, statusbar, buttons, dialogs (transient wizard), chatter, list/search/graph/pivot views, and report viewer/actions cover most UI needs. One readonly Owl field widget renders the compact workflow progress/timeline from one computed JSON payload. It performs no business decision and no custom RPC, avoiding per-step calls.
