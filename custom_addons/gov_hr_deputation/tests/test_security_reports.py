from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import DeputationCommon, PNG_1X1


@tagged("post_install", "-at_install")
class TestDeputationSecurityReports(DeputationCommon):
    def test_new_requester_form_is_editable(self):
        case_model = self.env["gov.hr.case"].with_user(self.requester_user)
        defaults = case_model.default_get(
            [
                "state",
                "requester_employee_id",
                "company_id",
                "can_edit_business",
                "can_edit_basis",
                "can_current_user_resubmit",
            ]
        )
        self.assertEqual(
            defaults["requester_employee_id"], self.requester_employee.id
        )

        draft = case_model.new(defaults)
        self.assertTrue(draft.can_edit_business)
        self.assertTrue(draft.can_edit_basis)
        self.assertTrue(draft.can_current_user_resubmit)

        form_view = self.env["gov.hr.deputation"].with_user(
            self.requester_user
        ).get_view(
            view_id=self.env.ref(
                "gov_hr_deputation.view_gov_hr_deputation_form"
            ).id,
            view_type="form",
        )
        self.assertIn('name="requester_employee_id"', form_view["arch"])
        self.assertIn('name="company_id" invisible="1"', form_view["arch"])

    def test_draft_has_no_stamp_final_is_guarded_and_cached(self):
        deputation = self._create_deputation()
        draft_report = self.env.ref(
            "gov_hr_deputation.action_report_deputation_mission_order_draft"
        )
        draft_html, _mime = draft_report._render_qweb_html(draft_report.id, [deputation.id])
        self.assertIn("مسودة".encode(), draft_html)
        self.assertNotIn("الختم الرسمي".encode(), draft_html)

        final_report = self.env.ref(
            "gov_hr_deputation.action_report_deputation_mission_order_final"
        )
        with self.assertRaises(AccessError):
            final_report._render_qweb_pdf(final_report.id, [deputation.id])

        self._reach_issuance(deputation)
        deputation.with_user(self.officer_user).write(
            {"outgoing_number": "OUT-900", "outgoing_date": fields.Date.today()}
        )
        deputation.with_user(self.officer_user).action_issue()
        attachment = deputation.final_order_attachment_id
        original_pdf = attachment.raw

        self.company.write({"gov_hr_official_stamp": b"bmV3LXN0YW1w"})
        rerendered_pdf, _mime = final_report.with_context(force_report_rendering=True)._render_qweb_pdf(
            final_report.id, [deputation.id]
        )
        self.assertEqual(original_pdf, attachment.raw)
        self.assertEqual(original_pdf, rerendered_pdf)
        self.assertEqual(
            final_report.retrieve_attachment(deputation), attachment
        )
        with self.assertRaises(AccessError):
            attachment.with_user(self.officer_user).write({"name": "tampered.pdf"})
        with self.assertRaises(AccessError):
            attachment.with_user(self.officer_user).unlink()
        self.assertTrue(attachment.exists())

    def test_participant_visibility_starts_only_after_issuance(self):
        deputation = self._create_deputation()
        participant_model = self.env["gov.hr.deputation"].with_user(self.participant_user)
        self.assertFalse(participant_model.search([("id", "=", deputation.id)]))

        self._reach_issuance(deputation)
        deputation.with_user(self.officer_user).write(
            {"outgoing_number": "OUT-PARTICIPANT", "outgoing_date": fields.Date.today()}
        )
        deputation.with_user(self.officer_user).action_issue()
        self.assertEqual(
            participant_model.search([("id", "=", deputation.id)]), deputation
        )

    def test_multi_company_visibility(self):
        visible = self._create_deputation()
        other_company = self.env["res.company"].create({"name": "Other Government Entity"})
        other_user = self._make_user("other.requester", self.group_user, other_company)
        other_employee = self._make_employee("Other Requester", other_user, other_company)
        other_manager_user = self._make_user("other.manager", None, other_company)
        other_manager = self._make_employee("Other Manager", other_manager_user, other_company)
        other_department = self.env["hr.department"].create(
            {"name": "Other Department", "company_id": other_company.id, "manager_id": other_manager.id}
        )
        other_officer_user = self._make_user("other.officer", self.group_officer, other_company)
        other_officer = self._make_employee("Other Officer", other_officer_user, other_company)
        other_admin_user = self._make_user("other.admin.manager", self.group_admin_manager, other_company)
        other_admin = self._make_employee("Other Admin Manager", other_admin_user, other_company)
        other_admin_department = self.env["hr.department"].create(
            {"name": "Other Administration", "company_id": other_company.id, "manager_id": other_admin.id}
        )
        other_dg = self._make_user("other.dg", self.group_dg, other_company)
        other_company.write(
            {
                "gov_hr_administrative_department_id": other_admin_department.id,
                "gov_hr_director_general_user_id": other_dg.id,
                "gov_hr_default_administrative_officer_id": other_officer.id,
                "gov_hr_official_stamp": PNG_1X1,
            }
        )
        other_activity_type = self.env["gov.hr.deputation.activity.type"].create(
            {"name": "Other Official Mission", "code": "official_mission", "company_id": other_company.id}
        )
        other_basis_type = self.env["gov.hr.basis.type"].create(
            {"name": "Other Work Order", "code": "work_order", "company_id": other_company.id}
        )
        other = self.env["gov.hr.deputation"].sudo().create(
            {
                "subject": "Other-company mission",
                "requester_employee_id": other_employee.id,
                "department_id": other_department.id,
                "company_id": other_company.id,
                "administrative_officer_id": other_officer.id,
                "deputation_activity_type_id": other_activity_type.id,
                "activity_description": "Other company",
                "destination": "Najaf",
                "date_from": fields.Date.today(),
                "date_to": fields.Date.today(),
                "participant_ids": [Command.create({"employee_id": other_employee.id, "employee_public_id": other_employee.id})],
                "basis_line_ids": [Command.create({"type_id": other_basis_type.id, "required": True, "file_data": b"ZmlsZQ==", "filename": "x.pdf"})],
            }
        )
        visible_ids = self.env["gov.hr.deputation"].with_user(self.requester_user).search([]).ids
        self.assertIn(visible.id, visible_ids)
        self.assertNotIn(other.id, visible_ids)
