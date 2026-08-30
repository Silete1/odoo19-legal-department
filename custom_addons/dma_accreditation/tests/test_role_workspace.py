# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The department band of the workspace.

Every assertion here stands for something an officer reads off the screen and
acts on: which sections their department gets, which files land in them, what
the row says is missing, and - for the parallel step - which of the two
departments has actually signed. A silent change to any of those turns a
sentence on a government screen into a false statement, so they are pinned
here rather than only looked at.

The security assertions are the other half: the band is built from searches
run as the reader, so a role must never be handed a section that belongs to a
department it is not in, and the payload must never become a way around the
guards the buttons obey.
"""
from odoo import fields
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestRoleWorkspace(DmaAccreditationCommon):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _brief(self, user):
        return (
            self.env["dma.accreditation.request"]
            .with_user(user)
            ._role_brief()
        )

    def _sections(self, user, role=None):
        """{section key: section} for ``user``'s department."""
        brief = self._brief(user)
        out = {}
        for dept in brief["departments"]:
            if role and dept["key"] != role:
                continue
            for section in dept["sections"]:
                out[section["key"]] = section
        return out

    def _refs(self, section):
        return {row["name"] for row in section["rows"]}

    def _to_state(self, request, target):
        """Drive a fresh request up to ``target`` through the real actions."""
        self._as(request, self.user_reception).action_submit()
        if target == "submitted":
            return request
        self._as(request, self.user_reception).action_send_to_general_director()
        if target == "gd_review":
            return request
        self._as(request, self.user_gd).action_gd_accept()
        if target == "legal_review":
            return request
        self._as(request, self.user_legal).action_legal_approve()
        if target == "cert_check":
            return request
        self._as(request, self.user_cert).document_ids.write({
            "is_provided": True, "review_result": "accepted",
        })
        self._as(request, self.user_cert).action_grant_office_accreditation()
        if target == "office_granted":
            return request
        self._as(request, self.user_operations).action_start_operational_phase()
        if target == "sop_submission":
            return request
        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()
        if target == "sop_fee":
            return request
        self._confirmed_fee(request, "sop_reading", "REC/T/1")
        self._as(request, self.user_finance).action_sop_fee_registered()
        if target == "dual_confirm":
            return request
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_operations).action_dual_confirm_done()
        if target == "demo_fee":
            return request
        self._confirmed_fee(request, "operational_demo", "REC/T/2")
        self._as(request, self.user_finance).action_demo_fee_registered()
        if target == "committee":
            return request
        raise ValueError(target)

    def _attach_sop(self, request):
        attachment = self.env["ir.attachment"].create({
            "name": "sop.pdf", "type": "binary", "raw": b"%PDF-1.4\n",
            "mimetype": "application/pdf",
            "res_model": request._name, "res_id": request.id,
        })
        request.sudo().write({"sop_attachment_ids": [(6, 0, attachment.ids)]})

    def _confirmed_fee(self, request, fee_type, receipt):
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": fee_type,
            "receipt_number": receipt,
            "receipt_date": fields.Date.context_today(request),
        })
        fee.action_confirm()
        return fee

    # ==================================================================
    # Who gets which department
    # ==================================================================
    def test_01_a_role_gets_its_own_department_and_no_other(self):
        for user, role in (
            (self.user_reception, "reception"),
            (self.user_gd, "general_director"),
            (self.user_legal, "legal_director"),
            (self.user_cert, "cert_officer"),
            (self.user_operations, "operations"),
            (self.user_finance, "finance"),
            (self.user_committee, "committee"),
        ):
            with self.subTest(user=user.login):
                brief = self._brief(user)
                self.assertEqual(
                    [dept["key"] for dept in brief["departments"]], [role],
                    "a reader must be given exactly the department they are in",
                )
                self.assertTrue(brief["departments"][0]["mission"])

    def test_02_only_reception_is_offered_the_create_action(self):
        """The button that opens a file is offered where the right exists.

        ``can_create`` only decides whether the button is drawn; the server
        still refuses the create itself, which the second half asserts.
        """
        self.assertTrue(self._brief(self.user_reception)["can_create"])
        for stranger in (self.user_gd, self.user_legal, self.user_cert,
                         self.user_operations, self.user_finance,
                         self.user_committee):
            with self.subTest(user=stranger.login):
                self.assertFalse(self._brief(stranger)["can_create"])
                self.assertFalse(
                    self.env["dma.accreditation.request"]
                    .with_user(stranger)
                    .has_access("create"),
                    "hiding the button must not be the only thing stopping a create",
                )

    def test_03_the_manager_is_not_given_a_department_band(self):
        """The manager holds every role, so the band would be the whole
        directorate repeated back; the analytics below are that reader's
        screen."""
        brief = self._brief(self.user_manager)
        self.assertTrue(brief["is_manager"])
        self.assertEqual(
            [dept["key"] for dept in brief["departments"]],
            ["reception", "general_director", "legal_director", "cert_officer",
             "operations", "finance", "committee"],
            "a manager does hold every department - the client hides the band, "
            "the server does not pretend the roles are absent",
        )

    # ==================================================================
    # Reception
    # ==================================================================
    def test_04_reception_separates_drafts_returns_and_registered(self):
        draft = self._new_request()
        returned = self._new_request()
        self._to_state(returned, "gd_review")
        self._as(returned, self.user_gd).action_return_to_applicant(
            "The insurance policies are out of date."
        )
        registered = self._new_request()
        self._as(registered, self.user_reception).action_submit()

        sections = self._sections(self.user_reception, "reception")
        self.assertIn(draft.name, self._refs(sections["drafts"]))
        self.assertIn(returned.name, self._refs(sections["returned"]))
        self.assertIn(registered.name, self._refs(sections["submitted"]))
        # ... and never in each other's.
        self.assertNotIn(draft.name, self._refs(sections["returned"]))
        self.assertNotIn(returned.name, self._refs(sections["submitted"]))

    def test_05_a_returned_row_carries_the_reason_and_the_step_it_resumes_at(self):
        request = self._new_request()
        self._to_state(request, "gd_review")
        self._as(request, self.user_gd).action_return_to_applicant(
            "The organisational structure is missing."
        )
        row = next(
            row for row in self._sections(self.user_reception)["returned"]["rows"]
            if row["name"] == request.name
        )
        self.assertIn("organisational structure", row["note"])
        self.assertTrue(
            any("Submitted" in chip["label"] for chip in row["chips"]),
            "the reception desk has to know which step the file goes back to",
        )

    def test_06_a_draft_without_a_scope_says_so_rather_than_ready(self):
        blocked = self._new_request(scope_ids=[(5, 0, 0)])
        ready = self._new_request()
        rows = {
            row["name"]: row
            for row in self._sections(self.user_reception)["drafts"]["rows"]
        }
        self.assertIn("scope", rows[blocked.name]["note"].lower())
        self.assertEqual(rows[ready.name]["note"], "Ready to submit.")

    # ==================================================================
    # Legal - the two jobs are two sections
    # ==================================================================
    def test_07_legal_review_and_legal_refinement_are_separate_sections(self):
        sections = self._sections(self.user_legal, "legal_director")
        self.assertEqual(
            sorted(sections), ["legal_refine", "legal_review"],
            "the two legal steps ask for different work and must not share a queue",
        )
        self.assertNotEqual(
            sections["legal_review"]["hint"], sections["legal_refine"]["hint"],
        )

    def test_08_a_file_lands_in_exactly_one_of_the_two_legal_sections(self):
        under_review = self._new_request()
        self._to_state(under_review, "legal_review")

        sections = self._sections(self.user_legal)
        self.assertIn(under_review.name, self._refs(sections["legal_review"]))
        self.assertNotIn(under_review.name, self._refs(sections["legal_refine"]))

    def test_09_refinement_says_whether_the_text_is_drafted(self):
        request = self._new_request()
        self._to_state(request, "committee")
        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()
        self.assertEqual(request.state, "legal_refine")

        row = next(
            row for row in self._sections(self.user_legal)["legal_refine"]["rows"]
            if row["name"] == request.name
        )
        self.assertTrue(any(chip["tone"] == "attention" for chip in row["chips"]))

        request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
        row = next(
            row for row in self._sections(self.user_legal)["legal_refine"]["rows"]
            if row["name"] == request.name
        )
        self.assertTrue(any(chip["tone"] == "done" for chip in row["chips"]))

    # ==================================================================
    # Certifications - the checklist is the whole job
    # ==================================================================
    def test_10_the_checklist_row_counts_what_is_missing_and_what_is_unreviewed(self):
        request = self._new_request()
        self._to_state(request, "cert_check")
        required = request.document_ids.filtered("is_required")
        self.assertGreaterEqual(len(required), 4)

        # two accepted, one provided but not accepted, the rest untouched.
        required[0].with_user(self.user_cert).write({
            "is_provided": True, "review_result": "accepted",
        })
        required[1].with_user(self.user_cert).write({
            "is_provided": True, "review_result": "accepted",
        })
        required[2].with_user(self.user_cert).write({"is_provided": True})

        row = next(
            row for row in self._sections(self.user_cert)["cert_check"]["rows"]
            if row["name"] == request.name
        )
        self.assertEqual(row["meter"]["done"], 2)
        self.assertEqual(row["meter"]["total"], len(required))
        self.assertEqual(row["meter"]["label"], "2 / %s" % len(required))
        labels = " ".join(chip["label"] for chip in row["chips"])
        self.assertIn("%s not provided" % (len(required) - 3), labels)
        self.assertIn("1 to review", labels)

    def test_11_a_complete_checklist_says_the_gate_is_open(self):
        request = self._new_request()
        self._to_state(request, "cert_check")
        request.document_ids.with_user(self.user_cert).write({
            "is_provided": True, "review_result": "accepted",
        })
        row = next(
            row for row in self._sections(self.user_cert)["cert_check"]["rows"]
            if row["name"] == request.name
        )
        self.assertEqual(row["meter"]["percent"], 100)
        self.assertIn("can be granted", row["note"])
        # ... and the server agrees, which is the claim that matters.
        self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertEqual(request.state, "office_granted")

    # ==================================================================
    # The parallel step, from both sides
    # ==================================================================
    def test_12_dual_confirmation_shows_both_signatures_from_either_side(self):
        request = self._new_request()
        self._to_state(request, "dual_confirm")
        self._as(request, self.user_finance).action_finance_confirm()

        finance_row = next(
            row for row in self._sections(self.user_finance)["dual_confirm"]["rows"]
            if row["name"] == request.name
        )
        self.assertTrue(finance_row["dual"]["mine_done"])
        self.assertFalse(finance_row["dual"]["other_done"])
        self.assertIn("waiting for the other", finance_row["note"])

        operations_row = next(
            row for row in self._sections(self.user_operations)["dual_confirm"]["rows"]
            if row["name"] == request.name
        )
        self.assertFalse(operations_row["dual"]["mine_done"])
        self.assertTrue(operations_row["dual"]["other_done"])
        self.assertEqual(
            operations_row["dual"]["other_by"], self.user_finance.display_name,
            "the side that has signed is named, so the other knows whom to ask",
        )
        self.assertIn("Your confirmation is outstanding", operations_row["note"])

    def test_13_both_signed_is_not_reported_as_still_waiting(self):
        request = self._new_request()
        self._to_state(request, "dual_confirm")
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()

        row = next(
            row for row in self._sections(self.user_operations)["dual_confirm"]["rows"]
            if row["name"] == request.name
        )
        self.assertTrue(row["dual"]["complete"])
        self.assertIn("Both departments have signed", row["note"])

    def test_14_the_dual_row_matches_the_server_flags_exactly(self):
        """The panel may never claim a signature the record does not carry."""
        request = self._new_request()
        self._to_state(request, "dual_confirm")
        for signer in (None, "finance", "operations"):
            if signer == "finance":
                self._as(request, self.user_finance).action_finance_confirm()
            if signer == "operations":
                self._as(request, self.user_operations).action_operations_confirm()
            row = next(
                row for row in self._sections(self.user_finance)["dual_confirm"]["rows"]
                if row["name"] == request.name
            )
            with self.subTest(signed=signer):
                self.assertEqual(
                    row["dual"]["mine_done"], request.finance_confirmed_sop_fee,
                )
                self.assertEqual(
                    row["dual"]["other_done"], request.operations_confirmed_sop,
                )

    # ==================================================================
    # Finance - the money, not the file
    # ==================================================================
    def test_15_finance_is_given_the_fee_lines_not_only_the_requests(self):
        request = self._new_request()
        self._to_state(request, "sop_fee")
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id, "fee_type": "sop_reading",
        })

        section = self._sections(self.user_finance)["fees_to_confirm"]
        self.assertEqual(section["kind"], "fees")
        row = next(row for row in section["rows"] if row["id"] == fee.id)
        self.assertEqual(row["name"], request.name)
        self.assertEqual(row["partner"], request.partner_id.display_name)
        self.assertFalse(row["ready"])
        self.assertIn("receipt number", row["note"])
        self.assertIn("receipt date", row["note"])

    def test_16_a_fee_with_its_receipt_is_reported_ready(self):
        request = self._new_request()
        self._to_state(request, "sop_fee")
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": "sop_reading",
            "receipt_number": "REC/2026/9001",
            "receipt_date": fields.Date.context_today(request),
            "amount": 250.0,
        })
        row = next(
            row for row in self._sections(self.user_finance)["fees_to_confirm"]["rows"]
            if row["id"] == fee.id
        )
        self.assertTrue(row["ready"])
        self.assertIn("Confirm the payment", row["note"])
        # ... and the server accepts the click the row is inviting.
        fee.action_confirm()
        self.assertEqual(fee.state, "confirmed")

    def test_17_a_confirmed_fee_leaves_the_to_confirm_section(self):
        request = self._new_request()
        self._to_state(request, "sop_fee")
        fee = self._confirmed_fee(request, "sop_reading", "REC/2026/9002")
        ids = {
            row["id"]
            for row in self._sections(self.user_finance)["fees_to_confirm"]["rows"]
        }
        self.assertNotIn(fee.id, ids)

    # ==================================================================
    # Operations and Committee
    # ==================================================================
    def test_18_sop_collection_names_the_copy_that_is_missing(self):
        request = self._new_request()
        self._to_state(request, "sop_submission")
        row = next(
            row for row in self._sections(self.user_operations)["sop_intake"]["rows"]
            if row["name"] == request.name
        )
        self.assertIn("electronic copy", row["note"])
        self.assertIn("paper copy", row["note"])

        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        row = next(
            row for row in self._sections(self.user_operations)["sop_intake"]["rows"]
            if row["name"] == request.name
        )
        self.assertIn("Both copies are in", row["note"])

    def test_19_the_committee_row_lists_what_is_still_to_record(self):
        request = self._new_request()
        self._to_state(request, "committee")
        row = next(
            row for row in self._sections(self.user_committee)["committee"]["rows"]
            if row["name"] == request.name
        )
        for expected in ("the decision", "the session date", "the decision text"):
            self.assertIn(expected, row["note"])

        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved.</p>",
        })
        row = next(
            row for row in self._sections(self.user_committee)["committee"]["rows"]
            if row["name"] == request.name
        )
        self.assertIn("Recorded in full", row["note"])

    # ==================================================================
    # Ordering, links and the payload as a whole
    # ==================================================================
    def test_20_a_section_is_worked_oldest_first_with_urgent_ahead(self):
        """Urgent first, then whatever has waited longest.

        ``waiting_since`` is stored and computed from the approval log, so the
        three drafts here share a timestamp and the tie is broken by id - which
        is still oldest-first. The urgent flag is what has to jump the queue.
        """
        first = self._new_request()
        second = self._new_request()
        urgent = self._new_request()
        urgent.priority = "1"

        refs = [
            row["name"]
            for row in self._sections(self.user_reception)["drafts"]["rows"]
        ]
        self.assertEqual(refs[0], urgent.name, "an urgent file leads its section")
        self.assertLess(
            refs.index(first.name), refs.index(second.name),
            "within a priority the older file is offered first",
        )

    def test_20b_the_oldest_wait_leads_when_no_file_is_urgent(self):
        stale = self._new_request()
        fresh = self._new_request()
        self.env.cr.execute(
            "UPDATE dma_accreditation_request SET waiting_since = %s WHERE id = %s",
            (fields.Datetime.subtract(fields.Datetime.now(), days=30), stale.id),
        )
        stale.invalidate_recordset(["waiting_since"])

        refs = [
            row["name"]
            for row in self._sections(self.user_reception)["drafts"]["rows"]
        ]
        self.assertLess(refs.index(stale.name), refs.index(fresh.name))

    def test_21_every_row_carries_the_id_the_link_opens(self):
        request = self._new_request()
        self._to_state(request, "gd_review")
        row = next(
            row for row in self._sections(self.user_gd)["gd_review"]["rows"]
            if row["name"] == request.name
        )
        self.assertEqual(row["id"], request.id)

    def test_22_a_section_count_is_the_whole_queue_not_the_page(self):
        for _ in range(9):
            self._new_request()
        section = self._sections(self.user_reception)["drafts"]
        self.assertGreaterEqual(section["count"], 9)
        self.assertLessEqual(
            len(section["rows"]), 6,
            "a desk panel shows a working handful and links to the rest",
        )
        self.assertLess(len(section["rows"]), section["count"])

    def test_23_the_brief_reaches_the_workspace_payload(self):
        data = (
            self.env["dma.accreditation.request"]
            .with_user(self.user_finance)
            .get_dashboard_data()
        )
        self.assertIn("role_brief", data)
        self.assertEqual(
            [dept["key"] for dept in data["role_brief"]["departments"]], ["finance"],
        )
        # The panels the other stream owns are untouched by the addition.
        for key in ("my_files", "hero", "pipeline", "ageing", "cycle",
                    "throughput", "returns", "expiring", "totals"):
            self.assertIn(key, data)

    def test_24_recent_work_is_this_reader_s_own_and_nobody_else_s(self):
        request = self._new_request()
        self._to_state(request, "legal_review")
        recent = self._brief(self.user_gd)["recent"]
        self.assertTrue(recent)
        self.assertTrue(
            all(entry["name"] for entry in recent),
        )
        lines = self.env["dma.approval.line"].search([
            ("id", "in", [
                line.id for line in request.approval_line_ids
            ]),
            ("user_id", "=", self.user_gd.id),
        ])
        self.assertTrue(lines, "the General Director's acceptance was logged")
        # Reception never signed the gd_review step, so it must not appear
        # under Reception's own "what you last put through".
        steps = {entry["step"] for entry in self._brief(self.user_reception)["recent"]}
        self.assertNotIn(
            "General Director Initial Acceptance", steps,
        )
