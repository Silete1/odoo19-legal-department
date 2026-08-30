# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationGates(DmaAccreditationCommon):
    """The two hard gates and the other server side pre-conditions."""

    # ------------------------------------------------------------------
    # Gate 1 - the prerequisites checklist
    # ------------------------------------------------------------------
    def test_01_office_grant_blocked_by_missing_document(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()

        # Everything accepted except one required line.
        self._accept_all_documents(request)
        missing = request.document_ids[0]
        missing.with_user(self.user_cert).write({
            "review_result": "missing", "is_provided": False,
        })
        self.assertFalse(request.checklist_complete)

        with self.assertRaises(ValidationError):
            self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertEqual(request.state, "cert_check", "The file must not move on")

        # The error message names the offending document.
        with self.assertRaises(ValidationError) as catcher:
            self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertIn(missing.type_id.name, str(catcher.exception))

        # Fixing it unblocks the gate.
        missing.with_user(self.user_cert).action_accept()
        self.assertTrue(request.checklist_complete)
        self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertEqual(request.state, "office_granted")

    def test_02_office_grant_blocked_when_provided_but_not_accepted(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        request.with_user(self.user_cert).document_ids.write({"is_provided": True})
        self.assertFalse(
            request.checklist_complete,
            "Provided is not enough: the Certifications Division must accept",
        )
        with self.assertRaises(ValidationError):
            self._as(request, self.user_cert).action_grant_office_accreditation()

    def test_03_office_grant_blocked_on_an_empty_checklist(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        request.sudo().document_ids.unlink()
        with self.assertRaises(ValidationError):
            self._as(request, self.user_cert).action_grant_office_accreditation()

    def test_04_a_document_cannot_be_accepted_before_being_provided(self):
        request = self._drive_to_cert_check(self._new_request())
        with self.assertRaises(ValidationError):
            request.document_ids[0].with_user(self.user_cert).write({
                "review_result": "accepted", "is_provided": False,
            })

    # ------------------------------------------------------------------
    # Gate 2 - the parallel dual confirmation
    # ------------------------------------------------------------------
    def test_05_dual_confirm_blocked_until_both_sides_signed(self):
        request = self._drive_to_dual_confirm(self._new_request())

        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_dual_confirm_done()

        self._as(request, self.user_finance).action_finance_confirm()
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_dual_confirm_done()
        self.assertEqual(request.state, "dual_confirm")

        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self.assertEqual(request.state, "demo_fee")

    def test_06_dual_confirm_blocked_with_only_operations(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_operations).action_operations_confirm()
        with self.assertRaises(ValidationError):
            self._as(request, self.user_operations).action_dual_confirm_done()

    def test_07_a_side_cannot_confirm_twice(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        with self.assertRaises(UserError):
            self._as(request, self.user_finance).action_finance_confirm()

    # ------------------------------------------------------------------
    # Other pre-conditions
    # ------------------------------------------------------------------
    def test_08_submission_requires_a_scope(self):
        request = self._new_request(scope_ids=[(5, 0, 0)])
        with self.assertRaises(ValidationError):
            self._as(request, self.user_reception).action_submit()

    def test_09_sop_step_requires_both_copies(self):
        request = self._drive_to_office_granted(self._new_request())
        self._as(request, self.user_operations).action_start_operational_phase()

        with self.assertRaises(ValidationError):
            self._as(request, self.user_operations).action_sop_received()

        self._attach_sop(request)
        with self.assertRaises(ValidationError):
            self._as(request, self.user_operations).action_sop_received()

        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()
        self.assertEqual(request.state, "sop_fee")

    def test_10_fee_steps_require_a_confirmed_fee(self):
        request = self._drive_to_office_granted(self._new_request())
        self._as(request, self.user_operations).action_start_operational_phase()
        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()

        # A fee that is only drafted does not count.
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": "sop_reading",
            "amount": 100.0,
        })
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_sop_fee_registered()

        # Neither does one without a receipt number.
        with self.assertRaises(ValidationError):
            fee.action_confirm()

        fee.write({
            "receipt_number": "REC/TEST/0099",
            "receipt_date": fields.Date.context_today(request),
        })
        fee.action_confirm()
        self._as(request, self.user_finance).action_sop_fee_registered()
        self.assertEqual(request.state, "dual_confirm")

    def test_11_committee_decision_requires_date_and_text(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self._add_confirmed_fee(request, "operational_demo", "REC/TEST/DEMO3")
        self._as(request, self.user_finance).action_demo_fee_registered()

        with self.assertRaises(ValidationError):
            self._as(request, self.user_committee).action_committee_decision()

        request.sudo().write({"committee_decision": "approve"})
        with self.assertRaises(ValidationError):
            self._as(request, self.user_committee).action_committee_decision()

        request.sudo().write({"committee_date": fields.Date.context_today(request)})
        with self.assertRaises(ValidationError):
            self._as(request, self.user_committee).action_committee_decision()

        request.sudo().write({"decision_text": "<p>Approved.</p>"})
        self._as(request, self.user_committee).action_committee_decision()
        self.assertEqual(request.state, "legal_refine")

    def test_12_authorization_requires_the_refined_text(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self._add_confirmed_fee(request, "operational_demo", "REC/TEST/DEMO4")
        self._as(request, self.user_finance).action_demo_fee_registered()
        request.sudo().write({
            "committee_decision": "conditional",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved with conditions.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()

        with self.assertRaises(ValidationError):
            self._as(request, self.user_legal).action_issue_authorization()

        request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
        self._as(request, self.user_legal).action_issue_authorization()
        self.assertEqual(request.state, "authorized")

    def test_13_actions_are_refused_in_the_wrong_state(self):
        request = self._new_request()
        with self.assertRaises(ValidationError):
            self._as(request, self.user_gd).action_gd_accept()
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_finance_confirm()
