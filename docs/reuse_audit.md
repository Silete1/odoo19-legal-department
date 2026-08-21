# Odoo 19 reuse audit

| Requirement | Existing Odoo mechanism | Source inspected | Reuse approach | Custom code required |
| --- | --- | --- | --- | --- |
| Employees | `hr.employee` | `odoo-19.0/addons/hr/models/hr_employee.py` | Direct employee references | Participant snapshot line only |
| Departments/hierarchy | `hr.department`, `parent_id`, `_parent_store` | `addons/hr/models/hr_department.py` | Direct department dropdown and company checks | None |
| Department manager | `hr.department.manager_id` + employee `user_id` | HR models/tests | Resolve at every routing/approval action | Clear configuration validation |
| Employee/user/company | stored employee `user_id`; native company rules | HR/base security | Reuse user/company mappings | Case-specific role resolution |
| Messaging/audit | `mail.thread.main.attachment`, tracked fields, chatter | HR leave/expense models | Inherit and post concise events | Structured immutable log in addition |
| Approval tasks | `mail.activity.mixin`, `activity_schedule`, `activity_feedback` | `hr_expense.py`, `hr_leave.py` | One native To Do per active step | Route-to-user orchestration |
| Security | groups, ACL CSV, `ir.rule`, company domains | HR and time-off security XML/tests | Native CRUD and additive role rules | State/actor/field checks in public methods |
| Numbering | `ir.sequence`, date-range interpolation | base sequence and addon data | `EFD/%(year)s/` + padding | Assign on creation, no SQL counter |
| Supporting files | attachment-backed Binary and chatter attachments | `ir.attachment`, Binary field examples | Structured Binary line plus chatter | Evidence metadata/verification fields |
| PDF reports | QWeb PDF, `ir.actions.report`, paper format | base `ir_actions_report.py`, account reports | Native report actions/templates | Arabic templates and render guards |
| Immutable final PDF | `attachment`, `attachment_use`, `retrieve_attachment` | base report model/tests | Deterministic cached attachment; serve archived ID | Issuance guard and saved attachment links |
| Analytics | list/search/graph/pivot | HR expense/time-off views | Native views and date grouping | Stored dependable measures |
| Configuration | `res.company` + related `res.config.settings` | HR/mail settings patterns | Company-specific organization/stamp settings | Government fields and restricted settings view |
| Approval behavior | guarded actions, state locking, refusal/activity cleanup | `hr_holidays`, `hr_expense`, `purchase` | Follow native transition patterns | Reusable two-phase route and return rounds |
| Enterprise UX reference | Documents, Sign, Approvals, Studio approval assets | `enterprise-19.0/{documents,sign,approvals,web_studio}` | Concepts only: ownership, concise decisions, audit visibility | No dependency/import/copy |
| Employee selection UX | native Many2one autocomplete | `web/static/src/views/fields` and HR views | Reuse inline participant employee selector | Onchange snapshot population |
| File upload UX | native Binary/file widget | web fields and attachment-backed models | Reuse filename/file fields | Checklist presentation in standard list |
| Conditional form actions | Odoo 19 expression attributes | HR expense/time-off views | `invisible`/`readonly` expressions | Server authorization remains authoritative |
| Return dialog | native modal `ir.actions.act_window` transient model | standard wizard patterns | Reuse Odoo dialog rendering | Mandatory-reason wizard |
| Notifications | standard display notification action | web client action handling | Return `display_notification` where useful | Messages only |
| Workflow presentation | statusbar is too coarse for role/date/round detail | statusbar and Owl field examples | Statusbar for high-level state; one readonly Owl field widget | Compact progress/timeline only |
| Director/Officer layouts | native responsive form groups, alerts, buttons, tabs | HR expense and purchase forms | Standard form architecture and Bootstrap/Odoo utilities | Role/state-focused task panel |
| PDF viewing | native report action / `/web/content` attachment | report controller/action conventions | Reuse report and attachment downloads | No custom viewer |

## Second-pass reinvention check

Completed after implementation on 2026-08-20. The second search covered `mail.activity` completion/archiving, `ir.actions.report.attachment_use`, `_check_company_auto`, HR organization fields, and Odoo web field widgets using `standardFieldProps` and the fields registry. No custom helper duplicated a suitable core mechanism.

The remaining custom pieces are justified government-domain behavior: organizational route resolution, immutable structured decisions and correction rounds, supporting-document verification, historical participant snapshots, final-stamp authorization and archived attachment protection, plus one readonly compact workflow field widget. The widget consumes one server-computed payload and performs no RPC or business decision.
