# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationSecurity(DmaAccreditationCommon):
    """Role guards, the return/reject wizard and the immutable approval log."""

    # ------------------------------------------------------------------
    # Role guards
    # ------------------------------------------------------------------
    def test_01_wrong_role_raises_access_error(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()

        # Finance has no business giving the initial acceptance.
        with self.assertRaises(AccessError):
            self._as(request, self.user_finance).action_gd_accept()
        # Neither has the Legal Department.
        with self.assertRaises(AccessError):
            self._as(request, self.user_legal).action_gd_accept()
        self.assertEqual(request.state, "gd_review")

        # The General Director may.
        self._as(request, self.user_gd).action_gd_accept()
        self.assertEqual(request.state, "legal_review")

    def test_02_every_step_rejects_the_wrong_department(self):
        checks = [
            ("action_submit", self.user_finance),
            ("action_gd_accept", self.user_cert),
            ("action_legal_approve", self.user_operations),
            ("action_grant_office_accreditation", self.user_finance),
            ("action_sop_received", self.user_committee),
            ("action_sop_fee_registered", self.user_legal),
            ("action_finance_confirm", self.user_committee),
            ("action_operations_confirm", self.user_legal),
            ("action_demo_fee_registered", self.user_cert),
            ("action_committee_decision", self.user_reception),
            ("action_issue_authorization", self.user_finance),
        ]
        request = self._new_request()
        for method, user in checks:
            with self.subTest(method=method):
                with self.assertRaises(AccessError):
                    getattr(self._as(request, user), method)()

    def test_03_manager_may_act_on_every_step(self):
        request = self._new_request()
        self._as(request, self.user_manager).action_submit()
        self._as(request, self.user_manager).action_send_to_general_director()
        self._as(request, self.user_manager).action_gd_accept()
        self._as(request, self.user_manager).action_legal_approve()
        self.assertEqual(request.state, "cert_check")

    def test_04_only_finance_confirms_a_fee(self):
        request = self._drive_to_office_granted(self._new_request())
        fee = self.env["dma.fee.payment"].sudo().create({
            "request_id": request.id,
            "fee_type": "sop_reading",
            "amount": 100.0,
            "receipt_number": "REC/TEST/SEC",
            "receipt_date": "2026-01-15",
        })
        with self.assertRaises(UserError):
            fee.with_user(self.user_operations).action_confirm()
        fee.with_user(self.user_finance).action_confirm()
        self.assertEqual(fee.state, "confirmed")
        self.assertEqual(fee.confirmed_by, self.user_finance)

    def test_05_creation_is_limited_to_reception_and_manager(self):
        for user in (self.user_finance, self.user_gd, self.user_committee):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.env["dma.accreditation.request"].with_user(user).create({
                        "partner_id": self.partner.id,
                    })
        # Reception and the manager may.
        self.env["dma.accreditation.request"].with_user(self.user_reception).create({
            "partner_id": self.partner.id,
        })
        self.env["dma.accreditation.request"].with_user(self.user_manager).create({
            "partner_id": self.partner.id,
        })

    def test_06_only_the_manager_deletes_and_only_a_draft(self):
        request = self._new_request()
        with self.assertRaises(AccessError):
            request.with_user(self.user_reception).unlink()

        submitted = self._new_request()
        self._as(submitted, self.user_reception).action_submit()
        with self.assertRaises(UserError):
            submitted.with_user(self.user_manager).unlink()

        request.with_user(self.user_manager).unlink()
        self.assertFalse(request.exists())

    def test_06b_a_decided_file_cannot_be_deleted_even_back_in_draft(self):
        """The cascade on the approval log must not become a way to erase it."""
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        request.with_user(self.user_manager).action_reset_to_draft()
        self.assertEqual(request.state, "draft")
        self.assertTrue(request.approval_line_ids)
        with self.assertRaises(UserError):
            request.with_user(self.user_manager).unlink()
        self.assertTrue(request.exists())
        self.assertTrue(
            request.approval_line_ids,
            "The audit trail survives the deletion attempt",
        )
        # Archiving stays available.
        request.with_user(self.user_manager).action_archive()
        self.assertFalse(request.active)

    def test_07_every_department_reads_every_file(self):
        request = self._new_request()
        for user in (
            self.user_gd, self.user_legal, self.user_cert,
            self.user_operations, self.user_finance, self.user_committee,
        ):
            with self.subTest(user=user.login):
                self.assertEqual(
                    request.with_user(user).partner_id, self.partner,
                    "The process is collegial: every department reads every file",
                )

    # ------------------------------------------------------------------
    # The workflow owns its fields: no writing around the guards
    # ------------------------------------------------------------------
    def test_07b_state_cannot_be_written_directly(self):
        """`readonly` is a client-side hint; the guard has to be in write()."""
        request = self._new_request()
        for user in (self.user_finance, self.user_reception, self.user_manager):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    request.with_user(user).write({"state": "authorized"})
        self.assertEqual(request.state, "draft")
        self.assertFalse(request.approval_line_ids)
        # Not even privileged code may jump the workflow.
        with self.assertRaises(AccessError):
            request.sudo().write({"state": "authorized"})

    def test_07c_official_references_and_signoffs_are_workflow_owned(self):
        request = self._drive_to_dual_confirm(self._new_request())
        protected = {
            "office_ref": "DMA/OFF/2026/9999",
            "certificate_ref": "DMA/CERT/2026/9999",
            "issue_date": "2026-01-01",
            "expiry_date": "2027-01-01",
            "finance_confirmed_sop_fee": True,
            "operations_confirmed_sop": True,
            "sop_paper_received": True,
            "reject_reason": "forged",
            "return_to_state": "draft",
            "verification_token": "deadbeef",
            "name": "DMA/ACC/2026/0000",
        }
        for field, value in protected.items():
            with self.subTest(field=field):
                with self.assertRaises(AccessError):
                    request.with_user(self.user_finance).write({field: value})
        # A forged Operations sign-off would have opened the dual gate.
        self.assertFalse(request.operations_confirmed_sop)
        with self.assertRaises(ValidationError):
            self._as(request, self.user_finance).action_dual_confirm_done()

    def test_07d_ordinary_fields_stay_writable(self):
        """The guard must not turn the request read-only for the departments."""
        request = self._drive_to_office_granted(self._new_request())
        self._as(request, self.user_operations).action_start_operational_phase()
        request.with_user(self.user_operations).write({
            "sop_reference": "SOP-2026", "sop_version": "2.0",
        })
        self.assertEqual(request.sop_reference, "SOP-2026")
        request.with_user(self.user_reception).write({"contact_phone": "+964 1 234"})
        self.assertEqual(request.contact_phone, "+964 1 234")

    def test_07e_checklist_verification_is_reserved_to_certifications(self):
        """Reception assembles the file; only Certifications decides."""
        request = self._drive_to_cert_check(self._new_request())
        line = request.document_ids[0]
        # Reception may attach and tick "provided"...
        line.with_user(self.user_reception).write({"is_provided": True})
        self.assertTrue(line.is_provided)
        # ... but not accept it, nor make a required document optional,
        # nor drop the line: each of those opens the office accreditation gate.
        with self.assertRaises(AccessError):
            line.with_user(self.user_reception).write({"review_result": "accepted"})
        with self.assertRaises(AccessError):
            line.with_user(self.user_reception).write({"is_required": False})
        with self.assertRaises(AccessError):
            line.with_user(self.user_reception).unlink()
        line.with_user(self.user_cert).write({"review_result": "accepted"})
        self.assertEqual(line.review_result, "accepted")
        self.assertEqual(line.reviewed_by, self.user_cert)

    # ------------------------------------------------------------------
    # Immutable approval log
    # ------------------------------------------------------------------
    def test_08_approval_log_cannot_be_written_or_deleted(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        line = request.approval_line_ids[0]

        with self.assertRaises(UserError):
            line.with_user(self.user_manager).write({"notes": "tampered"})
        with self.assertRaises(UserError):
            line.with_user(self.user_manager).unlink()
        # Not even privileged code may rewrite history.
        with self.assertRaises(UserError):
            line.sudo().write({"decision": "rejected"})
        with self.assertRaises(UserError):
            line.sudo().unlink()

    def test_09_approval_log_records_role_and_author(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        entries = request.approval_line_ids.sorted("id")
        self.assertEqual(entries[-1].step, "gd_review")
        self.assertEqual(entries[-1].role, "general_director")
        self.assertEqual(entries[-1].user_id, self.user_gd)
        self.assertEqual(entries[-1].decision, "approved")

    # ------------------------------------------------------------------
    # Return / reject wizard
    # ------------------------------------------------------------------
    def test_10_return_wizard_requires_a_reason(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()

        action = self._as(request, self.user_gd).action_open_return_wizard()
        self.assertEqual(action["res_model"], "dma.decision.reason")
        self.assertEqual(action["context"]["default_mode"], "return")

        wizard = self.env["dma.decision.reason"].with_user(self.user_gd).create({
            "request_id": request.id,
            "mode": "return",
            "reason": "   ",
        })
        with self.assertRaises(ValidationError):
            wizard.action_confirm()
        self.assertEqual(request.state, "gd_review")

        wizard.reason = "The organisational structure is outdated."
        wizard.action_confirm()
        self.assertEqual(request.state, "returned")
        self.assertEqual(request.return_to_state, "submitted")
        self.assertIn("outdated", request.return_reason)

        # A returned file resumes exactly one step back.
        self._as(request, self.user_reception).action_resume_from_return()
        self.assertEqual(request.state, "submitted")
        self.assertFalse(request.return_to_state)

    def test_11_reject_wizard_requires_a_reason_and_closes_the_file(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()

        wizard = self.env["dma.decision.reason"].with_user(self.user_legal).create({
            "request_id": request.id,
            "mode": "reject",
            "reason": "",
        })
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

        wizard.reason = "The applicant does not hold a valid registration."
        wizard.action_confirm()
        self.assertEqual(request.state, "rejected")
        self.assertIn("registration", request.reject_reason)
        self.assertEqual(request.approval_line_ids.sorted("id")[-1].decision, "rejected")

    def test_12_return_is_refused_to_a_department_that_does_not_own_the_step(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        with self.assertRaises(AccessError):
            self._as(request, self.user_finance).action_return_to_applicant("no")

    # ------------------------------------------------------------------
    # "Each role sees only its queue and its buttons"
    # ------------------------------------------------------------------
    def test_14_each_role_sees_only_its_own_queue_menu(self):
        expectations = {
            self.user_reception: {"Reception"},
            self.user_gd: {"Initial Acceptance"},
            self.user_legal: {"Legal Department"},
            self.user_cert: {"Certifications Division"},
            self.user_operations: {"Operations"},
            self.user_finance: {"Finance"},
            self.user_committee: {"Accreditation Committee"},
        }
        queue_menu = self.env.ref("dma_accreditation.menu_dma_queue")
        role_menus = queue_menu.child_id - self.env.ref(
            "dma_accreditation.menu_dma_queue_mine"
        )
        all_names = set(role_menus.mapped("name"))
        for user, expected in expectations.items():
            with self.subTest(user=user.login):
                visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
                seen = {menu.name for menu in role_menus if menu.id in visible}
                self.assertEqual(
                    seen, expected,
                    f"{user.login} must see exactly its own department queue",
                )
                self.assertFalse(
                    seen & (all_names - expected),
                    "no queue of another department may be visible",
                )
        # The manager sees every queue.
        manager_visible = self.env["ir.ui.menu"].with_user(
            self.user_manager
        )._visible_menu_ids()
        self.assertEqual(
            {menu.name for menu in role_menus if menu.id in manager_visible},
            all_names,
        )

    def test_15_configuration_menus_are_manager_only(self):
        config_menus = self.env.ref("dma_accreditation.menu_dma_configuration")
        for user in (self.user_reception, self.user_gd, self.user_finance):
            with self.subTest(user=user.login):
                visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
                self.assertNotIn(config_menus.id, visible)
        self.assertIn(
            config_menus.id,
            self.env["ir.ui.menu"].with_user(self.user_manager)._visible_menu_ids(),
        )

    def test_16_form_shows_only_the_buttons_of_the_reader(self):
        """get_views() strips the buttons whose groups= the reader lacks."""
        view_id = self.env.ref(
            "dma_accreditation.dma_accreditation_request_view_form"
        ).id
        expectations = {
            self.user_gd: ("action_gd_accept", "action_sop_fee_registered"),
            self.user_finance: ("action_sop_fee_registered", "action_gd_accept"),
            self.user_committee: ("action_committee_decision", "action_legal_approve"),
            self.user_cert: (
                "action_grant_office_accreditation", "action_demo_fee_registered",
            ),
        }
        for user, (present, absent) in expectations.items():
            with self.subTest(user=user.login):
                views = self.env["dma.accreditation.request"].with_user(user).get_views(
                    [(view_id, "form")]
                )
                arch = views["views"]["form"]["arch"]
                self.assertIn(present, arch, f"{user.login} should see {present}")
                self.assertNotIn(absent, arch, f"{user.login} must not see {absent}")

    def test_13_return_target_is_one_step_back_from_every_review_state(self):
        expectations = {
            "gd_review": "submitted",
            "legal_review": "gd_review",
            "cert_check": "legal_review",
        }
        for state, target in expectations.items():
            with self.subTest(state=state):
                request = self._new_request()
                self._as(request, self.user_reception).action_submit()
                self._as(request, self.user_reception).action_send_to_general_director()
                if state != "gd_review":
                    self._as(request, self.user_gd).action_gd_accept()
                if state == "cert_check":
                    self._as(request, self.user_legal).action_legal_approve()
                request.sudo().action_return_to_applicant("Missing paperwork.")
                self.assertEqual(request.state, "returned")
                self.assertEqual(request.return_to_state, target)
