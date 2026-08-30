# DMA Accreditation — تفويض المؤسسات العاملة في إزالة الألغام

Odoo 19 Community addon for the **Directorate of Mine Action** (دائرة شؤون الألغام).
It implements the two-phase accreditation process of demining organisations
described by **IMAS 07.30** and **TNMA 07.30/01**:

1. **Office Accreditation — التفويض المكتبي**
   reception → General Director initial acceptance → Legal Department review →
   Certifications Division prerequisites checklist → official letter.
2. **Operational Accreditation — تفويض العمليات**
   SOP submission (paper *and* electronic) → SOP reading fee → parallel
   Finance/Operations sign-off → operational demonstration fee → Accreditation
   Committee decision → legal refinement → certificate.

Every transition is guarded **server side**, appended to an **immutable approval
log**, posted to the chatter and pushed to the next department as a scheduled
activity.

* License: **LGPL-3**
* Version: `19.0.1.1.0`
* Depends: `base`, `mail`, `web` only — no Enterprise, no OCA modules.

---

## 1. Requirements

| Component | Version |
|---|---|
| Odoo | 19.0 Community |
| Python | 3.11 or 3.12 |
| PostgreSQL | 12 or later (13+ recommended by upstream Odoo) |
| wkhtmltopdf | optional — only needed to render the PDFs |
| rtlcss | recommended for the Arabic interface (`npm install -g rtlcss`) |

