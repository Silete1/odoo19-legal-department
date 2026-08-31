from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import LegalProcedureCommon


@tagged("post_install", "-at_install")
class TestWizards(LegalProcedureCommon):
    """The two dialogs a clerk actually uses, driven the way the client drives them."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.clerk = Users.create(
            {
                "name": "wiz_clerk",
                "login": "wiz_clerk",
                "group_ids": [
                    (6, 0, [cls.env.ref("legal_core.group_legal_clerk").id])
                ],
            }
        )
        cls.approver = Users.create(
            {
                "name": "wiz_approver",
                "login": "wiz_approver",
                "group_ids": [
                    (6, 0, [cls.env.ref("legal_core.group_legal_approver").id])
                ],
            }
        )

    def test_the_step_dialog_offers_the_configured_fields_and_keeps_the_answers(self):
        self.env["legal.procedure.field"].create(
            {
                "label": "رقم القطعة",
                "code": "plot_number",
                "step_id": self.step_prepare.id,
                "required": True,
            }
        )
        case = self._make_case()
        action = case.action_open_step_dialog()
        self.assertEqual(action["res_model"], "legal.case.step.wizard")

        # The client creates the transient and *then* presses the button, so the
        # lines have to survive that round trip.
        wizard = self.env["legal.case.step.wizard"].create({"case_id": case.id})
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids.label, "رقم القطعة")

        wizard.line_ids.value = "12/34"
        wizard.action_save()
        self.assertEqual(case.capture_values.get("plot_number"), "12/34")
        self.assertTrue(case.ready_to_advance)

    def test_the_step_dialog_refuses_an_unanswered_required_field(self):
        self.env["legal.procedure.field"].create(
            {
                "label": "اسم الموظف المستلم",
                "code": "receiving_officer",
                "step_id": self.step_prepare.id,
                "required": True,
            }
        )
        case = self._make_case()
        wizard = self.env["legal.case.step.wizard"].create({"case_id": case.id})
        with self.assertRaises(UserError):
            wizard.action_save()

    def test_the_step_dialog_can_save_and_advance_in_one_press(self):
        case = self._make_case()
        wizard = self.env["legal.case.step.wizard"].create({"case_id": case.id})
        wizard.note = "سلمنا الملف إلى الشعبة"
        wizard.action_save_and_advance()
        self.assertEqual(case.step_id, self.step_submit)
        self.assertTrue(
            case.log_ids.filtered(lambda entry: entry.description == "سلمنا الملف إلى الشعبة")
        )

    def test_the_return_dialog_demands_a_reason_and_opens_a_round(self):
        case = self._make_case()
        case.action_advance()
        action = case.action_return_for_correction()
        self.assertEqual(action["res_model"], "legal.case.return")

        wizard = self.env["legal.case.return"].create({"case_id": case.id})
        self.assertEqual(wizard.step_id, self.step_prepare)
        with self.assertRaises(UserError):
            wizard.action_confirm()

        wizard.reason = "نقص في المستمسكات"
        wizard.action_confirm()
        self.assertEqual(case.round, 2)
        self.assertEqual(case.step_id, self.step_prepare)
        self.assertTrue(case.sla_paused)

    def test_a_reasoned_move_that_is_not_a_return_does_not_open_a_round(self):
        """require_reason is not the same flag as is_return, and conflating them
        would give a conditional grant a correction round it never had."""
        move = self.env["legal.procedure.transition"].create(
            {
                "name": "قبول مشروط",
                "procedure_type_id": self.procedure.id,
                "from_step_id": self.step_submit.id,
                "to_step_id": self.step_done.id,
                "require_reason": True,
            }
        )
        case = self._make_case()
        case.action_advance()
        # The move ends the procedure, so its confirmation is the approver's;
        # the same confirmation from a clerk is refused server-side.
        refused = (
            self.env["legal.case.return"]
            .with_user(self.clerk)
            .create(
                {
                    "case_id": case.id,
                    "transition_id": move.id,
                    "reason": "محاولة كاتب",
                }
            )
        )
        with self.assertRaises(UserError):
            refused.action_confirm()
        wizard = (
            self.env["legal.case.return"]
            .with_user(self.approver)
            .create(
                {
                    "case_id": case.id,
                    "transition_id": move.id,
                    "reason": "بشرط تقديم الميزانية خلال شهر",
                }
            )
        )
        wizard.action_confirm()
        self.assertEqual(case.round, 1)
        self.assertEqual(case.step_id, self.step_done)
        self.assertEqual(case.outcome, "granted")

    def test_the_return_dialog_marks_the_refused_lines(self):
        self.env["legal.doc.requirement"].create(
            {
                "document_type_id": self.document_type.id,
                "procedure_type_id": self.procedure.id,
            }
        )
        case = self._make_case()
        document = self._register_document()
        case.document_ids.write({"company_document_id": document.id, "accepted": True})
        case.action_advance()
        line = case.document_ids[0]
        wizard = self.env["legal.case.return"].create(
            {
                "case_id": case.id,
                "reason": "الصورة غير مصدقة",
                "document_line_ids": [(6, 0, line.ids)],
            }
        )
        wizard.action_confirm()
        self.assertTrue(line.rejected)
        self.assertEqual(line.rejection_reason, "الصورة غير مصدقة")

    def test_revoking_a_power_of_attorney_needs_a_reason(self):
        agent = self.env["res.partner"].create({"name": "وكيل"})
        poa = self.env["legal.poa"].create(
            {
                "name": "وكالة",
                "entity_id": self.entity.id,
                "agent_partner_id": agent.id,
                "company_id": self.company.id,
                "issue_date": "2026-01-01",
            }
        )
        poa.action_activate()
        wizard = self.env["legal.poa.revoke"].create({"poa_id": poa.id})
        with self.assertRaises(UserError):
            wizard.action_confirm()
        wizard.reason = "انتهاء خدمة الوكيل"
        wizard.action_confirm()
        self.assertEqual(poa.state, "revoked")
        self.assertEqual(poa.revocation_reason, "انتهاء خدمة الوكيل")
