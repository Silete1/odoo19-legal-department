# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Government department request preparers, concerned-department managers, administrative officers, administrative-department managers, the Director General, and government HR configuration managers.

## Product Purpose

Provide one auditable employee-deputation case from draft through memorandum, approvals, supporting-document verification, mission order, outgoing registration, and immutable official PDF issuance. Success means ordinary users enter the business facts once and Odoo routes the rest to the correct organizational roles.

## Positioning

The application combines organization-driven approvals, structured administrative evidence, and immutable Arabic government correspondence while retaining Odoo's native employee, department, activity, chatter, attachment, security, report, and analytics infrastructure.

## Operating Context

The primary language is Arabic and the operating ritual is a controlled government correspondence process. A request creator supplies subject, department, activity, destination, dates, participants, and basis documents. Managers approve or return. Administration verifies documents, prepares the mission order, records the outgoing number/date, and issues the archived official PDF.

## Capabilities and Constraints

- Odoo 19 Community-compatible; no Enterprise or paid third-party runtime dependency.
- Reusable government administrative case foundation plus a deputation application.
- One case is the source for both memorandum and mission order.
- Department managers resolve from `hr.department.manager_id`; users resolve through `hr.employee.user_id`.
- Native activities, chatter, attachments, sequences, ACLs, record rules, QWeb PDF, graph, and pivot views.
- Server-side workflow authorization and multi-company isolation.
- Official stamp is company-specific and may appear only in the first authorized final render; archived PDFs remain authoritative.
- Responsive, keyboard-usable, RTL-capable web client; business logic remains in Python.

## Evidence on Hand

Odoo 19 Community source is present at `odoo-19.0`; Enterprise source is present separately for behavioral inspection only. No Access `.accdb` or `.mdb` database was present during the workspace-wide scan on 2026-08-20. No government logo, stamp, signature, or sample official letter asset was supplied.

## Product Principles

- One case and one source of truth.
- Organization-driven routing with attributable decisions.
- Native Odoo first, with targeted Owl presentation only where it materially reduces cognitive load.
- Simple operational screens over a reusable, auditable backend.
- Historical and cross-company integrity are non-negotiable.

## Accessibility & Inclusion

Arabic RTL is primary. Custom interactive UI must retain semantic status text, keyboard access, adequate contrast, responsive layouts, and must not communicate meaning by color alone.