Without `wkhtmltopdf` the module still installs and the whole workflow runs: PDF
generation is best-effort and a failure is logged in the chatter instead of
blocking the officer (see [§7](#7-official-documents)).

Without `rtlcss`, Odoo cannot mirror its stylesheets and logs
*"You need https://rtlcss.com/ to convert css file to right to left
compatiblity"* on every asset build. The Arabic text and the reading direction
are still correct, but the paddings and the icons stay laid out for a
left-to-right screen — install it on any server that will actually be used in
Arabic.

---

## 2. Installation

```bash
# 1. put the addon on the addons path
cp -r dma_accreditation /path/to/custom_addons/

# 2. point Odoo at it (odoo.conf)
#    addons_path = /path/to/custom_addons,/path/to/odoo/addons

# 3. create the database and install
odoo-bin -c odoo.conf -d dma_prod -i dma_accreditation --stop-after-init

# ... or with the demo dataset (8 demo users, 3 companies, 5 sample files)
odoo-bin -c odoo.conf -d dma_demo -i dma_accreditation --with-demo --stop-after-init
```

> **Odoo 19 note** — demo data is *off* by default; you must pass `--with-demo`
> explicitly. `--without-demo=all` is the inverse switch.

To add the addon to an existing database: *Apps → Update Apps List →* search
**DMA Accreditation** *→ Activate*.

### Arabic interface

*Settings → Translations → Languages → Add* **Arabic / العربية**, then set the
language on each user (*Settings → Users → Preferences → Language*). Odoo
switches the whole backend to RTL automatically. The module ships a complete
`i18n/ar.po`, so no further import is needed.

### Running it permanently on this machine

A permanent instance is installed and serving the `dma_accreditation` database:

| | |
|---|---|
| URL | <http://localhost:8070> |
| Database | `dma_accreditation` (pinned; no database selector) |
| Config | `odoo19_dma_service.conf` |
| Log | `.odoo_data_dma/odoo-dma.log` |
| Autostart | a `.vbs` launcher in the user's Startup folder, so it comes up at logon |
| Start / stop by hand | `scripts/dma_odoo_start.cmd` / `scripts/dma_odoo_stop.cmd` |

The launcher puts the official Odoo installation's `thirdparty` directory on
`PATH`, which is where `wkhtmltopdf.exe` lives, so the letters and certificates
come out as real PDFs on this instance.

To serve it instead from the **official Odoo Windows service**
(`odoo-server-19.0`, port 8069, which starts before anyone logs in), run this
once **as Administrator**:

    powershell -ExecutionPolicy Bypass -File "<repo>/scripts/dma_install_into_odoo_service.ps1"

It backs up that service's `odoo.conf`, adds this addon to its `addons_path`
and restarts the service. Both instances share the same PostgreSQL, so they see
the same databases.

---

## 3. Roles and who does what

The module creates the privilege **DMA Accreditation** with eight groups.
Assign them in *Settings → Users & Companies → Users →* open a user *→ the*
**DMA Accreditation** *selector on the Access Rights tab*.

| Group (technical name) | Arabic | Acts on which step | Sees |
|---|---|---|---|
| `group_dma_reception` | شعبة الاستلام | creates the file, submits it, forwards it to the General Director, resumes returned files | Reception queue |
| `group_dma_general_director` | المدير العام | initial acceptance (القبول الأولي); may also grant the office accreditation | Initial Acceptance queue, All Requests, Approvals Log |
| `group_dma_legal_director` | مدير القسم القانوني | legal review, then legal refinement (التنقيح القانوني) and issuing the final authorisation | Legal queue |
| `group_dma_cert_officer` | شعبة التصديقات | verifies the prerequisites checklist (الأوليات) and grants the office accreditation | Certifications queue |
| `group_dma_operations` | قسم العمليات | opens the operational phase, registers the paper SOP, confirms the SOP for appraisal | Operations queue |
| `group_dma_finance` | القسم المالي | registers and confirms both fees, confirms receipt of the request and of the SOP fee | Finance queue, Fees |
| `group_dma_committee` | لجنة منح التفويض | records the committee decision | Committee queue |
| `group_dma_manager` | مدير التفويض | implies **all** of the above, plus Configuration and deletion of drafts | everything |

The **Accreditation Manager** group implies every other group, so a manager can
unblock any step. `admin` is put in that group at install time.

### What each role sees when they log in

Opening the **DMA Accreditation** app shows a shield icon in the app switcher.
Inside:

* **My Queue**
  * *Waiting for Me* — every file currently on this user's desk, whatever the
    department. This is the one menu everybody has; it uses the `My Turn`
    filter, which understands that during the dual confirmation a file is on
    Finance's desk **and** on Operations' desk until each of them has signed.
  * one further entry **per department**, visible only to that department
    (*Reception*, *Initial Acceptance*, *Legal Department*, *Certifications
    Division*, *Operations*, *Finance*, *Accreditation Committee*).
* **Dashboard** — the landing page for every department: how many files are
  waiting for *you*, the whole pipeline as a bar per step, one row per queue you
  belong to, and the accreditations expiring in the next 90 days. Every tile
  drills through to the matching list.
* **All Requests** — kanban grouped by status, plus list, activity, graph and
  pivot views (manager and General Director only).
* **Fees** — every fee line with a *To Confirm* filter (Finance and manager).
* **Approvals Log** — the read-only audit trail (manager and General Director).
* **Configuration** — Document Types, Accreditation Scopes, Settings (manager).

### The progress rail

Every request form opens with a rail of the thirteen steps: green for signed
(naming the officer who signed and when), highlighted for the current one, amber
when it is blocked — and underneath, **exactly what is blocking it**, document by
document. It replaces guessing at a status bar with reading a sentence.

The rail is drawn by an OWL component from a `progress_payload` Json field, so
the rule for what counts as "blocked" lives in Python next to the gates it
mirrors, and is covered by the Python tests. The component itself holds no
business logic and is covered by its own hoot tests.

On a request form, the **header shows only the buttons the logged-in user may
press in the current status**. A Finance officer looking at a file in *Legal
Review* sees no action button at all; the same user in *SOP Reading Fee* sees
*Confirm SOP Reading Fee*, *Return* and *Reject*. The `groups=` and
`invisible=` attributes keep the screen clean, and the Python guard behind each
button raises `AccessError` if the call is attempted anyway (by RPC, for
instance).

---

## 4. Walking a file through the process

### Phase 1 — Office Accreditation (التفويض المكتبي)

| # | Status | Who | Button | What it checks |
|---|---|---|---|---|
| 1 | `draft` | Reception | **Submit** | at least one accreditation scope |
| 2 | `submitted` | Reception | **Send to General Director** | — |
| 3 | `gd_review` | General Director | **Initial Acceptance** | — |
| 4 | `legal_review` | Legal Director | **Legal Approval** | — |
| 5 | `cert_check` | Certifications Division | **Grant Office Accreditation** | **HARD GATE**, see below |

On success of step 5 the module, in one transaction:

* allocates the office reference from the `DMA/OFF/%(year)s/xxxx` sequence and
  stamps the date;
* e-mails the applicant the *Office Accreditation Granted* notification
  (**إشعار إلى المعني**);
* renders the **Office Accreditation Letter** PDF and attaches it to the file;
* logs the decision and schedules the next department's activity.

### Phase 2 — Operational Accreditation (تفويض العمليات)

| # | Status | Who | Button | What it checks |
|---|---|---|---|---|
| 6 | `office_granted` | Operations / Reception | **Start Operational Accreditation** | — |
| 7 | `sop_submission` | Operations | **Register Paper SOP**, then **Confirm SOP Submission** | electronic SOP attached **and** paper copy registered |
| 8 | `sop_fee` | Finance | **Confirm SOP Reading Fee** | a *confirmed* `sop_reading` fee line exists |
| 9 | `dual_confirm` | Finance **and** Operations, in any order | **Finance Confirmation** / **Operations Confirmation**, then **Proceed to the Demonstration Fee** | **HARD GATE**, see below |
| 10 | `demo_fee` | Finance | **Confirm Demonstration Fee** | a *confirmed* `operational_demo` fee line exists |
| 11 | `committee` | Accreditation Committee | **Record Committee Decision** | decision, session date and decision text are filled in |
| 12 | `legal_refine` | Legal Director / General Director | **Issue Operational Accreditation** | refined decision text is filled in |
| 13 | `authorized` | — | — | certificate number, issue and expiry dates, certificate PDF, final e-mail |

A committee decision of *Rejected* closes the file at step 11 instead of moving
it on. *Approved* and *Approved with Conditions* both continue to the legal
refinement.

### The two hard gates

Both are enforced in Python, **not** in the view, so they hold for RPC calls,
imports and scripts as well.

1. **Prerequisites checklist** — `action_grant_office_accreditation()` raises
   `ValidationError` unless *every* line flagged *Required* is both **Provided**
   and **Accepted**, and the checklist is not empty. The error names the
   offending documents. The form shows a blue banner with the `7 / 10` progress
   while the gate is closed.
2. **Dual confirmation** — `action_dual_confirm_done()` raises
   `ValidationError` unless **both** `finance_confirmed_sop_fee` and
   `operations_confirmed_sop` are set. Each side may sign first; each side may
   only sign once.

### Why the buttons are the only way in

`readonly="1"` is a client-side hint in Odoo 19: it stops nobody who talks to
the server directly. Every department needs write access to the request (to
type the SOP reference, attach the committee minutes, correct a phone number),
so the fields that carry the *legal* meaning of the file are protected in
`write()` instead:

`name` · `state` · `return_to_state` · `submission_date` · `office_ref` ·
`office_date` · `certificate_ref` · `issue_date` · `expiry_date` ·
`sop_paper_received(_by/_date)` · `finance_confirmed_sop_fee(_by/_on)` ·
`operations_confirmed_sop(_by/_on)` · `legal_refined_by(_on)` ·
`reject_reason` · `return_reason` · `verification_token`

Writing any of them raises `AccessError` unless the call comes from a workflow
method — including under `sudo()`. The kanban is likewise **not**
drag-and-drop: dropping a card in another column would write `state` straight
to the database.

The same reasoning applies to the checklist. Reception assembles the file — it
may attach documents and tick *Provided* — but `is_required` and
`review_result` may only be written, and a line may only be deleted, by the
**Certifications Division** (or the Accreditation Manager). Otherwise the
department that submits the file could open its own gate.

### Returning and rejecting

Every review status has **Return** and **Reject** buttons, restricted to the
department that owns the step. Both open the same small wizard, which
**requires a reason**. The reason is written to the record, posted to the
chatter, appended to the approval log and e-mailed to the applicant contact.

A returned file moves to `returned` and remembers where it came from
(`return_to_state`, exactly one step back). Reception then presses **Resume
Request** and the file lands back on that step.

### Resetting a file

The Accreditation Manager can **Reset to Draft** from any status. The evidence
stays on the file — the documents, the fees, the SOP and the whole approvals
log — but the *attestations* of the previous pass are dropped: the paper-SOP
receipt and both dual-confirmation sign-offs have to be given again. A sign-off
says "I checked this, on that day"; replaying the process must not inherit it.

A file that carries any decision at all can no longer be **deleted**, even back
in draft and even by the manager: `dma.approval.line` cascades on the request,
so deleting it would erase the audit trail through the back door. Archive it
instead.

---

## 5. Configuration

*DMA Accreditation → Configuration* (Accreditation Manager only).

### Settings

Settings live on their own model (`dma.accreditation.settings`) rather than on
`res.config.settings`, because saving the latter is reserved to users of
*Administration / Settings* — an Accreditation Manager would see the form and
then be unable to save it. The values are still ordinary system parameters.

| Setting | `ir.config_parameter` key | Default |
|---|---|---|
| SOP Reading Fee | `dma_accreditation.sop_fee` | `250.0` |
| Operational Demonstration Fee | `dma_accreditation.demo_fee` | `500.0` |
| Accreditation Validity (months) | `dma_accreditation.validity_months` | `12` |
| Expiry Warning (days) | `dma_accreditation.expiry_warning_days` | `90` |

The two fee amounts are proposed by default on a new fee line; an officer can
still type a different amount. The validity drives the **expiry date** of the
operational accreditation certificate (`issue_date + N months − 1 day`).

The expiry warning is how long before a certificate runs out the Accreditation
Manager starts being reminded of it.

The keys are plain system parameters, so they can also be set from a data file
or from `Settings → Technical → System Parameters`. Two more parameters have no
dialog because they are rarely touched:
`dma_accreditation.dossier_max_bytes` (default 200 MB) caps the size of a
generated dossier archive, and it is the only thing standing between a file with
half a gigabyte of scans and a worker running out of memory.

### Document Types (الأوليات)

Ten types are seeded from the IMAS/TNMA 07.30 application documents:

company registration certificate · organisational structure · key staff CVs and
qualifications · equipment list · insurance (staff medical and third-party
liability) · safety and occupational health policy · quality management
documentation · prior demining experience · financial capability statement ·
power of attorney of the representative.

On the Documents tab, Reception can **Mark All Provided** while assembling a
file, and the Certifications Division can **Accept All Provided** in one press
instead of ticking ten rows; both go through the same guards as the individual
buttons.

The list is editable: reorder with the handle, rename (the name is
translatable), toggle *Required by Default*, or archive a type that no longer
applies. **A request gets its checklist when it is created**, so changing the
configuration does not rewrite existing files; use the **Reload Checklist**
button on the Documents tab to pull in newly created types.

### Service Levels

*Configuration → Service Levels* is one editable table:
**Step · Department · Target · Warn before · Escalate after**, all in days.

The shipped rows are **starting values, not legal deadlines** — the module has
no business deciding how long the Legal Department may hold a file, so the
Accreditation Manager is expected to replace them with whatever the
Directorate's service charter says. They are shipped anyway because a time
control layer that arrives empty measures nothing and is quietly ignored.

Two rows are worth pointing at:

* the **dual confirmation** carries one row per department, because Finance and
  Operations are answerable for it at the same time;
* **Returned to Applicant** deliberately carries no row. The Directorate is not
  holding the file then, so the engine reports it as *paused* rather than
  letting a company's own delay count against a department.

### Accreditation Scopes

Eight scopes are seeded: Manual Clearance, Battle Area Clearance, EOD, Mine
Detection Dogs, Mechanical Demining, Technical Survey, Non-Technical Survey and
EORE. They are displayed as coloured tags on the request, the kanban card, the
letter and the certificate.

---

## 6. Data model

| Model | Purpose |
|---|---|
| `dma.accreditation.request` | the accreditation file; `mail.thread` + `mail.activity.mixin` |
| `dma.request.document` | one prerequisites checklist line |
| `dma.document.type` | configurable catalogue of prerequisite documents |
| `dma.fee.payment` | a fee (`sop_reading` / `operational_demo`) with its receipt |
| `dma.accreditation.scope` | a demining activity the organisation is accredited for |
| `dma.approval.line` | **immutable** audit trail of every transition |
| `dma.decision.reason` | transient wizard collecting the return/reject reason |
| `dma.accreditation.settings` | transient settings dialog owned by the Accreditation Manager |
| `dma.document.submission` | **immutable** superseded version of a checklist line's evidence |
| `dma.sla.rule` | the target, warning and escalation delays of one step |
| `dma.sla.escalation` | **immutable** record of one overrun of a service level |
| `dma.document.replacement` | transient wizard that files a version away and attaches its replacement |

Server methods feed the interface and keep its logic testable in Python:
`_compute_progress_payload` (the progress rail and its blockers),
`get_dashboard_data` (every number on the dashboard, counted through the record
rules), `_dossier_index` (the dossier, shared by the screen, the printed index
and the archive) and the three analytics payloads of
[§12](#12-time-control-and-process-performance).

### Why the approval log cannot be edited

`ir.model.access.csv` grants **read only** on `dma.approval.line` to every
group, including the manager, and `write()` / `unlink()` are overridden to raise
`UserError` — even under `sudo()`. Lines are appended by the workflow methods
only. The log survives a *Reset to Draft*: it records what happened, not what
the record looks like now.

### Sequences

| Sequence code | Prefix |
|---|---|
| `dma.accreditation.request` | `DMA/ACC/%(year)s/0001` |
| `dma.accreditation.office` | `DMA/OFF/%(year)s/0001` |
| `dma.accreditation.certificate` | `DMA/CERT/%(year)s/0001` |

---

## 7. Official documents

Three QWeb reports, Arabic-first and RTL, are bound to the request (*Print* menu
and header buttons):

1. **Office Accreditation Letter** — addressed to the General Director, carries
   the office reference, the organisation, the requested scopes, the verified
   prerequisites table and the QR verification code.
2. **Operational Accreditation Certificate** — A4 landscape, framed, certificate
   number, scopes, issue and expiry dates.
3. **Accreditation File Summary** — the whole file including the fees, the
   committee decision and the complete approvals log; this is the document to
   put in the paper folder.

Because a report bound to a model can be launched from the *Print* menu at any
step, the letter and the certificate refuse to look official before they exist:
a request without an `office_ref` (respectively a `certificate_ref`) prints a
framed **NOT GRANTED** / **NOT ISSUED** notice naming the current status
instead of the document.

The Arabic body and the Latin subtitle are deliberately *not* both translated:
the subtitles are rendered as literals so an Arabic reader still gets the
bilingual letterhead. The direction rules in the SCSS carry `/*rtl:ignore*/`
so `rtlcss` does not mirror an already right-to-left document back to
left-to-right for exactly the users who need it most.

### Letterhead

`report/report_office_letter.xml` defines a shared `report_dma_letterhead`
template with two dashed placeholders (`[ EMBLEM ]` and `[ LETTERHEAD ]`).
Replace the two `<div class="dma-emblem-placeholder">` blocks with the official
emblem images, for example:

```xml
<img src="/dma_accreditation/static/description/emblem.png" style="height: 58px;"/>
```

Typography, rules, table borders and the certificate frame live in
`static/src/scss/dma_report.scss`, loaded into `web.report_assets_common`.

### QR verification and the e-signature integration point

Each request gets a random `verification_token` (uuid4 hex) at creation. Every
official document embeds it as a QR code through Odoo's barcode controller:

```xml
<img t-att-src="'/report/barcode/QR/%s?width=180&amp;height=180&amp;quiet=0' % o.verification_token"/>
```

> The barcode type string on Odoo 19 is **`QR`**, not `QRCode`; an unknown type
> silently falls back to Code128. `width` and `height` must both be given and
> equal, otherwise the default `600×100` produces a stretched, unscannable code.

This makes the document **digitally verifiable** — a third party can check the
code against the register of the Directorate — but it is **not** a
cryptographic signature. The intended integration point for the national
e-signature (PKI) is marked with a comment in `report_dma_qr_block`: once a
national CA is available, sign the rendered PDF and print the signature
reference next to the QR.

`request.get_verification_url()` returns the public URL the QR points at
(`<web.base.url>/dma/verify/<token>`); serving that route is left to the
Directorate's public portal.

---

## 8. Notifications

Three `mail.template` records, Arabic body with an English summary underneath:

| Template | Sent when |
|---|---|
| `mail_template_office_granted` | the office accreditation is granted |
| `mail_template_request_returned` | the file is returned **or** rejected, with the reason |
| `mail_template_operational_granted` | the certificate is issued |

They are addressed to the **contact person** of the request and fall back to the
applicant organisation: `_mail_get_partner_fields` puts `contact_partner_id`
ahead of `partner_id`, which also makes the chatter propose the right recipient
when an officer writes a message by hand. If neither is known the module posts a note in the chatter instead of
failing the transition. Mails are queued (`force_send=False`) and go out with
the outgoing-mail cron.

In addition, every transition schedules a **to-do activity** for the users of
the next responsible group, and closes the automated activities of the previous
step, so a department's *Activities* view is always the real backlog.

---

## 9. Tests

```bash
odoo-bin -c odoo.conf -d dma_test -i dma_accreditation --with-demo \
         --test-enable --test-tags /dma_accreditation --stop-after-init
```

Three suites, run separately:

```bash
# 1. Python + browser tours (the tours need Chrome, see below)
odoo-bin -c odoo.conf -d dma_test -i dma_accreditation --with-demo          --test-enable --test-tags /dma_accreditation --stop-after-init

# 2. JavaScript unit tests (hoot). They run through web's own runner,
#    so --test-tags /dma_accreditation does NOT pick them up.
odoo-bin -c odoo.conf -d dma_test --test-enable --stop-after-init          --test-tags "/web:WebSuite.test_unit_desktop[@dma_accreditation]"
```

165 Python tests in nine files:

* `test_workflow.py` — the full happy path `draft → authorized` acted by a
  different user at every step, both dual-confirmation orders, the committee
  rejection branch, `pending_group` / `My Turn` (with the computed field and its
  search domain checked against each other for every role in every status), the
  next-step activities of the parallel step, the administrative reset, and the
  refusal of visually empty rich text on the decision gates.
* `test_gates.py` — both hard gates, plus the scope, SOP, fee, committee and
  refinement pre-conditions, and the wrong-status guard.
* `test_security.py` — a wrong-role call raises `AccessError` on every step,
  creation limited to reception and manager, deletion limited to the manager and
  to never-decided drafts, the workflow-owned fields refusing direct writes
  (including under `sudo()`), the checklist verification reserved to the
  Certifications Division, the immutable approval log, the per-role menus and
  form buttons, and the return/reject wizard requiring a reason.
* `test_reports.py` — sequences, the three QWeb documents rendered to HTML
  (with the QR URL and the Arabic RTL markup asserted), the refusal to print an
  official document before it is issued, the settings round trip as the
  Accreditation Manager, the fee defaults, and `get_views()` over every view the
  module ships.

* `test_coverage.py` — returning and rejecting from every second-phase step,
  a closed file refusing both, the return/reject/authorisation notifications and
  what they carry, multi-company isolation of the files *and* of the audit trail,
  duplicating a request, archiving, reloading the checklist, resetting a fee,
  forging an approval line, the chatter and status tracking (the rest of the
  suite runs with `tracking_disable`), and the seeded configuration.
* `test_tours.py` — two **browser** walk-throughs in headless Chrome: granting
  the office accreditation entirely through the interface (watching the progress
  rail update and the blockers clear), and a department that does not own the
  step being offered no button at all.
* `test_documents.py` — the validity states against the expiry date, an expiry
  blocking only where the Directorate configured it to, replacing the evidence
  of an accepted line superseding the acceptance (and not stamping the person
  who swapped the file as its reviewer), the immutability of a superseded
  version, the replacement wizard and its refusals, duplicate detection on the
  checksum, every blocking reason, and the scheduled refresh of the stored
  validity column.
* `test_dossier.py` — the headings of the index, evidence collected from every
  corner of the file, superseded versions marked as such, the decision trail,
  and the security: never another accreditation's evidence, a partial right
  producing a partial dossier rather than an error, sanitised and de-duplicated
  archive entry names, the size ceiling, and the screen, the report and the
  archive agreeing on one reading of the file.
* `test_sla.py` — time frozen throughout: where the clock starts, the dual
  confirmation's signatures not restarting it, a second visit to a step, all
  four verdicts at their thresholds, paused and closed and archived files,
  filtering, cron idempotency, escalation to the manager and its automatic
  closure, re-escalation on a second visit, manager-only configuration, and the
  same file being exactly as late in Baghdad as in UTC.
* `test_analytics.py` — every figure asserted against a number worked out by
  hand from a fixture with a known history: the duration on the log, the
  percentile aggregate reaching PostgreSQL, per-visit stage durations, the live
  backlog, the three bottleneck orderings, throughput by month, cycle time
  measured between decisions, rework, departmental workload, and a file in
  flight never dragging a cycle time down.

Plus 7 **hoot** tests in `static/tests/accreditation_progress.test.js` covering
the progress component itself: the step states, the pending department, the
blocker list, the closed-file case, the rejected case and the RTL flip.

The report tests render **HTML**, not PDF, so the suite is green on a CI machine
without `wkhtmltopdf`. The time-dependent suites freeze the clock with
`odoo.tests.common.freeze_time`, so a service level is asserted against a date
anybody reading the test can work out rather than against the day the suite
happens to run.

> **The browser suites SKIP rather than fail when they cannot run.** Odoo looks
> for Chrome at fixed paths (on Windows: `%ProgramFiles%`, `%ProgramFiles(x86)%`
> and `%LocalAppData%\Google\Chrome\Application\chrome.exe`) and needs the
> `websocket-client` package. Missing either one raises `SkipTest`, so a green
> run on a bare CI box can mean "not run" — check the log for the skip before
> trusting it.

---

## 10. Demo dataset

`--with-demo` seeds three applicant organisations (Al-Amal Demining Company,
Sanad Mine Action Services, Nahrain Clearance Group), one user per role
(`dma_reception`, `dma_gd`, `dma_legal`, `dma_cert`, `dma_operations`,
`dma_finance`, `dma_committee`, `dma_manager`) and five requests:

| File | Status | What it shows |
|---|---|---|
| `demo_request_draft` | `draft` | a renewal still being typed |
| `demo_request_cert_check` | `cert_check` | 7 of 10 prerequisites accepted — the office gate is closed |
| `demo_request_dual_confirm` | `dual_confirm` | Finance signed, Operations has not — the dual gate is closed |
| `demo_request_authorized` | `authorized` | a fully accredited organisation with certificate |
| `demo_request_returned` | `returned` | returned by the General Director with a reason |

The demo records are **driven through the real workflow methods** by
`models/dma_accreditation_demo.py`, each step impersonating the department that
owns it — so the demo database also ships a realistic approvals log, chatter and
activity backlog instead of records with a hand-set status.

---

## 11. Document intelligence and the accreditation dossier

The prerequisites checklist used to answer one question - has the Certifications
Division accepted this document? It now answers the rest of what an officer and
an auditor actually need.

### What a checklist line knows about itself

| Field | Why |
|---|---|
| `reference`, `issuer` | the number printed on the document and who issued it |
| `issue_date`, `expiry_date` | only for the types marked **Expires** |
| `validity_state` | `no_expiry` / `valid` / `expiring` / `expired`, stored so it can be filtered and grouped |
| `version`, `superseded_count` | which version is on file, and how many came before |
| `duplicate_of_id` | another requirement carrying byte-for-byte the same file |
| `is_blocking`, `blocking_reason` | whether this line is what is holding the office accreditation up, and precisely why |

**No validity period is ever assumed.** How long an Iraqi registration
certificate or a third-party liability policy stays valid is a matter for the
issuer and for the law, so the module records the expiry date the officer reads
off the document and warns before it - nothing more. Whether a lapsed copy
*blocks* the office accreditation is a decision of the Directorate, taken per
document type with **Expiry Blocks Accreditation**, and it is off everywhere by
default.

`validity_state` is derived from today's date, so a stored value is a day stale
by tomorrow. The daily job brings it back in line; the hard gate never reads it
and asks the calendar directly, so it is never a day out.

### Versions, and one defect this release fixes

`review_result` used to survive a change of the files behind it. Reception has
write access to the checklist because it assembles the file, so an accepted line
could have its evidence swapped for something nobody had looked at - and the
hard gate would still open on it.

A sign-off says *"I checked **this** on that day"*. So from now on, replacing the
evidence of a reviewed line:

1. freezes the state it was in into a `dma.document.submission` - the files, the
   verdict, who gave it and when, and the reason for the replacement;
2. resets the line to *Pending*, without stamping the person who swapped the file
   as its reviewer;
3. says so in the chatter.

Nothing else about the workflow moves. Previous evidence is never destroyed, the
version rows are as immutable as the approval log, and the attachments are
**referenced, never copied** - four versions of an insurance policy are four
files in the filestore, not eight.

The **Replace Document** dialog is the polite way in: it takes the new file, what
the new document says about itself, and a reason, and the reason lands on the
version being superseded, where it belongs.

### Duplicate detection

Matched on the SHA-1 checksum `ir.attachment` computes server side, so it is the
bytes that are compared and not the name an applicant chose. It is a **warning,
never a refusal**: one PDF can legitimately be both the registration certificate
and the proof of legal representation, and it is the Certifications Division that
decides whether that is acceptable.

### The accreditation dossier

*"Show me the complete evidence and decision trail for DMA/ACC/2026/0042."*

The **Dossier** tab assembles exactly that, from the record itself, in the order
an auditor reads a paper file: the application, the prerequisites (one block per
requirement, with its verdict, its validity and every version), the SOP, the fee
receipts, the committee minutes, the documents the Directorate issued, any other
correspondence, and the decision trail with how long each step took.

One reading of the file feeds three consumers, so they can never disagree:

* the **panel** on the form;
* the **printed index** (*Print Index*), a QWeb report in the same bilingual
  house style as the letter and the certificate;
* the **archive** (*Download Dossier*), built on demand and never stored, so a
  dossier costs no second copy of a single byte. It carries the same index as
  its cover sheet, in HTML: rendering that template through `wkhtmltopdf` costs
  around a minute on a plain server against ten milliseconds for the markup, an
  officer waiting on a download should not be waiting on a PDF engine, and the
  archive then has an index even where no PDF engine is installed at all.

The archive is laid out the way the index reads:

```
DMA_ACC_2026_0042/
  00_DMA_ACC_2026_0042_index.html
  02_prerequisites/registration/company-registration.pdf
  02_prerequisites/insurance/insurance-2026.pdf
  02_prerequisites/insurance/superseded/insurance-2025.pdf
  03_sop/SANAD-SOP-2026.pdf
  04_fees/receipt-0141.pdf
  ...
```

Security, in the order it is applied:

1. the route takes the **request**, never a list of attachment ids, so nobody can
   ask for somebody else's evidence by guessing numbers;
2. the reader is checked against the record before a single byte is read;
3. every attachment is filtered through `ir.attachment`'s own access rules - a
   reader who may not see one piece of evidence gets a dossier **without it**
   rather than an error;
4. anything filed against another accreditation is dropped and logged, however it
   got into the set;
5. archive entry names are sanitised and de-duplicated. Odoo's own ZIP builders
   write the attachment name in verbatim, which lets a file called
   `../../evil.exe` write outside the extraction directory on a careless
   extractor; that is not repeated here.

### Preparing for OCR, without doing OCR

The document layer is deliberately structured so text extraction can be added
later without a migration: content already flows through `ir.attachment`, whose
`index_content` is the extension point, and Odoo Community ships
`attachment_indexation` (LGPL-3, depends only on `web`) which extracts PDF, OOXML
and OpenDocument text into it. Adding that module to `depends` is the whole
integration; nothing here needs to change, and no cloud service is involved.

---

## 12. Time control and process performance

### Where the clock starts, and why it cannot drift

Every transition already appends one `dma.approval.line` carrying the step that
was *left* and the moment it was left. Three stored, indexed columns now turn
that log into something a database can aggregate:

| Column | Meaning |
|---|---|
| `entered_on` | when the file reached the step this entry was decided on |
| `duration_hours` | how long it had been there |
| `is_transition` | whether this entry is the one that actually closed the step |

All three are **computed off the log itself**, so they can never disagree with
it, an upgrade backfills every historical file for free, and the log stays as
immutable as it was. `is_transition` is what makes the dual confirmation honest:
that step writes an entry per department while the file stays put, and only the
last of them closed it - so *"how long does the dual confirmation take"* is
measured once per visit and not three times.

The request's `stage_entered_on` is then simply the date of the last entry that
closed something.

### The verdict

| Verdict | When |
|---|---|
| **On Track** | more than the warning period left |
| **Due Soon** | inside the warning period before the target |
| **Overdue** | past the target |
| **Escalated** | past the target plus the escalation delay |
| **Paused** | returned to the applicant - the Directorate is not holding it |
| **No Service Level** | a decided or archived file, or a step with no rule |

The verdict is computed from the wall clock on every read and never stored, so a
list stays honest as the day goes on. It is filterable (*Overdue*, *Due Soon*,
*Escalated* in the search panel) and the deadline itself - which does not move
with the clock - is stored and indexed so a queue can be sorted by it.

The **dual confirmation** is the one step with two clocks. Each department has
its own rule row; each drops off the list as soon as it signs; and the file as a
whole is exactly as late as its latest party. The badge names both.

### Reminders, escalation and the scheduled jobs

Two crons, both safe to run as often as the Directorate likes because every
record they write is keyed so a second run over unchanged data writes nothing:

* **service level review** (every 4 h) - puts exactly one *Accreditation
  deadline* to-do per responsible user, in that user's own language, and updates
  it in place; raises a level-1 escalation for the department and a level-2
  escalation to the Accreditation Manager once the escalation delay has passed;
  closes the escalations of steps the file has since left. The idempotency key is
  *(file, step, department, level, arrival)* - so a file that comes back to a
  step it already overran gets a second row rather than silently reusing the
  first. It walks the whole live caseload, reporting progress to the scheduler
  rather than capping itself at a fixed batch, because a "first N per run" cap
  would keep re-examining the head of the queue and never reach the tail.
* **expiring evidence and certificates** (daily) - refreshes the stored validity
  columns and reminds the Certifications Division about stale paperwork and the
  Accreditation Manager about accreditations running out.

Nothing here changes the legal status of anything. An accreditation whose
certificate has run out is *reported* as expired and lands on the manager's desk;
it is not silently revoked, and no renewal file is opened on the Directorate's
behalf. Time passing is not a decision.

### Urgency and lateness are different things

The priority star is the officer's judgement; the service level badge is the
clock's. A file can be one, the other, or both, and the list and the form let you
tell which. Colour never carries the message alone: every verdict ships an icon
and the written verdict beside the hue.

### Process performance

*Monitoring -> Process Performance* (Accreditation Manager and General Director)
answers four questions, all from the approval log:

* **Where does the time go** - median and p90 wait per step, with the current
  backlog and how much of it is late. One series, so it is bar rows and not a
  chart: length carries the magnitude and a hue would carry nothing.
* **Is it getting faster** - the one chart on the screen: files submitted, office
  accreditations granted and operational accreditations granted, by month. The
  same numbers are one click away as a table.
* **Who is holding what** - per department: files held, how many are late, how
  many were completed in the period and the median action time.
* **Where does it go wrong** - returns by step, files returned more than once,
  and the state of the paperwork in the building.

Percentiles are computed by PostgreSQL. Odoo's aggregate whitelist stops at
`avg`/`min`/`max`, so `dma.approval.line` extends `_read_group_select` with
`p50`, `p90` and `p95` through the documented per-model hook - the SQL is
injected into the query `_search` built, so the record rules still apply to every
aggregate, and the whole stage table is one query.

**A median of three files is not a fact.** Every distribution ships its sample
size and anything computed from fewer than five closed visits is flagged, so the
screen says *"too few files to be a figure"* instead of quietly presenting an
average as a performance figure.

The three payloads - `get_process_performance_data`, `get_sla_dashboard_data` and
`get_document_health_data` - are plain structures any screen can render, so
another dashboard never has to know how a median is computed.

---

## 13. Notes and limitations

* The public verification route (`/dma/verify/<token>`) is intentionally **not**
  implemented here: it belongs to the Directorate's public website, and the
  token is already exposed for it.
* Documents are stored as `ir.attachment` records; the module does not add a
  virus scan or a retention policy.
* Multi-company is supported through `company_id` and six global record rules,
  but the process itself assumes a single Directorate.
* Service levels are measured in **calendar** time, not working hours. Working
  time would mean depending on the `resource` addon and giving the Directorate a
  calendar to maintain; until that is asked for, a target of "3 days" means three
  days.
* The dossier archive is built in memory, like every ZIP builder in Odoo, and is
  capped by `dma_accreditation.dossier_max_bytes` (200 MB) for that reason.
* PDF rendering needs `wkhtmltopdf`; without it the workflow completes and the
  chatter says the PDF could not be produced.
