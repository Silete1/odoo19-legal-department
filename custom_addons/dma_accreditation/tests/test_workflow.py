# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationWorkflow(DmaAccreditationCommon):
    """The full happy path, each step acted by the department that owns it."""

    def test_01_sequence_and_checklist_on_create(self):
        request = self._new_request()
        self.assertTrue(
            request.name.startswith("DMA/ACC/"),
            f"The reference should come from the sequence, got {request.name!r}",
        )
        self.assertEqual(request.state, "draft")
        self.assertTrue(request.verification_token, "A verification token is expected")
        doc_types = self.env["dma.document.type"].search([])
        self.assertEqual(
            len(request.document_ids), len(doc_types),
            "One checklist line per active document type is expected",
        )
        self.assertEqual(request.required_document_count, 10)
        self.assertFalse(request.checklist_complete)

    def test_02_full_happy_path_draft_to_authorized(self):
        request = self._new_request()

        # -- Phase 1: office accreditation -------------------------------
        self._as(request, self.user_reception).action_submit()
        self.assertEqual(request.state, "submitted")
        self.assertEqual(request.submission_date, fields.Date.context_today(request))

        self._as(request, self.user_reception).action_send_to_general_director()
        self.assertEqual(request.state, "gd_review")
        self.assertEqual(request.pending_group, "general_director")

        self._as(request, self.user_gd).action_gd_accept()
        self.assertEqual(request.state, "legal_review")

        self._as(request, self.user_legal).action_legal_approve()
        self.assertEqual(request.state, "cert_check")
        self.assertEqual(request.pending_group, "cert_officer")

        self._accept_all_documents(request)
        self.assertTrue(request.checklist_complete)
        self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertEqual(request.state, "office_granted")
        self.assertTrue(request.office_ref.startswith("DMA/OFF/"))
        self.assertEqual(request.office_date, fields.Date.context_today(request))

        # The applicant has been notified by e-mail, with the right template.
        template = self.env.ref("dma_accreditation.mail_template_office_granted")
        mails = self.env["mail.mail"].sudo().search([
            ("model", "=", request._name), ("res_id", "=", request.id),
        ])
        self.assertTrue(mails, "An office accreditation notification is expected")
        recipients = mails.mapped("recipient_ids")
        self.assertIn(
            request.contact_partner_id, recipients,
            "The notification goes to the representative of the applicant, "
            "not only to the organisation",
        )
        self.assertTrue(
            any(request.office_ref in (mail.body_html or "") for mail in mails),
            "The notification carries the office accreditation reference",
        )
        self.assertTrue(
            any(template.subject.split("{{")[0].strip() in (mail.subject or "") or
                "التفويض المكتبي" in (mail.subject or "") for mail in mails),
            "The mail is the office accreditation template, not just any mail",
        )

        # -- Phase 2: operational accreditation --------------------------
        self._as(request, self.user_operations).action_start_operational_phase()
        self.assertEqual(request.state, "sop_submission")

        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        self.assertTrue(request.sop_paper_received)
        self.assertEqual(request.sop_paper_received_by, self.user_operations)

        self._as(request, self.user_operations).action_sop_received()
        self.assertEqual(request.state, "sop_fee")

        self._add_confirmed_fee(request, "sop_reading", "REC/TEST/SOP")
        self.assertTrue(request.sop_fee_paid)
        self._as(request, self.user_finance).action_sop_fee_registered()
        self.assertEqual(request.state, "dual_confirm")

        # Parallel dual confirmation, Operations first this time.
        self._as(request, self.user_operations).action_operations_confirm()
        self.assertTrue(request.operations_confirmed_sop)
        self.assertFalse(request.dual_confirm_complete)
        self._as(request, self.user_finance).action_finance_confirm()
        self.assertTrue(request.dual_confirm_complete)

        self._as(request, self.user_finance).action_dual_confirm_done()
        self.assertEqual(request.state, "demo_fee")

        self._add_confirmed_fee(request, "operational_demo", "REC/TEST/DEMO")
        self.assertTrue(request.demo_fee_paid)
        self._as(request, self.user_finance).action_demo_fee_registered()
        self.assertEqual(request.state, "committee")

        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved by the Accreditation Committee.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()
        self.assertEqual(request.state, "legal_refine")

        request.sudo().write({
            "refined_decision_text": "<p>Refined by the Legal Department.</p>",
        })
        self._as(request, self.user_legal).action_issue_authorization()
        self.assertEqual(request.state, "authorized")
        self.assertTrue(request.certificate_ref.startswith("DMA/CERT/"))
        self.assertEqual(request.issue_date, fields.Date.context_today(request))
        self.assertTrue(request.expiry_date > request.issue_date)

        # -- The approvals log is complete and in order ------------------
        steps = request.approval_line_ids.sorted("id").mapped("step")
        self.assertEqual(
            steps,
            [
                "draft", "submitted", "gd_review", "legal_review", "cert_check",
                "office_granted", "sop_submission", "sop_fee",
                "dual_confirm", "dual_confirm", "dual_confirm",
                "demo_fee", "committee", "legal_refine",
            ],
        )
        self.assertTrue(
            all(request.approval_line_ids.mapped("user_id")),
            "Every approval line records its author",
        )

    def test_03_dual_confirmation_order_is_free(self):
        """Finance first also works; only the pair matters."""
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self.assertEqual(request.finance_confirmed_by, self.user_finance)
        self.assertTrue(request.finance_confirmed_on)
        self._as(request, self.user_operations).action_operations_confirm()
        self.assertEqual(request.operations_confirmed_by, self.user_operations)
        self._as(request, self.user_operations).action_dual_confirm_done()
        self.assertEqual(request.state, "demo_fee")

    def test_04_committee_rejection_closes_the_file(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self._add_confirmed_fee(request, "operational_demo", "REC/TEST/DEMO2")
        self._as(request, self.user_finance).action_demo_fee_registered()
        request.sudo().write({
            "committee_decision": "reject",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>The organisation does not meet the standards.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()
        self.assertEqual(request.state, "rejected")
        self.assertTrue(request.reject_reason)

    def test_05_pending_group_and_my_turn_follow_the_state(self):
        request = self._new_request()
        self.assertEqual(request.pending_group, "reception")
        self.assertTrue(self._as(request, self.user_reception).is_my_turn)
        self.assertFalse(self._as(request, self.user_gd).is_my_turn)

        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self.assertEqual(request.pending_group, "general_director")
        self.assertTrue(self._as(request, self.user_gd).is_my_turn)
        self.assertFalse(self._as(request, self.user_finance).is_my_turn)

        # The search side of the field must agree with the computed side.
        found = self.env["dma.accreditation.request"].with_user(self.user_gd).search([
            ("is_my_turn", "=", True), ("id", "=", request.id),
        ])
        self.assertEqual(found, request)
        not_found = self.env["dma.accreditation.request"].with_user(self.user_finance).search([
            ("is_my_turn", "=", True), ("id", "=", request.id),
        ])
        self.assertFalse(not_found)

    def test_06_dual_confirm_my_turn_is_per_side(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self.assertTrue(self._as(request, self.user_finance).is_my_turn)
        self.assertTrue(self._as(request, self.user_operations).is_my_turn)
        self._as(request, self.user_finance).action_finance_confirm()
        self.assertFalse(
            self._as(request, self.user_finance).is_my_turn,
            "Finance already signed: the file is no longer on their desk",
        )
        self.assertTrue(self._as(request, self.user_operations).is_my_turn)

    def test_08_dual_confirm_notifies_both_departments(self):
        """The parallel step is the only one with two responsible departments."""
        request = self._drive_to_dual_confirm(self._new_request())
        activities = self.env["mail.activity"].sudo()

        def owners():
            return set(activities.search([
                ("res_model", "=", request._name), ("res_id", "=", request.id),
            ]).mapped("user_id"))

        # A demo database has its own users in those groups, so assert on the
        # two users this test owns rather than on the whole set.
        self.assertIn(self.user_finance, owners())
        self.assertIn(
            self.user_operations, owners(),
            "Operations must be notified too: the step is parallel",
        )
        self.assertEqual(set(request._pending_roles()), {"finance", "operations"})

        self._as(request, self.user_finance).action_finance_confirm()
        self.assertNotIn(
            self.user_finance, owners(),
            "Finance signed, so its to-do must be gone",
        )
        self.assertIn(self.user_operations, owners())
        self.assertEqual(request._pending_roles(), ["operations"])

        self._as(request, self.user_operations).action_operations_confirm()
        self.assertNotIn(self.user_operations, owners())
        self.assertIn(
            self.user_finance, owners(),
            "Both signed: a to-do remains to push the file to the next step",
        )

        self._as(request, self.user_finance).action_dual_confirm_done()
        self.assertIn(
            self.user_finance, owners(),
            "The demonstration fee is a Finance step",
        )
        self.assertNotIn(self.user_operations, owners())

    def test_09_closing_a_file_clears_its_activities(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self.assertTrue(self.env["mail.activity"].sudo().search([
            ("res_model", "=", request._name), ("res_id", "=", request.id),
        ]))
        request.sudo().action_reject("Not eligible.")
        self.assertFalse(
            self.env["mail.activity"].sudo().search([
                ("res_model", "=", request._name), ("res_id", "=", request.id),
            ]),
            "A rejected file must not leave to-dos behind",
        )

    def test_10_my_turn_search_matches_the_computed_field_everywhere(self):
        """The `search=` domain and the Python compute must never disagree.

        A hand-built prefix domain gets this wrong the moment one branch has
        more than one leaf, and the mismatch is invisible until a whole step
        silently disappears from a department's queue.
        """
        cases = {}
        cases["sop_fee"] = self._drive_to_office_granted(self._new_request())
        self._as(cases["sop_fee"], self.user_operations).action_start_operational_phase()
        self._attach_sop(cases["sop_fee"])
        self._as(cases["sop_fee"], self.user_operations).action_register_paper_sop()
        self._as(cases["sop_fee"], self.user_operations).action_sop_received()

        cases["dual_confirm"] = self._drive_to_dual_confirm(self._new_request())

        signed = self._drive_to_dual_confirm(self._new_request())
        self._as(signed, self.user_finance).action_finance_confirm()
        cases["dual_confirm_finance_signed"] = signed

        both = self._drive_to_dual_confirm(self._new_request())
        self._as(both, self.user_finance).action_finance_confirm()
        self._as(both, self.user_operations).action_operations_confirm()
        cases["dual_confirm_both_signed"] = both

        demo = self._drive_to_dual_confirm(self._new_request())
        self._as(demo, self.user_finance).action_finance_confirm()
        self._as(demo, self.user_operations).action_operations_confirm()
        self._as(demo, self.user_finance).action_dual_confirm_done()
        cases["demo_fee"] = demo

        cases["draft"] = self._new_request()

        users = (
            self.user_reception, self.user_gd, self.user_legal, self.user_cert,
            self.user_operations, self.user_finance, self.user_committee,
            self.user_manager,
        )
        Request = self.env["dma.accreditation.request"]
        for label, request in cases.items():
            for user in users:
                with self.subTest(case=label, user=user.login):
                    computed = request.with_user(user).is_my_turn
                    found = bool(Request.with_user(user).search([
                        ("is_my_turn", "=", True), ("id", "=", request.id),
                    ]))
                    self.assertEqual(
                        computed, found,
                        f"compute says {computed} but the search says {found}",
                    )
                    negated = bool(Request.with_user(user).search([
                        ("is_my_turn", "=", False), ("id", "=", request.id),
                    ]))
                    self.assertEqual(
                        negated, not computed,
                        "the negated search must be the exact complement",
                    )

        # The concrete regressions behind this test.
        self.assertTrue(
            cases["demo_fee"].with_user(self.user_finance).is_my_turn,
            "Finance owns the demonstration fee step even after signing the "
            "dual confirmation",
        )
        self.assertTrue(
            cases["dual_confirm_both_signed"].with_user(self.user_finance).is_my_turn,
            "Both sides signed: the file still needs someone to move it on",
        )
        self.assertTrue(
            cases["dual_confirm"].with_user(self.user_manager).is_my_turn,
            "A manager holds every role and must still get a coherent queue",
        )

    def test_11_reset_to_draft_drops_the_previous_signoffs(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        lines_before = len(request.approval_line_ids)

        request.with_user(self.user_manager).action_reset_to_draft()

        self.assertEqual(request.state, "draft")
        self.assertFalse(request.finance_confirmed_sop_fee)
        self.assertFalse(request.operations_confirmed_sop)
        self.assertFalse(request.sop_paper_received)
        self.assertTrue(
            request.fee_ids, "The fees are evidence and stay on the file",
        )
        self.assertTrue(
            request.document_ids, "The checklist stays on the file",
        )
        self.assertGreater(
            len(request.approval_line_ids), lines_before,
            "The reset itself is recorded in the approvals log",
        )
        # A replay has to obtain the sign-offs again.
        self._as(request, self.user_manager).action_submit()
        self._as(request, self.user_manager).action_send_to_general_director()
        self._as(request, self.user_manager).action_gd_accept()
        self._as(request, self.user_manager).action_legal_approve()
        self._as(request, self.user_manager).action_grant_office_accreditation()
        self._as(request, self.user_manager).action_start_operational_phase()
        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()
        self._as(request, self.user_finance).action_sop_fee_registered()
        self.assertEqual(request.state, "dual_confirm")
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_dual_confirm_done()

    def test_12_empty_rich_text_does_not_satisfy_the_decision_gates(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self._add_confirmed_fee(request, "operational_demo", "REC/TEST/EMPTY")
        self._as(request, self.user_finance).action_demo_fee_registered()
        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p><br></p>",
        })
        with self.assertRaises(ValidationError):
            self._as(request, self.user_committee).action_committee_decision()

        request.sudo().write({"decision_text": "<p>Approved.</p>"})
        self._as(request, self.user_committee).action_committee_decision()
        request.sudo().write({"refined_decision_text": "<p>&nbsp;</p>"})
        with self.assertRaises(ValidationError):
            self._as(request, self.user_legal).action_issue_authorization()

    def test_07_next_step_activity_is_scheduled(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        activities = self.env["mail.activity"].sudo().search([
            ("res_model", "=", request._name), ("res_id", "=", request.id),
        ])
        self.assertIn(
            self.user_gd, activities.mapped("user_id"),
            "The General Director should have a to-do for the initial acceptance",
        )
