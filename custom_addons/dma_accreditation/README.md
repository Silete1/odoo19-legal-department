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
* Version: `19.0.1.0.0`
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

The two fee amounts are proposed by default on a new fee line; an officer can
still type a different amount. The validity drives the **expiry date** of the
operational accreditation certificate (`issue_date + N months − 1 day`).

The keys are plain system parameters, so they can also be set from a data file
or from `Settings → Technical → System Parameters`.

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

Two server methods feed the interface and keep its logic testable in Python:
`_compute_progress_payload` (the progress rail and its blockers) and
`get_dashboard_data` (every number on the dashboard, counted through the record
rules).

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

78 Python tests in five files:

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

Plus 7 **hoot** tests in `static/tests/accreditation_progress.test.js` covering
the progress component itself: the step states, the pending department, the
blocker list, the closed-file case, the rejected case and the RTL flip.

The report tests render **HTML**, not PDF, so the suite is green on a CI machine
without `wkhtmltopdf`.

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

## 11. Notes and limitations

* The public verification route (`/dma/verify/<token>`) is intentionally **not**
  implemented here: it belongs to the Directorate's public website, and the
  token is already exposed for it.
* Documents are stored as `ir.attachment` records; the module does not add a
  virus scan or a retention policy.
* Multi-company is supported through `company_id` and three global record rules,
  but the process itself assumes a single Directorate.
* PDF rendering needs `wkhtmltopdf`; without it the workflow completes and the
  chatter says the PDF could not be produced.
