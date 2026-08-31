# Browser UI/UX + RTL Audit — Admin walk (BEFORE state)

Audited: 2026-08-31, http://localhost:8090 db=legal_dept, user `admin` (en_US interface), Playwright/Chromium 1366x768 (key screens re-shot at 1920x1080). Screenshots: `docs/ui-audit/before/admin__*.png`. Read-only walk; DB facts confirmed with SELECT-only SQL.

## Summary

The installed product is a *government-procedure tracking* suite (legal_core + legal_correspondence + legal_procedure + 5 Iraqi content packs + demo), not the corporate legal-affairs system in the client spec. Of the spec's domains, only correspondence, corporate documents/licences, POA, obligations/deadlines and a role model exist. **Missing entirely: legal request intake, contracts + obligations-on-contract lifecycle, litigation/cases with hearings and a courts registry, and legal opinions/consultations** (`legal.case` is a government-transaction file, not a court case; there is no court/hearing/contract/opinion model anywhere in the schema). The company currency is **USD with USD the only active currency (no IQD)** despite an Arabic-named Iraqi company. The five role users run Arabic (ar_001) interfaces, but **no legal module ships any i18n/ar.po file and 0 of 164 menus / 0 of 157 actions have an ar_001 value** — the entire custom UI falls back to English for Arabic users; conversely most master data (procedure types, gov bodies) is stored as Arabic text under the `en_US` key, so labels are a fixed hard-coded mix (e.g. menu "صادر - Outgoing", "تسجيل كتاب وارد" beside "Mail Room", "Fees Paid"). Menu naming also collides: two different menus named "Mail Room" (dashboard vs correspondence list), two named "Procedures", a "Files/My Files" pair whose action is titled "My Desk" like the separate top-level "My Desk" dashboard.

## Findings table

