# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Browser walk-throughs of the real interface.

These drive headless Chrome, so they cover what no Python test can: that the
progress widget renders and refreshes, that the checklist bulk buttons are
wired to the right methods, and that a department which does not own the
current step is genuinely offered nothing to press.

They are SKIPPED, not failed, when Chrome or websocket-client is unavailable -
see odoo/tests/common.py. A green run on a machine without Chrome therefore
means "not run"; check the log for the skip.
"""
from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install", "dma_accreditation_tour")
class TestAccreditationTours(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Tour Demining Company",
            "is_company": True,
            "email": "tour@demining.example.com",
        })
        cls.manager = new_test_user(
            cls.env,
            login="dma_tour_manager",
            password="dma_tour_manager",
            name="DMA Tour Manager",
            email="dma_tour_manager@example.com",
            groups="base.group_user,dma_accreditation.group_dma_manager",
        )
        cls.manager.lang = "en_US"
        cls.finance = new_test_user(
            cls.env,
            login="dma_tour_finance",
            password="dma_tour_finance",
            name="DMA Tour Finance",
            email="dma_tour_finance@example.com",
            groups="base.group_user,dma_accreditation.group_dma_finance",
        )
        cls.finance.lang = "en_US"

    def _request_at_cert_check(self):
        """A file waiting on the Certifications Division, checklist incomplete."""
        request = self.env["dma.accreditation.request"].with_user(self.manager).create({
            "partner_id": self.partner.id,
            "scope_ids": [(6, 0, [
                self.env.ref("dma_accreditation.scope_manual_clearance").id,
            ])],
        })
        request = request.with_user(self.manager)
        request.action_submit()
        request.action_send_to_general_director()
        request.action_gd_accept()
        request.action_legal_approve()
        self.assertEqual(request.state, "cert_check")
        self.assertFalse(request.checklist_complete)
        return request

    def test_office_accreditation_can_be_granted_from_the_interface(self):
        request = self._request_at_cert_check()
        self.start_tour(
            f"/odoo/action-dma_accreditation.action_dma_accreditation_request/{request.id}",
            "dma_accreditation_office_grant",
            login="dma_tour_manager",
        )
        request.invalidate_recordset()
        self.assertEqual(
            request.state, "office_granted",
            "the tour really drove the workflow, it did not just click around",
        )
        self.assertTrue(request.checklist_complete)
        self.assertTrue(request.office_ref)
        self.assertIn(
            "cert_check", request.approval_line_ids.mapped("step"),
            "the grant went through the workflow method and was logged",
        )

    def test_a_department_that_does_not_own_the_step_gets_no_button(self):
        request = self._request_at_cert_check()
        self.start_tour(
            f"/odoo/action-dma_accreditation.action_dma_accreditation_request/{request.id}",
            "dma_accreditation_wrong_role",
            login="dma_tour_finance",
        )
        request.invalidate_recordset()
        self.assertEqual(request.state, "cert_check", "nothing moved")
