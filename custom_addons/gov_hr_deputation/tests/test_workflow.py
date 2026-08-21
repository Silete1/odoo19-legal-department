from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import DeputationCommon


@tagged("post_install", "-at_install")
class TestDeputationWorkflow(DeputationCommon):
    def test_complete_workflow_and_native_activities(self):
        deputation = self._create_deputation()
        self.assertRegex(deputation.name, r"^EFD/\d{4}/\d{4}$")

        deputation.with_user(self.requester_user).action_submit()
        self.assertEqual(deputation.current_approver_user_id, self.dept_manager_user)
        self.assertTrue(deputation.current_activity_id.active)

        with self.assertRaises(AccessError):
            deputation.with_user(self.dg_user).action_approve()
        with self.assertRaises(AccessError):
            deputation.with_user(self.requester_user).action_approve()
        with self.assertRaises(AccessError):
            deputation.with_user(self.admin_manager_user).action_approve()
        with self.assertRaises(AccessError):
            deputation.with_user(self.officer_user).action_issue()
        with self.assertRaises(AccessError):
            deputation.with_user(self.requester_user).write({"destination": "Changed"})

        deputation.with_user(self.dept_manager_user).action_approve()
        deputation.with_user(self.dg_user).action_approve()
        deputation.with_user(self.admin_manager_user).action_approve()
        self.assertEqual(deputation.current_approver_user_id, self.officer_user)

        with self.assertRaises(ValidationError):
            deputation.with_user(self.officer_user).action_verify_documents()
        deputation.basis_line_ids.with_user(self.officer_user).write(
            {"verification_status": "verified"}
        )
        deputation.with_user(self.officer_user).action_verify_documents()
        deputation.with_user(self.officer_user).action_prepare_mission_order()
        self.assertTrue(deputation.memorandum_attachment_id)

        deputation.with_user(self.admin_manager_user).action_approve()
        with self.assertRaises(AccessError):
            deputation.with_user(self.admin_manager_user).action_approve()
        deputation.with_user(self.dg_user).action_approve()
        self.assertEqual(deputation.current_approver_user_id, self.officer_user)
        self.assertTrue(deputation.final_dg_approval_log_id)

        with self.assertRaises(ValidationError):
            deputation.with_user(self.officer_user).action_issue()
        deputation.with_user(self.officer_user).write(
            {"outgoing_number": "1524", "outgoing_date": deputation.date_to}
        )
        deputation.with_user(self.officer_user).action_issue()
        self.assertEqual(deputation.state, "done")
        self.assertTrue(deputation.final_order_attachment_id)
        self.assertFalse(deputation.current_activity_id)
        self.assertEqual(deputation.approval_log_ids.filtered(lambda log: log.action == "approved").mapped("step_id.role_code").count("director_general"), 2)

        with self.assertRaises(AccessError):
            deputation.with_user(self.config_manager_user).write({"destination": "Illegal"})
        with self.assertRaises(AccessError):
            deputation.with_user(self.config_manager_user).unlink()

    def test_return_reason_history_and_resubmission_round(self):
        deputation = self._create_deputation()
        deputation.with_user(self.requester_user).action_submit()
        deputation.with_user(self.dept_manager_user).action_approve()
        with self.assertRaises(ValidationError):
            deputation.with_user(self.dg_user).action_return("")
        deputation.with_user(self.dg_user).action_return("Correct the destination details")
        self.assertEqual(deputation.state, "returned")
        self.assertEqual(deputation.correction_user_id, self.requester_user)
        self.assertTrue(deputation.current_activity_id.active)
        approved_log = deputation.approval_log_ids.filtered(
            lambda log: log.action == "approved"
        )
        self.assertEqual(len(approved_log), 1)

        deputation.with_user(self.requester_user).write({"destination": "Baghdad"})
        deputation.with_user(self.requester_user).action_submit()
        self.assertEqual(deputation.round_number, 2)
        self.assertTrue(approved_log.is_superseded)
        self.assertEqual(deputation.current_approver_user_id, self.dept_manager_user)
        self.assertTrue(deputation.approval_log_ids.filtered(lambda log: log.action == "returned"))
        self.assertTrue(deputation.approval_log_ids.filtered(lambda log: log.action == "restarted"))

        with self.assertRaises(AccessError):
            approved_log.write({"reason": "tamper"})

    def test_required_document_and_org_configuration_validation(self):
        deputation = self._create_deputation()
        deputation.basis_line_ids.with_user(self.requester_user).write({"file_data": False})
        with self.assertRaisesRegex(ValidationError, "required supporting documents"):
            deputation.with_user(self.requester_user).action_submit()

        deputation.basis_line_ids.with_user(self.requester_user).write(
            {"file_data": b"ZmlsZQ=="}
        )
        self.department.manager_id = False
        with self.assertRaisesRegex(ValidationError, "must have a manager"):
            deputation.with_user(self.requester_user).action_submit()

    def test_mission_return_only_unlocks_administrative_correction_fields(self):
        deputation = self._create_deputation()
        self._reach_document_review(deputation)
        deputation.basis_line_ids.with_user(self.officer_user).write(
            {"verification_status": "verified"}
        )
        deputation.with_user(self.officer_user).action_verify_documents()
        deputation.with_user(self.officer_user).action_prepare_mission_order()
        deputation.with_user(self.admin_manager_user).action_return(
            "Clarify the mission-order implementation note"
        )

        self.assertEqual(deputation.correction_user_id, self.officer_user)
        with self.assertRaises(AccessError):
            deputation.with_user(self.officer_user).write({"destination": "Changed"})
        deputation.with_user(self.officer_user).write(
            {"mission_order_notes": "Clarified implementation responsibility"}
        )
        self.assertTrue(
            deputation.with_user(self.officer_user).can_current_user_resubmit
        )
        self.assertFalse(deputation.with_user(self.officer_user).can_edit_business)
        deputation.with_user(self.officer_user).action_submit()
        self.assertEqual(deputation.current_approver_user_id, self.admin_manager_user)

    def test_administrative_manager_reassignment_reroutes_native_activity(self):
        deputation = self._create_deputation()
        self._reach_document_review(deputation)
        old_activity = deputation.current_activity_id
        replacement_user = self._make_user(
            "replacement.officer", self.group_officer
        )
        replacement_employee = self._make_employee(
            "Replacement Administrative Officer", replacement_user
        )
        replacement_employee.department_id = self.admin_department

        deputation.with_user(self.admin_manager_user).write(
            {"administrative_officer_id": replacement_employee.id}
        )

        self.assertEqual(deputation.current_approver_user_id, replacement_user)
        self.assertEqual(deputation.current_activity_id.user_id, replacement_user)
        self.assertFalse(old_activity.active)