| # | Area | Current | Problem | Severity | Target |
|---|------|---------|---------|----------|--------|
| 1 | Currency | Only USD active; company currency USD (res_currency: 1 row USD; company 1 = USD) | Client spec requires IQD for an Iraqi legal department; every fee amount renders in $ | critical | IQD company currency, IQD-formatted amounts (with proper ar digit/grouping), USD optional secondary |
| 2 | Translations | No i18n dir in any legal_* module; 0/164 menus, 0/157 actions carry ar_001; role users are ar_001 | Arabic-first requirement broken: Arabic users get English chrome, menus, buttons, statusbars; admin (en) gets Arabic data under en labels | critical | Full ar.po coverage for all legal modules; Arabic as source-of-truth language; verified RTL rendering |
| 3 | Functional scope | Models present: case(procedure file), correspondence, document, poa, obligation, fee, sla | No contracts, no litigation/hearings/courts registry, no legal opinions/consultations, no legal-request intake model | critical | Add the missing spec domains as first-class models with menus, stages, deadlines feeding the unified calendar |
| 4 | Menu naming | "Mail Room" appears twice (dashboard action 532 vs correspondence list action 169); "Procedures" twice (config parent 153 + its child action 514); menu "My Files" opens action titled "My Desk" while a top-level "My Desk" dashboard also exists | Duplicate/ambiguous names make the breadcrumb and command palette ambiguous; users cannot tell which "Mail Room" they are in | high | Unique, role-oriented menu names; one dashboard entry, one register entry |
| 5 | Menu language mix | Menu labels hard-code mixed Arabic/English: "سجل الصادر والوارد / Correspondence Register", "صادر - Outgoing", "وارد - Incoming", "تسجيل كتاب وارد" beside all-English siblings | Unprofessional mixed-language chrome in both locales; the mix is baked into the source string instead of translated per-locale | high | Single-language source strings + per-locale translations |
| 6 | Roles vs spec | Groups: Clerk, Follow-up Officer, Approver, Legal Manager, Auditor (read only), + Registrar (مسؤول السجل) | Role set exists (good) but group names are en-only; a sixth Registrar group overlaps Clerk conceptually and is granted separately | medium | Keep 5-role model, localize names, define Registrar as an addition to a base role or fold into Clerk |
| 7 | Cron/automation | 4 legal crons active (deadline scan hourly; obligation generate/late daily; POA lapse daily); stock crons incl. "Publisher: Update Notification", disabled Fetchmail | Legal crons exist (good); publisher-update and unused mail crons are noise; no cron for correspondence reply-deadline chasing distinct from generic scan | medium | Keep legal crons, silence irrelevant stock crons, add reply-due escalation if redesign keeps register |
| 8 | Technical leftovers | Installed: api_doc, web_tour, iap/iap_mail, google_gmail, web_unsplash, base_install_request; admin default-lands on generic screen; Apps/Settings fully exposed | Non-functional Enterprise-ish/technical modules clutter Apps and Settings for the admin persona; api_doc exposes /doc | medium | Trim to needed modules; document what admin should see |
| 9 | Empty registers | legal_poa: 0 rows, legal_fee: 0 rows, legal_sla_escalation: 0 rows | Menus lead to empty lists with stock "create" empty state; no guidance, and demo data (legal_iq_demo) covers only 6 cases/14 letters/15 docs | medium | Seed representative demo data per register or provide action-specific empty-state help |
| 10 | Dashboard architecture | Two custom OWL client actions: "The Mail Room" (tag legal_mail_room) and "My Desk" (tag legal_desk) | Dashboards exist but are split; no single role dashboard for clerk/officer/approver/manager/auditor as spec requires | high | One role-aware dashboard covering intake, deadlines, approvals, workload |
| 11 | Admin lockout | No legal ACL includes base.group_system or is global (verified: 0 rows); admin is in no legal group | **Admin sees the whole Legal menu but every click throws "Access Error" dialogs** — Mail Room, My Desk, Files, Correspondence all blocked for the system administrator; menus are shown for models the user cannot read | critical | Either grant admin/system a support role or hide menus by group; never render a menu tree that 100% errors |
| 12 | Default landing | Admin's default app after login is **Discuss** (empty "No conversation selected") | The legal system is not the landing app even on a legal-department database; first impression is an empty chat client | medium | Land users on the (role-aware) legal dashboard |
| 13 | Admin apps menu | Apps dropdown for admin shows only **Discuss, Apps, Settings** — no Legal app at all (menus themselves are group-less except Configuration=manager, Mail Room/My Desk=clerk; the app disappears because admin fails the action-model ACL check) | The system administrator cannot even reach the legal configuration (procedure types, fee schedules, SLA rules) that ships in data modules; only clerks/managers can see the app | critical | Give admin/support an explicit path to the app and its configuration |
| 14 | Officer/Approver access | Follow-up Officer has ACLs on only 4 legal models, Approver on 2; dashboards read legal.case + legal.correspondence which neither can read | Two of the five spec roles get the same Access Error walls as admin across nearly the whole app including both dashboards | critical | Grant every role read access to the surfaces its dashboard and menus expose; deny by record rule, not by missing ACL |
| 15 | Error UX | Denied access renders as a blocking modal over a blank canvas, in English, quoting model names (legal.case) and internal group paths | Non-technical Arabic-speaking staff will routinely see untranslated technical modals; no graceful degraded/empty state anywhere | high | Localized, human-readable denial states; hide what a role cannot open |

