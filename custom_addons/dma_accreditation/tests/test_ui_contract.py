# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The contract the interface relies on.

Every one of these fields exists because a view asks it a question - "may I
offer Return here", "will the blue button work", "how long has this been on my
desk". They are as much part of the product as the workflow itself, and a
silent change to any of them turns a button into a trap, so they are pinned
here rather than only exercised through the screens.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationUiContract(DmaAccreditationCommon):

    # ------------------------------------------------------------------
    # can_review - the header offers Return/Reject exactly when the server
    # would accept the click
    # ------------------------------------------------------------------
    def test_01_can_review_matches_the_server_guard(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self.assertEqual(request.state, "legal_review")

        self.assertTrue(self._as(request, self.user_legal).can_review)
        self.assertTrue(self._as(request, self.user_manager).can_review)
        for stranger in (self.user_finance, self.user_operations, self.user_cert):
            with self.subTest(user=stranger.login):
                self.assertFalse(self._as(request, stranger).can_review)
                # ... and the server agrees.
                with self.assertRaises(AccessError):
                    self._as(request, stranger).action_return_to_applicant("no")

    def test_02_can_review_is_not_is_my_turn(self):
        """The General Director carries cert_check in its queue but may not decide on it.

        Reusing ``is_my_turn`` for the Return button would offer the General
        Director an action that raises: ROLE_QUEUE_STATES gives them the
        Certifications step so the file shows up on their desk, while
        ``_reviewer_roles_for_state`` names only the Certifications Division.
        """
        request = self._new_request()
        self._drive_to_cert_check(request)
        gd = self._as(request, self.user_gd)
        self.assertTrue(gd.is_my_turn, "the file is on the General Director's board")
        self.assertFalse(gd.can_review, "but the decision is not theirs to take")
        with self.assertRaises(AccessError):
            gd.action_return_to_applicant("not mine to return")

    def test_03_a_closed_file_offers_no_decision(self):
        request = self._new_request()
        self.assertFalse(self._as(request, self.user_reception).can_review,
                         "a draft has not been submitted to anybody yet")
        closed = self._new_request()
        self._drive_to_cert_check(closed)
        self._as(closed, self.user_cert).action_reject("no")
        self.assertFalse(self._as(closed, self.user_manager).can_review)

    # ------------------------------------------------------------------
    # ready_to_advance - the blue button never lies
    # ------------------------------------------------------------------
    def test_04_ready_to_advance_tracks_the_blockers_it_is_derived_from(self):
        request = self._new_request()
        self._drive_to_cert_check(request)
        self.assertFalse(request.ready_to_advance)
        self.assertTrue(request._progress_blockers())
        with self.assertRaises(ValidationError):
            self._as(request, self.user_cert).action_grant_office_accreditation()

        self._accept_all_documents(request)
        request.invalidate_recordset()
        self.assertTrue(request.ready_to_advance)
        self.assertFalse(request._progress_blockers())
        self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertEqual(request.state, "office_granted")

    def test_05_ready_to_advance_covers_every_gate_of_the_second_phase(self):
        request = self._new_request()
        self._drive_to_dual_confirm(request)

        # Neither department has signed: the gate is shut.
        self.assertFalse(request.ready_to_advance)
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_dual_confirm_done()

        self._as(request, self.user_finance).action_finance_confirm()
        self.assertFalse(request.ready_to_advance, "one signature is not two")
        self._as(request, self.user_operations).action_operations_confirm()
        self.assertTrue(request.ready_to_advance)
        self._as(request, self.user_finance).action_dual_confirm_done()

        # demo_fee: no confirmed fee yet.
        self.assertEqual(request.state, "demo_fee")
        self.assertFalse(request.ready_to_advance)
        self._add_confirmed_fee(request, "operational_demo", "REC/UI/DEMO")
        request.invalidate_recordset()
        self.assertTrue(request.ready_to_advance)

    def test_06_a_draft_without_a_scope_is_not_ready(self):
        request = self._new_request(scope_ids=[(5, 0, 0)])
        self.assertFalse(request.ready_to_advance)
        with self.assertRaises(ValidationError):
            self._as(request, self.user_reception).action_submit()
        request.write({"scope_ids": [(6, 0, self.scopes.ids)]})
        self.assertTrue(request.ready_to_advance)

    # ------------------------------------------------------------------
    # waiting_since / blocker_summary - what a queue and a board show
    # ------------------------------------------------------------------
    def test_07_waiting_since_follows_the_approval_log(self):
        request = self._new_request()
        self.assertEqual(
            request.waiting_since, request.create_date,
            "a file nobody has decided on has been waiting since it was opened",
        )
        self._as(request, self.user_reception).action_submit()
        request.invalidate_recordset()
        last = max(request.approval_line_ids.mapped("date"))
        self.assertEqual(request.waiting_since, last)

        self._as(request, self.user_reception).action_send_to_general_director()
        request.invalidate_recordset()
        self.assertGreaterEqual(request.waiting_since, last,
                                "it moves forward with every hand-off")

    def test_08_a_queue_can_sort_on_waiting_since(self):
        """It is stored and indexed, otherwise the queue order is a lie."""
        field = self.env["dma.accreditation.request"]._fields["waiting_since"]
        self.assertTrue(field.store)
        old = self._new_request()
        fresh = self._new_request()
        old.flush_recordset()
        # Backdate through SQL: the field is computed, not writable.
        self.env.cr.execute(
            "UPDATE dma_accreditation_request SET waiting_since = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=30), old.id),
        )
        old.invalidate_recordset()
        found = self.env["dma.accreditation.request"].search(
            [("id", "in", (old | fresh).ids)], order="waiting_since asc",
        )
        self.assertEqual(found[0], old, "the oldest work on the desk comes first")

    def test_09_blocker_summary_is_the_first_thing_in_the_way(self):
        request = self._new_request()
        self._drive_to_cert_check(request)
        self.assertTrue(request.blocker_summary)
        self.assertEqual(request.blocker_summary, request._progress_blockers()[0])
        self._accept_all_documents(request)
        request.invalidate_recordset()
        self.assertFalse(request.blocker_summary)

    # ------------------------------------------------------------------
    # The checklist rollup and its guards
    # ------------------------------------------------------------------
    def test_10_line_status_separates_the_two_states_the_gate_turns_on(self):
        request = self._new_request()
        line = request.document_ids.filtered("is_required")[0]
        self.assertEqual(line.line_status, "to_provide")

        line.with_user(self.user_reception).write({"is_provided": True})
        self.assertEqual(line.line_status, "to_review",
                         "handed in is not the same as signed off")

        self._drive_to_cert_check(request)
        line.with_user(self.user_cert).action_accept()
        self.assertEqual(line.line_status, "accepted")

        line.with_user(self.user_cert).write({"notes": "Policy expired 2025-11-30."})
        line.with_user(self.user_cert).action_mark_invalid()
        self.assertEqual(line.line_status, "invalid")
        self.assertTrue(line.is_provided,
                        "invalid means it arrived and does not qualify")

        line.with_user(self.user_cert).action_mark_missing()
        self.assertEqual(line.line_status, "missing")
        self.assertFalse(line.is_provided)

        optional = request.document_ids.filtered("is_required")[1]
        optional.with_user(self.user_cert).write({"is_required": False})
        self.assertEqual(optional.line_status, "optional")

    def test_11_marking_a_document_invalid_is_reserved_to_certifications(self):
        request = self._new_request()
        line = request.document_ids[0]
        line.with_user(self.user_reception).write({"is_provided": True})
        self._drive_to_cert_check(request)
        with self.assertRaises(AccessError):
            line.with_user(self.user_reception).action_mark_invalid()
        line.with_user(self.user_cert).write({"notes": "Signature missing."})
        line.with_user(self.user_cert).action_mark_invalid()
        self.assertEqual(line.review_result, "invalid")
        self.assertEqual(line.reviewed_by, self.user_cert,
                         "the review stamp is written whatever the outcome")

    def test_11b_a_document_cannot_be_verified_before_certifications_get_it(self):
        """The row buttons gate on the step; the dialog and RPC must too.

        Otherwise a Certifications officer signs a whole checklist off while
        the file is still with the General Director, and it arrives at the hard
        gate already open with nothing in the approvals log.
        """
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self.assertEqual(request.state, "gd_review")
        line = request.document_ids[0]
        line.with_user(self.user_reception).write({"is_provided": True})
        with self.assertRaises(UserError):
            line.with_user(self.user_cert).action_accept()
        self.assertFalse(request.checklist_complete)

        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        line.with_user(self.user_cert).action_accept()
        self.assertEqual(line.review_result, "accepted")

    def test_11c_a_negative_verdict_records_why(self):
        request = self._new_request()
        self._drive_to_cert_check(request)
        line = request.document_ids[0]
        line.with_user(self.user_cert).action_accept()
        with self.assertRaises(ValidationError):
            line.with_user(self.user_cert).action_mark_invalid()
        line.with_user(self.user_cert).write({
            "notes": "The third-party liability cover expired on 30 June 2026.",
        })
        line.with_user(self.user_cert).action_mark_invalid()
        self.assertEqual(line.line_status, "invalid")
        # "Missing" needs no note: never handed over says itself.
        line.with_user(self.user_cert).write({"notes": False})
        line.with_user(self.user_cert).action_mark_missing()
        self.assertEqual(line.line_status, "missing")

    def test_11d_the_checklist_of_a_closed_file_is_history(self):
        request = self._new_request()
        self._drive_to_authorized(request)
        line = request.document_ids[0]
        with self.assertRaises(UserError):
            line.with_user(self.user_cert).write({"is_provided": False})
        with self.assertRaises(UserError):
            line.with_user(self.user_reception).write({"notes": "late note"})

    def test_12_the_checklist_cannot_be_reloaded_on_a_closed_file(self):
        request = self._new_request()
        self._drive_to_office_granted(request)
        # Still open: reloading is fine.
        request.with_user(self.user_cert).action_reload_checklist()

        closed = self._new_request()
        self._drive_to_cert_check(closed)
        self._as(closed, self.user_cert).action_reject("refused")
        with self.assertRaises(UserError):
            closed.with_user(self.user_cert).action_reload_checklist()

    def test_13_the_checklist_chip_survives_a_right_to_left_paragraph(self):
        """No spaces around the slash, so bidi cannot reorder "3 / 10"."""
        request = self._new_request()
        self.assertNotIn(" / ", request.checklist_progress)
        self.assertRegex(request.checklist_progress, r"^\d+/\d+$")

    def test_14_attachment_counts_are_exposed_for_the_lists(self):
        request = self._new_request()
        line = request.document_ids[0]
        self.assertEqual(line.attachment_count, 0)
        attachment = self.env["ir.attachment"].create({
            "name": "registration.pdf", "type": "binary", "raw": b"%PDF-1.4\n",
        })
        line.with_user(self.user_reception).write(
            {"attachment_ids": [(6, 0, attachment.ids)]}
        )
        self.assertEqual(line.attachment_count, 1)

    # ------------------------------------------------------------------
    # SOP evidence
    # ------------------------------------------------------------------
    def test_15_the_electronic_sop_flag_is_readable_by_every_department(self):
        """It is stored through sudo, because ir.attachment hides records.

        The SOP page and the header button both key on it; a view level
        ``not sop_attachment_ids`` would tell an officer who cannot read the
        attachment that the SOP is missing when it is on file.
        """
        request = self._new_request()
        self._drive_to_office_granted(request)
        self._as(request, self.user_operations).action_start_operational_phase()
        self.assertFalse(request.sop_electronic_received)
        self.assertEqual(request.sop_attachment_count, 0)

        self._attach_sop(request)
        request.invalidate_recordset()
        self.assertTrue(request.sop_electronic_received)
        self.assertEqual(request.sop_attachment_count, 1)
        self.assertTrue(
            self._as(request, self.user_finance).sop_electronic_received,
            "a department that does not own the attachment still sees the fact",
        )

    # ------------------------------------------------------------------
    # Money
    # ------------------------------------------------------------------
    def test_16_the_fees_tab_separates_pending_money_from_confirmed_money(self):
        request = self._new_request()
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id, "fee_type": "sop_reading", "amount": 250.0,
        })
        request.invalidate_recordset()
        self.assertEqual(request.total_fees_pending, 250.0)
        self.assertEqual(request.total_fees_confirmed, 0.0)

        fee.write({"receipt_number": "REC/UI/0001",
                   "receipt_date": fields.Date.context_today(request)})
        fee.with_user(self.user_finance).action_confirm()
        request.invalidate_recordset()
        self.assertEqual(request.total_fees_pending, 0.0)
        self.assertEqual(request.total_fees_confirmed, 250.0)

    def test_17_a_confirmed_fee_is_evidence_and_cannot_be_deleted(self):
        request = self._new_request()
        fee = self._add_confirmed_fee(request, "sop_reading", "REC/UI/DEL")
        with self.assertRaises(UserError):
            fee.with_user(self.user_finance).unlink()
        # The manager may, because only the manager can reset it either way.
        fee.with_user(self.user_manager).unlink()

        draft = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id, "fee_type": "sop_reading", "amount": 10.0,
        })
        draft.with_user(self.user_finance).unlink()

    # ------------------------------------------------------------------
    # Issued accreditation
    # ------------------------------------------------------------------
    def test_18_validity_state_says_when_an_accreditation_has_lapsed(self):
        request = self._new_request()
        self.assertFalse(request.validity_state, "nothing has been issued")
        self._drive_to_authorized(request)
        self.assertEqual(request.validity_state, "valid")

        today = fields.Date.context_today(request)
        request._workflow_write({"expiry_date": today + timedelta(days=10)})
        self.assertEqual(request.validity_state, "expiring")
        request._workflow_write({"expiry_date": today - timedelta(days=1)})
        self.assertEqual(
            request.validity_state, "expired",
            "the green ribbon has to come off a certificate that has run out",
        )

    def test_19_validity_state_is_never_stored(self):
        """A date-relative answer changes because the calendar moved.

        Stored, it would go stale overnight on every accreditation that lapses
        and no write would ever recompute it.
        """
        field = self.env["dma.accreditation.request"]._fields["validity_state"]
        self.assertFalse(field.store)

    # ------------------------------------------------------------------
    # Audit trail
    # ------------------------------------------------------------------
    def test_20_the_approvals_tab_can_count_its_own_entries(self):
        request = self._new_request()
        self.assertEqual(request.approval_line_count, 0)
        self._as(request, self.user_reception).action_submit()
        request.invalidate_recordset()
        self.assertEqual(request.approval_line_count, len(request.approval_line_ids))
        self.assertEqual(request.approval_line_count, 1)

    # ------------------------------------------------------------------
    # The progress payload the widget renders
    # ------------------------------------------------------------------
    def test_21_the_payload_answers_is_this_waiting_for_me(self):
        request = self._new_request()
        self._drive_to_cert_check(request)
        self.assertTrue(self._as(request, self.user_cert).progress_payload["mine"])
        self.assertFalse(self._as(request, self.user_finance).progress_payload["mine"])

    def test_21b_the_rail_names_both_departments_during_the_parallel_step(self):
        """`pending_group` is a scalar, so the headline used to name one of two.

        Saying "Waiting on Finance" while Operations is equally blocking
        contradicts the blocker list rendered directly underneath it.
        """
        request = self._new_request()
        self._drive_to_dual_confirm(request)
        payload = self._as(request, self.user_manager).progress_payload
        self.assertEqual(len(payload["pending_roles"]), 2, payload["pending_roles"])

        self._as(request, self.user_finance).action_finance_confirm()
        request.invalidate_recordset()
        payload = self._as(request, self.user_manager).progress_payload
        self.assertEqual(len(payload["pending_roles"]), 1,
                         "a department drops off the headline once it has signed")

    def test_21c_the_rail_shows_decision_times_in_the_reader_timezone(self):
        """Not naive UTC: the same timestamp is a localised field one tab away."""
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        payload = request.with_context(tz="Asia/Baghdad").progress_payload
        signed = [step for step in payload["steps"] if step["date"]]
        self.assertTrue(signed)
        line = request.approval_line_ids.sorted("id")[0]
        self.assertNotEqual(
            signed[0]["date"], fields.Datetime.to_string(line.date),
            "the payload must not hand the browser a raw UTC string",
        )

    def test_22_a_closed_file_is_waiting_for_nobody(self):
        request = self._new_request()
        self._drive_to_authorized(request)
        for user in (self.user_manager, self.user_legal, self.user_finance):
            with self.subTest(user=user.login):
                self.assertFalse(self._as(request, user).progress_payload["mine"])

    # ------------------------------------------------------------------
    # The return dialog
    # ------------------------------------------------------------------
    def test_23_the_return_wizard_names_the_step_the_file_resumes_at(self):
        request = self._new_request()
        self._drive_to_cert_check(request)
        wizard = self.env["dma.decision.reason"].with_user(self.user_cert).create({
            "request_id": request.id, "mode": "return", "reason": "incomplete",
        })
        self.assertEqual(wizard.current_state, "cert_check")
        self.assertEqual(
            wizard.resume_state, "legal_review",
            "returning from the Certifications check sends the file back to Legal, "
            "which is the fact the reviewer is deciding about",
        )
        wizard.action_confirm()
        self.assertEqual(request.state, "returned")
        self.assertEqual(request.return_to_state, wizard.resume_state)

    # ------------------------------------------------------------------
    # Every view the module ships still compiles
    # ------------------------------------------------------------------
    def test_24_the_views_added_for_the_interface_compile(self):
        self.env["dma.request.document"].with_user(self.user_cert).get_views([
            (self.env.ref("dma_accreditation.dma_request_document_view_form").id, "form"),
        ])
        self.env["dma.accreditation.scope"].with_user(self.user_manager).get_views([
            (self.env.ref("dma_accreditation.dma_accreditation_scope_view_search").id,
             "search"),
        ])
        self.env["dma.accreditation.request"].with_user(self.user_manager).get_views([
            (self.env.ref(
                "dma_accreditation.dma_accreditation_request_view_search_panel"
            ).id, "search"),
        ])

    def test_25_every_role_can_open_the_shared_screens_its_menu_now_offers(self):
        """All Requests and the Approvals Log are open to every department.

        The record rules say the process is collegial; the navigation used to
        say need-to-know. Widening the menus is only safe because reading is
        all it grants.
        """
        request = self._new_request()
        self._drive_to_cert_check(request)
        for user in (self.user_finance, self.user_operations, self.user_committee):
            with self.subTest(user=user.login):
                self.assertIn(
                    request,
                    self.env["dma.accreditation.request"].with_user(user).search([]),
                )
                self.env["dma.approval.line"].with_user(user).search([])
                with self.assertRaises(AccessError):
                    self.env["dma.approval.line"].with_user(user).create({
                        "request_id": request.id, "step": "draft",
                        "role": "manager", "decision": "approved",
                    })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _drive_to_cert_check(self, request):
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        return request

    def _drive_to_authorized(self, request):
        self._drive_to_dual_confirm(request)
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self._add_confirmed_fee(request, "operational_demo", "REC/UI/AUTH")
        self._as(request, self.user_finance).action_demo_fee_registered()
        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()
        request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
        self._as(request, self.user_legal).action_issue_authorization()
        return request
