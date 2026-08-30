# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""What each department is actually supposed to do, and on which files.

The workspace already answers "how much is on my desk". This file answers the
questions an officer asks *next*, which the shared desk cannot: what is this
department for, what does this particular step expect of me, which of my files
are blocked and on whom, and what did I just finish.

Two things are deliberate.

**One brief, seven configurations - not seven screens.** The departments differ
in which slice of one process they own, not in kind, and the Accreditation
Manager holds every role at once; seven separate client actions could not
represent that reader at all. So there is a single payload shape - a list of
sections, each a title, a hint, an empty state and a list of rows - and
:meth:`_brief_builders` says which builder runs for which role. Adding a
department is a dictionary entry, not a component.

**The rows are built server side, in the reader's language.** A row carries the
sentence an officer needs ("waiting for Finance since 3 March", "2 of 10
prerequisites still missing") already composed, because composing it in the
browser would mean re-deriving in JavaScript the state machine that lives in
Python - and getting a different answer the day one of them changes.

Nothing here decides anything. Every guard stays where it was: the sections are
built from the same ``ROLE_QUEUE_STATES`` the menus and ``is_my_turn`` use, the
searches run as the reader so the record rules apply, and no row offers an
action the server would refuse.
"""
from odoo import api, fields, models
from odoo.tools import is_html_empty

from .dma_constants import (
    ROLE_GROUP,
    ROLE_SELECTION,
    role_label,
    state_label,
)

#: How many rows a section shows before it defers to its "open all" link. A
#: desk panel is a to-do list, not a report: past about half a dozen entries an
#: officer stops reading rows and starts using the queue screen, which sorts
#: and filters properly.
SECTION_LIMIT = 6


class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    # ==================================================================
    # Row builders - one shape, whatever the section
    # ==================================================================
    def _brief_row(self, note=False, chips=None, meter=None):
        """One file, as a desk row.

        ``note`` is the sentence that says why the row is here; ``chips`` are
        short facts worth scanning down the column; ``meter`` is a completion
        ratio where the step has one.
        """
        self.ensure_one()
        waiting = self._brief_waiting_days()
        return {
            "id": self.id,
            "name": self.name,
            "partner": self.partner_id.display_name,
            "state": self.state,
            "state_label": state_label(self.env, self.state),
            "urgent": self.priority == "1",
            "waiting_days": waiting,
            "waiting_label": (
                self.env._("today") if waiting <= 0
                else self.env._("%s day(s)", waiting)
            ),
            "sla": self._brief_sla(),
            "note": note or "",
            "chips": chips or [],
            "meter": meter or False,
        }

    def _brief_sla(self):
        """The agreed verdict on this file's wait, where one applies.

        The service level is defined once, in ``dma.sla.rule``, and rendered
        once, by the badge on the form. A desk row asks the same question -
        "is this late" - so it reuses that answer rather than re-deriving a
        second opinion from a day count: two numbers on two screens that
        disagree is worse than one number on one.
        """
        self.ensure_one()
        payload = self.sla_payload or {}
        state = payload.get("state")
        if not state or state in ("not_applicable",):
            return False
        return {
            "state": state,
            "label": payload.get("state_label") or "",
            "icon": payload.get("icon") or "",
            "age": payload.get("age") or "",
            # A tone the band already knows how to paint, so the desk and the
            # form agree without sharing a stylesheet.
            "tone": {
                "on_track": "neutral",
                "warning": "attention",
                "overdue": "critical",
                "escalated": "critical",
                "paused": "neutral",
            }.get(state, "neutral"),
        }

    def _brief_waiting_days(self):
        """Days the file has been standing at its current step."""
        self.ensure_one()
        since = self.waiting_since or self.create_date
        if not since:
            return 0
        return max(0, (fields.Datetime.now() - since).days)

    def _brief_search(self, domain, limit=SECTION_LIMIT):
        """Oldest first: a desk panel is worked from the top down.

        Urgent files still come first, because the priority flag exists to say
        exactly that, but within a priority the file that has waited longest is
        the one that should be opened next.
        """
        return self.search(domain, order="priority desc, waiting_since asc, id asc", limit=limit)

    # ==================================================================
    # Sections - one builder per thing a department is asked to do
    # ==================================================================
    def _brief_section(self, key, title, hint, empty, domain, rows, kind="files",
                       action=False, count=None):
        """One panel of a department's desk.

        ``count`` is the size of the whole queue, not of the page: the rows are
        capped at :data:`SECTION_LIMIT` and the footer offers the rest, so a
        count taken from ``len(rows)`` would tell an officer the backlog is six
        when it is sixty. It defaults to counting ``domain`` on the request
        model; a section over another model passes its own.
        """
        return {
            "key": key,
            "kind": kind,
            "title": title,
            "hint": hint,
            "empty": empty,
            "count": self.search_count(domain) if count is None else count,
            "domain": domain,
            "rows": rows,
            "action": action,
        }

    # -- Reception ------------------------------------------------------
    def _brief_reception(self):
        sections = []

        domain = [("state", "=", "draft")]
        rows = []
        for request in self._brief_search(domain):
            blockers = request._progress_blockers()
            rows.append(request._brief_row(
                note=blockers[0] if blockers else self.env._("Ready to submit."),
                chips=[{
                    "label": self.env._("%s scope(s)", len(request.scope_ids))
                    if request.scope_ids else self.env._("No scope yet"),
                    "tone": "neutral" if request.scope_ids else "attention",
                }],
            ))
        sections.append(self._brief_section(
            "drafts",
            self.env._("Files being opened"),
            self.env._("Intake started but not yet registered. Complete the applicant and the requested scopes, then submit."),
            self.env._("No file is half-open on the desk."),
            domain, rows,
        ))

        domain = [("state", "=", "returned")]
        rows = []
        for request in self._brief_search(domain):
            rows.append(request._brief_row(
                note=(request.return_reason or "").strip().replace("\n", " ")[:160],
                chips=[{
                    "label": self.env._(
                        "Resumes at %s", state_label(self.env, request.return_to_state),
                    ) if request.return_to_state else self.env._("Resumes at intake"),
                    "tone": "attention",
                }],
            ))
        sections.append(self._brief_section(
            "returned",
            self.env._("Returned for completion"),
            self.env._("A department sent these back. Obtain what the reason asks for from the applicant, then resume the file."),
            self.env._("Nothing has been returned to the reception desk."),
            domain, rows,
        ))

        domain = [("state", "=", "submitted")]
        rows = []
        for request in self._brief_search(domain):
            rows.append(request._brief_row(
                note=self.env._("Registered. Forward it to the General Director."),
            ))
        sections.append(self._brief_section(
            "submitted",
            self.env._("Registered, not yet forwarded"),
            self.env._("These carry a reference and a submission date but are still on this desk."),
            self.env._("Every registered file has been forwarded."),
            domain, rows,
        ))
        return sections

    # -- General Director ----------------------------------------------
    def _brief_general_director(self):
        domain = [("state", "=", "gd_review")]
        rows = []
        for request in self._brief_search(domain):
            chips = [{"label": dict(
                self._fields["request_type"]._description_selection(self.env)
            ).get(request.request_type, ""), "tone": "neutral"}]
            if request.scope_ids:
                chips.append({
                    "label": ", ".join(request.scope_ids.mapped("name")[:3]),
                    "tone": "neutral",
                })
            rows.append(request._brief_row(
                note=self.env._("Accept to send it to the Legal Department, or return it with a reason."),
                chips=chips,
            ))
        return [self._brief_section(
            "gd_review",
            self.env._("Awaiting your initial acceptance"),
            self.env._("The first decision on the application: whether the Directorate takes the file forward at all."),
            self.env._("No application is waiting for the initial acceptance."),
            domain, rows,
        )]

    # -- Legal Department ----------------------------------------------
    def _brief_legal_director(self):
        """Two jobs, two sections.

        The Legal Department is asked for something different at each of its
        two appearances - an opinion on the application, then a drafting pass
        over somebody else's decision - and a single "Legal queue" mixing them
        is the reason an officer has to open a file to find out what it wants.
        """
        sections = []

        domain = [("state", "=", "legal_review")]
        rows = []
        for request in self._brief_search(domain):
            rows.append(request._brief_row(
                note=self.env._("Approve to send it to the Certifications Division, or return it with a reason."),
            ))
        sections.append(self._brief_section(
            "legal_review",
            self.env._("Initial legal review"),
            self.env._("Review the application itself, before the prerequisites are verified. The outcome is an approval, a return or a rejection."),
            self.env._("No application is waiting for the initial legal review."),
            domain, rows,
        ))

        domain = [("state", "=", "legal_refine")]
        rows = []
        for request in self._brief_search(domain):
            drafted = not is_html_empty(request.refined_decision_text)
            rows.append(request._brief_row(
                note=(
                    self.env._("Refined text drafted. Issue the operational accreditation.")
                    if drafted
                    else self.env._("Refine the committee decision text before the certificate can be issued.")
                ),
                chips=[{
                    "label": (
                        self.env._("Text drafted") if drafted
                        else self.env._("Text outstanding")
                    ),
                    "tone": "done" if drafted else "attention",
                }],
            ))
        sections.append(self._brief_section(
            "legal_refine",
            self.env._("Final legal refinement"),
            self.env._("The Accreditation Committee has decided. Put its decision into the legal wording that the certificate is issued on."),
            self.env._("No committee decision is waiting for refinement."),
            domain, rows,
        ))
        return sections

    # -- Certifications Division ---------------------------------------
    def _brief_cert_officer(self):
        domain = [("state", "=", "cert_check")]
        rows = []
        for request in self._brief_search(domain):
            required = request.document_ids.filtered("is_required")
            accepted = required.filtered(
                lambda line: line.is_provided and line.review_result == "accepted"
            )
            not_provided = required.filtered(lambda line: not line.is_provided)
            provided_unreviewed = required.filtered(
                lambda line: line.is_provided and line.review_result != "accepted"
            )
            chips = []
            if not_provided:
                chips.append({
                    "label": self.env._("%s not provided", len(not_provided)),
                    "tone": "critical",
                })
            if provided_unreviewed:
                chips.append({
                    "label": self.env._("%s to review", len(provided_unreviewed)),
                    "tone": "attention",
                })
            if not chips:
                chips.append({
                    "label": self.env._("Checklist complete"), "tone": "done",
                })
            rows.append(request._brief_row(
                note=(
                    self.env._("Every prerequisite is accepted. The office accreditation can be granted.")
                    if request.checklist_complete
                    else self.env._("The office accreditation stays blocked until every required prerequisite is provided and accepted.")
                ),
                chips=chips,
                meter={
                    "done": len(accepted),
                    "total": len(required),
                    "percent": round(100.0 * len(accepted) / len(required)) if required else 0,
                    # One atomic chip: keeping the two numbers out of the
                    # surrounding sentence is what makes it readable right to
                    # left.
                    "label": f"{len(accepted)} / {len(required)}",
                },
            ))
        return [self._brief_section(
            "cert_check",
            self.env._("Prerequisites to verify"),
            self.env._("Check each required document (الأوليات) and accept it, or record it as missing or invalid. Office accreditation is granted only once every required item is accepted."),
            self.env._("No file is waiting for the Certifications Division."),
            domain, rows,
        )]

    # -- Operations -----------------------------------------------------
    def _brief_operations(self):
        sections = []

        domain = [("state", "in", ("office_granted", "sop_submission"))]
        rows = []
        for request in self._brief_search(domain):
            if request.state == "office_granted":
                note = self.env._("Open the operational phase to start collecting the SOP.")
                chips = []
            else:
                missing = []
                if not request.sop_electronic_received:
                    missing.append(self.env._("electronic copy"))
                if not request.sop_paper_received:
                    missing.append(self.env._("paper copy"))
                note = (
                    self.env._("Both copies are in. Confirm the SOP submission.")
                    if not missing
                    else self.env._("Still outstanding: %s.", ", ".join(missing))
                )
                chips = [
                    {
                        "label": self.env._("Paper SOP"),
                        "tone": "done" if request.sop_paper_received else "attention",
                    },
                    {
                        "label": self.env._("Electronic SOP"),
                        "tone": "done" if request.sop_electronic_received else "attention",
                    },
                ]
            rows.append(request._brief_row(note=note, chips=chips))
        sections.append(self._brief_section(
            "sop_intake",
            self.env._("SOP collection"),
            self.env._("Open the operational phase, then record the paper and the electronic Standing Operating Procedures as they arrive."),
            self.env._("No file is waiting for the SOP to be collected."),
            domain, rows,
        ))

        sections.append(self._brief_dual_section("operations"))
        return sections

    # -- Finance --------------------------------------------------------
    def _brief_finance(self):
        sections = []

        fee_domain = [("state", "=", "draft")]
        Fee = self.env["dma.fee.payment"]
        fees = Fee.search(
            fee_domain, order="receipt_date asc, id asc", limit=SECTION_LIMIT,
        )
        fee_labels = dict(
            self.env["dma.fee.payment"]._fields["fee_type"]._description_selection(self.env)
        )
        rows = []
        for fee in fees:
            missing = []
            if not fee.receipt_number:
                missing.append(self.env._("receipt number"))
            if not fee.receipt_date:
                missing.append(self.env._("receipt date"))
            if fee.currency_id.is_zero(fee.amount):
                missing.append(self.env._("amount"))
            rows.append({
                "id": fee.id,
                "model": "dma.fee.payment",
                "request_id": fee.request_id.id,
                "name": fee.request_id.name,
                "partner": fee.partner_id.display_name,
                "fee_type": fee_labels.get(fee.fee_type, ""),
                "amount": fee.amount,
                "currency": fee.currency_id.symbol or fee.currency_id.name,
                "receipt_number": fee.receipt_number or "",
                "receipt_date": fee.receipt_date and str(fee.receipt_date) or "",
                "attachments": fee.attachment_count,
                "state_label": state_label(self.env, fee.request_state)
                if fee.request_state else "",
                "note": (
                    self.env._("Missing before it can be confirmed: %s.", ", ".join(missing))
                    if missing
                    else self.env._("Receipt details complete. Confirm the payment.")
                ),
                "ready": not missing,
            })
        sections.append(self._brief_section(
            "fees_to_confirm",
            self.env._("Fees awaiting confirmation"),
            self.env._("Check each payment against its receipt, then confirm it. A confirmed fee is evidence and cannot be deleted."),
            self.env._("No fee is waiting to be confirmed."),
            fee_domain, rows, kind="fees", count=Fee.search_count(fee_domain),
        ))

        domain = [("state", "in", ("sop_fee", "demo_fee"))]
        rows = []
        for request in self._brief_search(domain):
            if request.state == "sop_fee":
                note = (
                    self.env._("The SOP reading fee is confirmed. Move the file to the dual confirmation.")
                    if request.sop_fee_paid
                    else self.env._("Register and confirm the SOP reading fee on the file.")
                )
            else:
                note = (
                    self.env._("The demonstration fee is confirmed. Send the file to the Accreditation Committee.")
                    if request.demo_fee_paid
                    else self.env._("Register and confirm the operational demonstration fee.")
                )
            rows.append(request._brief_row(note=note))
        sections.append(self._brief_section(
            "fee_steps",
            self.env._("Steps waiting on Finance"),
            self.env._("Files the procedure cannot move past until Finance has settled the fee of the step."),
            self.env._("No step is held up by a fee."),
            domain, rows,
        ))

        sections.append(self._brief_dual_section("finance"))
        return sections

    # -- Accreditation Committee ---------------------------------------
    def _brief_committee(self):
        domain = [("state", "=", "committee")]
        rows = []
        for request in self._brief_search(domain):
            outstanding = []
            if not request.committee_decision:
                outstanding.append(self.env._("the decision"))
            if not request.committee_date:
                outstanding.append(self.env._("the session date"))
            if is_html_empty(request.decision_text):
                outstanding.append(self.env._("the decision text"))
            chips = [{
                "label": (
                    self.env._("%s minute(s) attached", len(request.committee_minutes_ids))
                    if request.committee_minutes_ids
                    else self.env._("No minutes attached")
                ),
                "tone": "done" if request.committee_minutes_ids else "attention",
            }]
            rows.append(request._brief_row(
                note=(
                    self.env._("Recorded in full. Confirming it sends the file to the Legal Department for refinement.")
                    if not outstanding
                    else self.env._("Still to record: %s.", ", ".join(outstanding))
                ),
                chips=chips,
            ))
        return [self._brief_section(
            "committee",
            self.env._("Files for decision"),
            self.env._("Record the decision, the date of the session and the reasoned decision text, and attach the signed minutes. An approval goes on to the Legal Department for refinement; a rejection closes the file."),
            self.env._("No file is before the Accreditation Committee."),
            domain, rows,
        )]

    # -- The parallel step, from whichever side is reading ---------------
    def _brief_dual_section(self, side):
        """The dual confirmation as two independent signatures, never as a status.

        Both halves are always shown, whichever department is reading: the
        question an officer has at this step is not "what state is this in" but
        "have I signed, and is the other department still holding it".
        """
        other = "operations" if side == "finance" else "finance"
        mine_field = (
            "finance_confirmed_sop_fee" if side == "finance"
            else "operations_confirmed_sop"
        )
        other_field = (
            "operations_confirmed_sop" if side == "finance"
            else "finance_confirmed_sop_fee"
        )
        other_by = (
            "operations_confirmed_by" if side == "finance"
            else "finance_confirmed_by"
        )
        other_on = (
            "operations_confirmed_on" if side == "finance"
            else "finance_confirmed_on"
        )

        domain = [("state", "=", "dual_confirm")]
        rows = []
        for request in self._brief_search(domain):
            mine_done = bool(request[mine_field])
            theirs_done = bool(request[other_field])
            if not mine_done:
                note = self.env._("Your confirmation is outstanding.")
            elif not theirs_done:
                note = self.env._("You have signed. The file is waiting for the other department.")
            else:
                note = self.env._("Both departments have signed. The file can move to the demonstration fee.")
            signer = request[other_by]
            row = request._brief_row(note=note)
            row["dual"] = {
                "mine_label": role_label(self.env, side),
                "mine_done": mine_done,
                "other_label": role_label(self.env, other),
                "other_done": theirs_done,
                "other_by": signer.display_name if signer else "",
                "other_on": (
                    str(request[other_on])[:16] if request[other_on] else ""
                ),
                "complete": mine_done and theirs_done,
            }
            rows.append(row)
        return self._brief_section(
            "dual_confirm",
            self.env._("Dual confirmation"),
            self.env._("Finance and Operations sign this step independently. Neither waits for the other, and the file only moves on once both have."),
            self.env._("No file is at the dual confirmation."),
            domain, rows, kind="dual",
        )

    # ==================================================================
    # Assembly
    # ==================================================================
    #: role -> the builder that produces its sections.
    def _brief_builders(self):
        return {
            "reception": self._brief_reception,
            "general_director": self._brief_general_director,
            "legal_director": self._brief_legal_director,
            "cert_officer": self._brief_cert_officer,
            "operations": self._brief_operations,
            "finance": self._brief_finance,
            "committee": self._brief_committee,
        }

    def _brief_mission(self, role):
        """One sentence: what this department is for."""
        return {
            "reception": self.env._("Open accreditation files, complete their intake and forward them to the General Director."),
            "general_director": self.env._("Decide whether the Directorate accepts an application, and issue the operational accreditation once the Legal Department has refined the decision."),
            "legal_director": self.env._("Give the legal opinion on an application, and later put the committee decision into the wording the certificate is issued on."),
            "cert_officer": self.env._("Verify the prerequisites of every application and grant the office accreditation once they are all in order."),
            "operations": self.env._("Collect the Standing Operating Procedures and confirm their receipt for appraisal."),
            "finance": self.env._("Confirm the accreditation fees against their receipts and sign the Finance half of the dual confirmation."),
            "committee": self.env._("Sit on the file, record the accreditation decision and the minutes of the session."),
        }.get(role, "")

    def _brief_recent(self, limit=5):
        """What this reader last put through, newest first.

        Short and deliberately unclickable-looking beyond the file link: it is
        here to close the loop on a morning's work, not to invite a second pass
        over decisions the log has already sealed.
        """
        lines = self.env["dma.approval.line"].search(
            [("user_id", "=", self.env.uid)], order="date desc, id desc", limit=limit,
        )
        decisions = dict(
            self.env["dma.approval.line"]._fields["decision"]._description_selection(self.env)
        )
        return [{
            "id": line.request_id.id,
            "name": line.request_id.name,
            "partner": line.request_id.partner_id.display_name,
            "step": state_label(self.env, line.step),
            "decision": decisions.get(line.decision, ""),
            "tone": {
                "approved": "done", "confirmed": "done",
                "returned": "attention", "rejected": "critical",
            }.get(line.decision, "neutral"),
            "date": str(line.date)[:16] if line.date else "",
        } for line in lines]

    @api.model
    def _role_brief(self):
        """The department half of the workspace, for whoever is reading."""
        user = self.env.user
        builders = self._brief_builders()
        held = [
            key for key, _label in ROLE_SELECTION
            if key != "manager" and user.has_group(ROLE_GROUP[key])
        ]
        departments = []
        for key in held:
            builder = builders.get(key)
            if not builder:
                continue
            sections = [section for section in builder() if section]
            departments.append({
                "key": key,
                "label": role_label(self.env, key),
                "mission": self._brief_mission(key),
                "sections": sections,
                "outstanding": sum(
                    section["count"] for section in sections
                ),
            })
        return {
            "departments": departments,
            "recent": self._brief_recent(),
            # The Accreditation Manager holds every role, so the department
            # band would repeat the whole directorate back at them. The
            # analytics below are that reader's screen; this band is not.
            "is_manager": user.has_group("dma_accreditation.group_dma_manager"),
            "can_create": user.has_group("dma_accreditation.group_dma_reception"),
        }

    # ==================================================================
    # Hooked onto the one payload the workspace already fetches
    # ==================================================================
    @api.model
    def get_dashboard_data(self, window_days=None):
        """Add the department brief to the workspace payload.

        Appended here rather than merged into the original method so the two
        halves of the screen stay separately readable and separately testable:
        the desk counts the caseload, this says what to do with it.
        """
        data = super().get_dashboard_data(window_days=window_days)
        data["role_brief"] = self._role_brief()
        return data