(Visual findings from the screenshot walk are in the next section's numbered notes and in the table rows added below it.)

## Admin menu map (from ir.ui.menu, verified in UI)

Top level app: **Legal** (`legal_core.menu_legal_root`, id 114) — the only custom app. Structure and actions:

- **Mail Room** → ir.actions.client 532 "The Mail Room" (tag `legal_mail_room`) — OWL dashboard
- **My Desk** → ir.actions.client 533 "My Desk" (tag `legal_desk`) — OWL dashboard
- **Operations**
  - Files → act_window 527 `legal.case` (kanban,list,form,calendar)
  - My Files → act_window 529 "My Desk" `legal.case` (kanban,list,form)
  - Overdue → act_window 528 `legal.case`
  - Blocking Documents → act_window 520 `legal.case.document` (list only)
  - Compliance Calendar → act_window 526 `legal.obligation.instance` (list,calendar,form)
  - Escalations → act_window 531 `legal.sla.escalation` (list only)
- **Registers**
  - سجل الصادر والوارد / Correspondence Register
    - Mail Room → act_window 169 `legal.correspondence` (list,kanban,form,calendar)
    - تسجيل كتاب وارد → act_window 174 wizard `legal.correspondence.register.wizard`
    - صادر - Outgoing → act_window 170; وارد - Incoming → act_window 171
    - Awaiting Reply → act_window 172; Contact Notes → act_window 173
  - Company Documents → act_window 162 `legal.document` (list,calendar,form)
  - Renewals Due → act_window 163 `legal.document`
  - Legal Entities → act_window 156 `legal.entity`
  - Government Bodies → act_window 154 `legal.gov.body` (list,kanban,form)
  - Powers Of Attorney → act_window 524 `legal.poa`
  - Fees Paid → act_window 522 `legal.fee` (list only)
  - Action Trail → act_window 530 `legal.action.log`
- **Configuration**
  - Government Bodies: Bodies (154 again — same action as the register), Body Types (155), Jurisdictions (153)
  - Procedures: Procedures (514), Steps (515), Phases (516), Transitions (518), Capture Fields (517), Document Requirements (519), Fee Schedule (521), Service Levels (523), Recurring Obligations (525)
  - Documents: Document Types (160), Document Kinds (161)
  - Correspondence: Registers (166), Correspondence Kinds (167), Letter Templates (168)
  - Entities: Legal Forms (157), Identifier Kinds (158), Signatories & Seals (159)

Notes: "Government Bodies" exists under both Registers and Configuration pointing at the *same* action 154 (duplicated menu). No menu for legal.licence.grade (model exists, config data from legal_iq_chamber, unreachable from UI). Menu translations ar_001: none.

## Settings audit

- **Users** (screens admin__39/40): admin/Administrator + 5 role users, Arabic names, logins clerk@legal.iq … auditor@legal.iq, all lang=ar_001 tz=Asia/Baghdad. Groups per user = exactly one legal group each (clerk/officer/approver/manager/auditor). Admin partner has no tz set.
- **Groups**: legal_core groups Clerk(32), Follow-up Officer(33), Approver(34), Legal Manager(35), Auditor (read only)(36) + legal_correspondence Registrar (مسؤول السجل)(37) — Registrar assigned to no user.
- **ACL coverage per group** (legal models, from ir.model.access): Auditor 37 read-only ACLs (0 with write — the read-only intent holds at ACL level); Clerk 43 (17 writable); Manager 37 (36 writable); **Follow-up Officer only 4 ACLs** (gov.body, poa, poa.revoke, sla.escalation) and **Approver only 2** (entity, letter.template) — officer and approver users will hit the same Access Error walls as admin on most of the app, including the two dashboards (which read legal.case/legal.correspondence). 24 record rules exist on legal models. Severity high: two of the five spec roles cannot operate the core workflow surfaces at all.
- **Languages**: active = ar_001 "Arabic / الْعَرَبيّة" and en_US only.
- **Currencies**: **USD only active — confirmed**; company "شركة الرافدين للتجارة والمقاولات العامة المحدودة" uses USD. No IQD row active.
- **Scheduled actions** (ir.cron): 15 total — legal: `Legal: deadline scan and escalation` (hourly), `Legal: generate obligation periods` (daily), `Legal: mark obligation periods late` (daily), `Legal: lapse expired powers of attorney` (daily); stock: auto-vacuum, portal deletion, mail queue, publisher update notification (weekly), old-notification cleanup, fetchmail (disabled), scheduled messages x2, web push, discuss unmute, unregistered-users notify.
- **Apps inventory** (30 installed): base stack (base, web, mail, bus, resource, rpc, html_editor, base_setup, base_import, base_import_module, base_install_request, auth_signup/totp/totp_mail/passkey, google_gmail, iap, iap_mail, api_doc, web_tour, web_unsplash) + 9 legal modules + legal_iq_demo. No accounting, no contacts app menu, no calendar app — Compliance Calendar is the only calendar surface.
- **Content packs**: legal_iq_registrar/tax/chamber/social_security/residency contribute *data only* (procedure types, steps, fee rules, gov bodies, resource calendars with Iraqi holidays) — 23 procedure types, all Arabic-titled under en_US key.

## Browser walk — visual findings

**Dominant result: as admin, every legal screen is an "Access Error" modal.** Navigating to any legal action URL (dashboards 532/533, Files 527, Overdue 528, Blocking Documents 520, Compliance Calendar 526, Escalations 531, Company Documents 162, Renewals 163, correspondence 169-174, all Configuration actions) renders an empty grey canvas with a modal: *"You are not allowed to access 'X' records. This operation is allowed for the following groups: - Legal Department/Auditor (read only) - Legal Department/Clerk - Legal Department/Legal Manager. Contact your administrator to request access if necessary."* — shown **to the administrator himself** (screens admin__04 … admin__38, e.g. `admin__04_mail_room_dashboard.png`, `admin__14_company_documents.png`).

Per-screen observations:

1. **admin__01_login** — stock Odoo login, English, no branding for the legal department, no Arabic. Low.
2. **admin__02_default_home** — admin lands in **Discuss** with "No conversation selected"; the channels are "Administrators"/"general". A legal-department database greets its admin with an empty chat app. Medium.
3. **admin__03_apps_dropdown** — the apps menu contains only *Discuss, Apps, Settings*. The Legal app is invisible to admin (ACL-driven menu filtering; see table #13). Critical.
4. **admin__04/05 dashboards, admin__06-16 legal actions** — all Access Error modals as above. The custom OWL dashboards do not degrade gracefully: the failed RPC surfaces as a blocking modal on a blank page rather than an in-place empty/denied state. The dialog leaks technical identifiers (`legal.correspondence`, internal group names) — poor for non-technical users who will see the same dialog whenever a record rule or ACL bites (e.g. officer opening a clerk-only wizard). High.
5. **Top navbar** — the Arabic company name "شركة الرافدين…" is truncated in the LTR systray with the ellipsis mid-name (`admin__04`); with an English UI and long Arabic names the navbar handles bidi text poorly. Low.
6. **admin__39_settings_users** — Users list: the new Odoo 19 "Role" column shows only generic *User* badges for all five staff; the legal role (clerk/officer/…) is invisible in the list, so an administrator cannot tell who holds which legal role without opening each form. Medium.
7. **admin__40_settings_user_form** — Admin's own form shows the app-provided privilege selector "LEGAL DEPARTMENT → Legal Department: No" (radio) — the legal roles are exposed as a proper privilege section (good), but admin is left at "No" with no visibility into the app.
8. **admin__41_settings_groups** — Groups list confirms privilege "Legal Department" with 6 groups: Approver, Auditor (read only), Clerk, Follow-up Officer, Legal Manager, Registrar (مسؤول السجل) — the Registrar name mixes scripts in one label.
9. **admin__42_settings_languages / admin__43_settings_currencies** — Active languages: Arabic + English (US) only, of 92. Currencies: **only USD toggled active of 170; IQD not active** — visual confirmation of the SQL finding. All rates 1.000000, no "Last Update".
10. **admin__44_settings_cron** — 14 scheduled actions; the four `Legal:` crons are present and active (deadline scan hourly at :45; obligation generate/late daily; POA lapse daily). Stock crons (web push, discuss unmute, publisher update) remain as noise.
11. **admin__45_apps** — Apps kanban advertises the whole Odoo store on a Community build: Enterprise-only tiles (Accounting, Knowledge, Studio, MRP II, Timesheets…) with "Upgrade" buttons beside Activate-able Community apps. The one custom app of this database (Legal) is not what the page surfaces first — it markets Sales/Restaurant/Invoicing instead. Low/medium noise for the admin persona.
12. **admin__46_general_settings** — General Settings has **no section for the Legal app** (no res.config.settings integration: no default register, numbering, SLA calendar, or IQD/locale options). Only stock Users/Languages/Companies blocks. Medium.
13. **JS console**: zero `console.error/warning` and zero uncaught `pageerror` events across the entire 48-screen walk (listener capture file empty). The access failures are handled RPC errors surfaced as dialogs, not crashes. The webclient itself is technically healthy for admin.
14. **Breadcrumbs**: on every legal action the breadcrumb never rendered (no view mounted behind the error modal); only Settings screens produced breadcrumbs (Users, Groups, Languages, Currencies, Scheduled Actions, Apps, Settings). No horizontal overflow detected at 1366x768 or 1920x1080 on any captured screen — but note nothing content-heavy ever rendered for admin.

## Walk completion status

48 screenshots captured (admin__01 … admin__48; `admin__49_hd_case_form` skipped — no kanban records clickable behind the access modal). All legal record-open attempts reported "no records" because lists never loaded (ACL). View-switcher and search-panel interactions could not run for the same reason. Evidence directory: `docs/ui-audit/before/`.

## Overall inventory (admin perspective)

- Apps visible to admin: Discuss, Apps, Settings — nothing else.
- Apps visible to legal staff: Legal (plus Discuss). No Contacts, Calendar, or Documents app on this Community build.
- Custom client actions: 2 OWL dashboards (legal_mail_room, legal_desk). Custom models: 44 legal.* models. Menus: 51 legal menus. Window actions: 40.
- Data volume: 6 cases, 14 correspondence, 15 documents, 39+ gov bodies, 41 obligation periods, 23 procedure types, 19 action-log rows; 0 POAs, 0 fees, 0 escalations.
- Iraqi content packs (registrar/tax/chamber/social_security/residency) are data-only modules feeding procedure/document/fee/obligation configuration — all titled in Arabic under `en_US`.

