# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Coverage for the corners the main suites leave out.

The other three files follow the process; this one goes after the things that
only bite in production: returning a file from the second phase, the two
notification templates nobody asserts, multi-company isolation, duplicating a
record, the configuration actions, and the fact that the whole suite runs with
``tracking_disable`` so nothing else ever proves the chatter works.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import new_test_user, tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationCoverage(DmaAccreditationCommon):

    # ------------------------------------------------------------------
    # Returning and rejecting from the second phase
    # ------------------------------------------------------------------
    def _drive_to(self, state):
        """Drive a fresh request up to ``state`` and return it."""
        request = self._new_request()
        if state in ("submitted",):
            self._as(request, self.user_reception).action_submit()
            return request
        self._drive_to_office_granted(request)
        if state == "office_granted":
            return request
        self._as(request, self.user_operations).action_start_operational_phase()
        if state == "sop_submission":
            return request
        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()
        if state == "sop_fee":
            return request
        self._add_confirmed_fee(request, "sop_reading", f"REC/COV/{state}")
        self._as(request, self.user_finance).action_sop_fee_registered()
        if state == "dual_confirm":
            return request
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        if state == "demo_fee":
            return request
        self._add_confirmed_fee(request, "operational_demo", f"REC/COV/D/{state}")
        self._as(request, self.user_finance).action_demo_fee_registered()
        if state == "committee":
            return request
        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()
        if state == "legal_refine":
            return request
        request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
        self._as(request, self.user_legal).action_issue_authorization()
        return request

    def test_01_every_phase_two_step_can_be_returned_one_step_back(self):
        expectations = {
            "office_granted": ("cert_check", self.user_operations),
            "sop_submission": ("office_granted", self.user_operations),
            "sop_fee": ("sop_submission", self.user_finance),
            "dual_confirm": ("sop_fee", self.user_finance),
            "demo_fee": ("dual_confirm", self.user_finance),
            "committee": ("demo_fee", self.user_committee),
            "legal_refine": ("committee", self.user_legal),
        }
        for state, (target, actor) in expectations.items():
            with self.subTest(state=state):
                request = self._drive_to(state)
                self.assertEqual(request.state, state)
                self._as(request, actor).action_return_to_applicant(
                    f"Incomplete at {state}."
                )
                self.assertEqual(request.state, "returned")
                self.assertEqual(request.return_to_state, target)
                self._as(request, self.user_reception).action_resume_from_return()
                self.assertEqual(request.state, target)

    def test_02_every_phase_two_step_can_be_rejected(self):
        for state, actor in [
            ("sop_submission", self.user_operations),
            ("dual_confirm", self.user_finance),
            ("committee", self.user_committee),
            ("legal_refine", self.user_legal),
        ]:
            with self.subTest(state=state):
                request = self._drive_to(state)
                self._as(request, actor).action_reject(f"Refused at {state}.")
                self.assertEqual(request.state, "rejected")
                self.assertIn(state, request.reject_reason)
                self.assertEqual(
                    request.approval_line_ids.sorted("id")[-1].decision, "rejected",
                )

    def test_03_a_closed_file_can_no_longer_be_returned_or_rejected(self):
        authorized = self._drive_to("authorized")
        with self.assertRaises(ValidationError):
            authorized.sudo().action_return_to_applicant("too late")
        with self.assertRaises(ValidationError):
            authorized.sudo().action_reject("too late")
        self.assertEqual(authorized.state, "authorized")

        rejected = self._drive_to("committee")
        self._as(rejected, self.user_committee).action_reject("no")
        with self.assertRaises(ValidationError):
            rejected.sudo().action_return_to_applicant("again")

    def test_04_a_draft_cannot_be_returned(self):
        request = self._new_request()
        with self.assertRaises(ValidationError):
            request.sudo().action_return_to_applicant("nothing to return")

    # ------------------------------------------------------------------
    # The notifications nobody else asserts
    # ------------------------------------------------------------------
    def _mails(self, request):
        return self.env["mail.mail"].sudo().search([
            ("model", "=", request._name), ("res_id", "=", request.id),
        ])

    def test_05_the_return_notification_carries_the_reason(self):
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()
        before = self._mails(request)
        reason = "The insurance policies attached are expired."
        self._as(request, self.user_gd).action_return_to_applicant(reason)
        new = self._mails(request) - before
        self.assertTrue(new, "Returning notifies the applicant")
        bodies = " ".join(mail.body_html or "" for mail in new)
        self.assertIn(reason, bodies, "The reason itself reaches the applicant")
        self.assertIn(
            request.contact_partner_id, new.mapped("recipient_ids"),
            "The notification is addressed to the representative",
        )

    def test_06_the_rejection_notification_carries_the_reason(self):
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()
        before = self._mails(request)
        reason = "The organisation holds no valid registration certificate."
        self._as(request, self.user_gd).action_reject(reason)
        new = self._mails(request) - before
        bodies = " ".join(mail.body_html or "" for mail in new)
        self.assertIn(reason, bodies)

    def test_07_the_final_authorisation_notification_carries_the_certificate(self):
        request = self._drive_to("legal_refine")
        before = self._mails(request)
        request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
        self._as(request, self.user_legal).action_issue_authorization()
        new = self._mails(request) - before
        self.assertTrue(new, "Issuing the accreditation notifies the applicant")
        bodies = " ".join(mail.body_html or "" for mail in new)
        self.assertIn(request.certificate_ref, bodies)
        self.assertIn(str(request.expiry_date), bodies)

    def test_08_a_file_without_any_address_does_not_break_the_workflow(self):
        """No e-mail must never mean no accreditation."""
        silent = self.env["res.partner"].create({
            "name": "Company With No Email", "is_company": True,
        })
        request = self._new_request(partner_id=silent.id, contact_partner_id=False)
        self._drive_to_office_granted(request)
        self.assertEqual(request.state, "office_granted")
        self.assertTrue(
            any("e-mail address" in (m.body or "") for m in request.message_ids),
            "The chatter says why nothing was sent",
        )

    # ------------------------------------------------------------------
    # Multi-company isolation
    # ------------------------------------------------------------------
    def test_09_a_request_of_another_company_is_invisible(self):
        other_company = self.env["res.company"].create({"name": "Other Directorate"})
        mine = self._new_request()
        theirs = self._new_request()
        theirs.sudo().company_id = other_company

        stranger = new_test_user(
            self.env,
            login="dma_test_other_company",
            name="DMA Test Other Company",
            email="dma_test_other_company@example.com",
            groups="base.group_user,dma_accreditation.group_dma_manager",
            company_id=other_company.id,
            company_ids=[(6, 0, other_company.ids)],
        )
        visible = self.env["dma.accreditation.request"].with_user(stranger).search([])
        self.assertIn(theirs, visible)
        self.assertNotIn(mine, visible, "The multi-company rule isolates the files")

        # ... and the approval log of a foreign file is invisible too.
        self._as(mine, self.user_reception).action_submit()
        self.assertFalse(
            self.env["dma.approval.line"].with_user(stranger).search([
                ("request_id", "=", mine.id),
            ]),
            "The audit trail follows the company boundary",
        )

    # ------------------------------------------------------------------
    # Duplicating, archiving, reloading
    # ------------------------------------------------------------------
    def test_10_duplicating_a_file_starts_it_clean(self):
        source = self._drive_to("sop_fee")
        copy = source.with_user(self.user_reception).copy()
        self.assertNotEqual(copy.name, source.name)
        self.assertTrue(copy.name.startswith("DMA/ACC/"))
        self.assertEqual(copy.state, "draft")
        self.assertNotEqual(copy.verification_token, source.verification_token)
        for field in (
            "office_ref", "office_date", "certificate_ref", "issue_date",
            "expiry_date", "submission_date", "sop_paper_received",
            "finance_confirmed_sop_fee", "operations_confirmed_sop",
            "reject_reason", "return_reason", "return_to_state",
        ):
            with self.subTest(field=field):
                self.assertFalse(copy[field], f"{field} must not be copied")
        self.assertFalse(copy.approval_line_ids, "A copy carries no history")
        self.assertTrue(copy.document_ids, "A copy still gets its checklist")

    def test_11_archiving_replaces_deleting(self):
        request = self._drive_to("submitted")
        request.with_user(self.user_manager).action_archive()
        self.assertFalse(request.active)
        self.assertNotIn(
            request,
            self.env["dma.accreditation.request"].with_user(self.user_gd).search([]),
            "An archived file drops out of the queues",
        )
        request.with_user(self.user_manager).action_unarchive()
        self.assertTrue(request.active)

    def test_12_reloading_the_checklist_picks_up_new_document_types(self):
        request = self._new_request()
        before = len(request.document_ids)
        new_type = self.env["dma.document.type"].with_user(self.user_manager).create({
            "name": "Mine Risk Education Curriculum",
            "sequence": 110,
            "required_default": True,
        })
        self.assertEqual(len(request.document_ids), before,
                         "An existing file is not rewritten behind the officer's back")

        with self.assertRaises(AccessError):
            request.with_user(self.user_finance).action_reload_checklist()

        request.with_user(self.user_cert).action_reload_checklist()
        self.assertEqual(len(request.document_ids), before + 1)
        self.assertIn(new_type, request.document_ids.type_id)

        # Reloading twice must not duplicate anything.
        request.with_user(self.user_cert).action_reload_checklist()
        self.assertEqual(len(request.document_ids), before + 1)

    # ------------------------------------------------------------------
    # Fees
    # ------------------------------------------------------------------
    def test_13_a_confirmed_fee_can_be_reset_only_by_finance_or_the_manager(self):
        request = self._drive_to("sop_fee")
        fee = self._add_confirmed_fee(request, "sop_reading", "REC/COV/RESET")
        with self.assertRaises(UserError):
            fee.with_user(self.user_operations).action_reset_draft()
        fee.with_user(self.user_finance).action_reset_draft()
        self.assertEqual(fee.state, "draft")
        self.assertFalse(fee.confirmed_by)
        self.assertFalse(request.sop_fee_paid)
        # ... and the step it was gating closes again.
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_sop_fee_registered()

    def test_14_a_negative_fee_is_refused_by_the_database(self):
        request = self._new_request()
        with self.assertRaises(Exception):
            with self.cr.savepoint():
                self.env["dma.fee.payment"].with_user(self.user_finance).create({
                    "request_id": request.id,
                    "fee_type": "sop_reading",
                    "amount": -10.0,
                })

    def test_15_a_fee_of_zero_cannot_be_confirmed(self):
        request = self._new_request()
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": "sop_reading",
            "amount": 0.0,
            "receipt_number": "REC/COV/ZERO",
            "receipt_date": fields.Date.context_today(request),
        })
        with self.assertRaises(ValidationError):
            fee.action_confirm()

    # ------------------------------------------------------------------
    # The approval log cannot be forged
    # ------------------------------------------------------------------
    def test_16_nobody_can_append_to_the_approval_log_by_hand(self):
        request = self._drive_to("submitted")
        for user in (self.user_reception, self.user_gd, self.user_manager):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.env["dma.approval.line"].with_user(user).create({
                        "request_id": request.id,
                        "step": "authorized",
                        "role": "general_director",
                        "decision": "approved",
                    })

    # ------------------------------------------------------------------
    # Chatter and tracking - the rest of the suite runs with tracking off
    # ------------------------------------------------------------------
    def test_17_a_transition_is_tracked_and_posted_to_the_chatter(self):
        env = self.env(context=dict(self.env.context, tracking_disable=False))
        request = env["dma.accreditation.request"].with_user(self.user_reception).create({
            "partner_id": self.partner.id,
            "contact_partner_id": self.contact.id,
            "scope_ids": [(6, 0, self.scopes.ids)],
        })
        # A record created and written in the same transaction has its tracking
        # discarded until the creation itself is finalised, so close the
        # "creation" first, the way a real request would.
        env.flush_all()
        self.cr.flush()
        before = len(request.message_ids)
        acting = request.with_user(self.user_reception)
        acting.action_submit()
        # Tracking messages are built by a precommit hook on the acting
        # environment, which a test transaction never reaches on its own.
        acting.env.flush_all()
        self.cr.flush()          # the helper mail's own tests use
        request.invalidate_recordset()
        self.assertGreater(
            len(request.message_ids), before,
            "The transition is posted to the chatter",
        )
        # tracking values are readable by administrators only
        tracked = request.message_ids.sudo().tracking_value_ids.filtered(
            lambda value: value.field_id.name == "state"
        )
        self.assertTrue(tracked, "The status change is tracked")
        self.assertEqual(tracked[0].new_value_char, "Submitted")
        self.assertEqual(
            request.message_ids.sorted("id")[-1].author_id,
            self.user_reception.partner_id,
            "The chatter names the officer who acted",
        )

    # ------------------------------------------------------------------
    # Search / grouping helpers used by the views
    # ------------------------------------------------------------------
    def test_18_only_the_overview_kanban_shows_the_whole_pipeline(self):
        from ..models.dma_constants import MAIN_PATH_STATES
        Request = self.env["dma.accreditation.request"]

        expanded = Request.with_context(dma_expand_pipeline=1)._group_expand_state(
            ["draft"], None,
        )
        self.assertEqual(
            expanded, MAIN_PATH_STATES,
            "'All Requests' keeps a column per step, empty or not",
        )
        self.assertIsNot(
            expanded, MAIN_PATH_STATES,
            "A copy: the ORM may sort the returned list in place",
        )

        present = ["draft", "cert_check"]
        narrowed = Request._group_expand_state(present, None)
        self.assertEqual(
            narrowed, present,
            "A role queue shows only the steps it actually holds, so its cards "
            "are not buried behind ten empty columns",
        )
        self.assertIsNot(narrowed, present, "Still a copy")

    def test_19_the_my_turn_search_accepts_the_operators_the_client_sends(self):
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()
        Request = self.env["dma.accreditation.request"].with_user(self.user_gd)
        for domain, expected in [
            ([("is_my_turn", "=", True)], True),
            ([("is_my_turn", "!=", False)], True),
            ([("is_my_turn", "=", False)], False),
            ([("is_my_turn", "!=", True)], False),
            ([("is_my_turn", "in", [True])], True),
            ([("is_my_turn", "not in", [True])], False),
            ([("is_my_turn", "in", [False])], False),
        ]:
            with self.subTest(domain=domain):
                found = bool(Request.search(domain + [("id", "=", request.id)]))
                self.assertEqual(found, expected)

    # ------------------------------------------------------------------
    # The two payloads the interface is built on
    # ------------------------------------------------------------------
    def test_21_the_progress_payload_describes_the_file(self):
        request = self._new_request()
        payload = request.progress_payload
        self.assertEqual(len(payload["steps"]), 13)
        self.assertEqual(payload["current"], "draft")
        self.assertEqual(payload["steps"][0]["status"], "current")
        self.assertEqual(payload["steps"][-1]["status"], "todo")
        self.assertFalse(payload["closed"])

        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        payload = request.progress_payload
        self.assertEqual(payload["current"], "cert_check")
        self.assertEqual(payload["pending_role_key"], "cert_officer")
        signed = {step["key"]: step for step in payload["steps"] if step["status"] == "done"}
        self.assertIn("gd_review", signed)
        self.assertEqual(signed["gd_review"]["user"], self.user_gd.display_name)
        self.assertTrue(signed["gd_review"]["date"])

    def test_21b_a_parked_file_does_not_read_as_a_finished_one(self):
        """`returned` and `rejected` sit off the main path.

        Reading the step index off the path therefore fell through to its
        length, which drew every one of the thirteen steps as complete: a file
        the Legal Department had just sent back displayed exactly like an
        accredited one.
        """
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()

        wizard = self.env["dma.decision.reason"].with_user(self.user_legal).create({
            "request_id": request.id,
            "mode": "return",
            "reason": "The financial capability statement is missing.",
        })
        wizard.action_confirm()

        payload = request.progress_payload
        self.assertEqual(request.state, "returned")
        self.assertLess(
            payload["percent"], 100,
            "a returned file has not completed the procedure",
        )
        self.assertLess(payload["steps_done"], payload["steps_total"])
        self.assertEqual(payload["exception"], "returned")
        self.assertTrue(
            any(step["status"] == "todo" for step in payload["steps"]),
            "the steps still to come are still to come",
        )

    def test_21c_an_accredited_file_reaches_the_end_of_the_rail(self):
        """The last step of the path is also the closing state.

        A step equal to the current one was always drawn as in-progress, so an
        accredited file sat one step short of its own certificate for ever.
        """
        request = self._drive_to("authorized")
        payload = request.progress_payload
        self.assertEqual(request.state, "authorized")
        self.assertTrue(payload["closed"])
        self.assertEqual(
            payload["steps_done"], payload["steps_total"],
            "every step of the procedure has been completed",
        )
        self.assertEqual(payload["percent"], 100)
        self.assertEqual(payload["steps"][-1]["status"], "done")

    def test_22_the_progress_payload_names_every_blocker(self):
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        blockers = request.progress_payload["blockers"]
        self.assertEqual(
            len(blockers), request.required_document_count,
            "every unaccepted required document is named",
        )
        self._accept_all_documents(request)
        self.assertFalse(request.progress_payload["blockers"])

        # ... and the dual confirmation names the side that has not signed
        self._as(request, self.user_cert).action_grant_office_accreditation()
        self._as(request, self.user_operations).action_start_operational_phase()
        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()
        self._add_confirmed_fee(request, "sop_reading", "REC/COV/PAYLOAD")
        self._as(request, self.user_finance).action_sop_fee_registered()
        self.assertEqual(len(request.progress_payload["blockers"]), 2)
        self._as(request, self.user_finance).action_finance_confirm()
        self.assertEqual(len(request.progress_payload["blockers"]), 1)

    def test_23_the_dashboard_counts_what_the_reader_may_see(self):
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()

        data = self.env["dma.accreditation.request"].with_user(
            self.user_gd
        ).get_dashboard_data()
        # Twelve, not thirteen: `authorized` is where files come to rest, not
        # a step they pass through. Leaving it in meant the chart accumulated
        # every organisation ever accredited, so one bar was full and the other
        # eleven were slivers. Outcomes are reported separately.
        self.assertEqual(len(data["pipeline"]), 12)
        self.assertEqual(
            [step["key"] for step in data["pipeline"]][:2], ["draft", "submitted"],
        )
        self.assertNotIn(
            "authorized", [step["key"] for step in data["pipeline"]],
            "a finished file is not standing at a step",
        )
        self.assertEqual(
            data["totals"]["authorized"],
            self.env["dma.accreditation.request"].with_user(
                self.user_gd
            ).search_count([("state", "=", "authorized")]),
            "the accredited count moves to the ledger rather than disappearing",
        )
        by_key = {step["key"]: step["count"] for step in data["pipeline"]}
        self.assertGreaterEqual(by_key["gd_review"], 1)
        # The General Director's queue spans both of their steps, so "waiting
        # for me" is their sum, not just the initial acceptance.
        self.assertEqual(
            data["my_turn"], by_key["gd_review"] + by_key["cert_check"],
        )
        self.assertEqual(
            [queue["role"] for queue in data["queues"]], ["general_director"],
            "a reader only sees the queues of the departments they belong to",
        )

        # a manager holds every role, so every queue is listed
        manager_data = self.env["dma.accreditation.request"].with_user(
            self.user_manager
        ).get_dashboard_data()
        self.assertEqual(len(manager_data["queues"]), 7)

    def test_24_the_dashboard_flags_expiring_accreditations(self):
        request = self._drive_to("authorized")

        def expiring_ids():
            return [
                row["id"] for row in self.env["dma.accreditation.request"].with_user(
                    self.user_manager
                ).get_dashboard_data()["expiring"]
            ]

        # Scoped to the record under test. The demo database now ships a
        # generated caseload whose accreditations legitimately fall inside the
        # ninety-day horizon, so asserting the whole list is empty would only
        # be testing how little demo data there is.
        self.assertNotIn(
            request.id, expiring_ids(),
            "a year-long accreditation is not expiring yet",
        )
        today = fields.Date.context_today(request)
        for delta, level in [(60, "warning"), (10, "serious"), (-5, "critical")]:
            with self.subTest(level=level):
                # the issue date moves with it: a certificate may not expire
                # before it was issued (database constraint)
                request.sudo()._workflow_write({
                    "issue_date": today + relativedelta(days=delta - 365),
                    "expiry_date": today + relativedelta(days=delta),
                })
                expiring = self.env["dma.accreditation.request"].with_user(
                    self.user_manager
                ).get_dashboard_data()["expiring"]
                # Picked out by id rather than by position: the demo database
                # ships a caseload of its own, and this test is about one
                # record's level, not about how many others are expiring.
                row = next((e for e in expiring if e["id"] == request.id), None)
                self.assertIsNotNone(row, "the record under test is listed")
                self.assertEqual(row["level"], level)
                self.assertTrue(
                    row["level_label"],
                    "the level is written out, never colour alone",
                )

    def test_25_bulk_checklist_actions_respect_the_roles(self):
        request = self._drive_to("submitted")
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()

        with self.assertRaises(AccessError):
            self._as(request, self.user_finance).action_mark_all_provided()
        self._as(request, self.user_reception).action_mark_all_provided()
        self.assertTrue(all(request.document_ids.mapped("is_provided")))
        self.assertFalse(
            request.checklist_complete,
            "provided is not accepted: the gate is still shut",
        )

        with self.assertRaises(AccessError):
            self._as(request, self.user_reception).action_accept_all_provided()
        self._as(request, self.user_cert).action_accept_all_provided()
        self.assertTrue(request.checklist_complete)
        with self.assertRaises(UserError):
            self._as(request, self.user_cert).action_accept_all_provided()

    def test_20_the_seeded_configuration_matches_the_standard(self):
        types = self.env["dma.document.type"].search([]).mapped("name")
        for expected in [
            "Company Registration Certificate",
            "Organisational Structure",
            "Key Staff CVs and Qualifications",
            "Equipment List",
            "Insurance (Staff Medical and Third-Party Liability)",
            "Safety and Occupational Health Policy",
            "Quality Management Documentation",
            "Prior Demining Experience",
            "Financial Capability Statement",
            "Power of Attorney of the Representative",
        ]:
            self.assertIn(expected, types)
        scopes = self.env["dma.accreditation.scope"].search([]).mapped("name")
        for expected in [
            "Manual Clearance", "Battle Area Clearance",
            "Explosive Ordnance Disposal (EOD)", "Mine Detection Dogs",
            "Mechanical Demining", "Technical Survey", "Non-Technical Survey",
            "Explosive Ordnance Risk Education (EORE)",
        ]:
            self.assertIn(expected, scopes)
        self.assertEqual(len(scopes), 8)
