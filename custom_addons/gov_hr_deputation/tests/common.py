import base64

from odoo import Command, fields
from odoo.tests import TransactionCase


PNG_1X1 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDAT\x08\xd7c\xf8\xcf\xc0\xf0\x1f\x00\x05\x00\x01\xff\x89\x99=\x1d\x00\x00\x00\x00IEND\xaeB`\x82"
)


class DeputationCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group_user = cls.env.ref("gov_hr_base.group_gov_hr_user")
        cls.group_officer = cls.env.ref("gov_hr_base.group_gov_hr_admin_officer")
        cls.group_admin_manager = cls.env.ref("gov_hr_base.group_gov_hr_admin_manager")
        cls.group_dg = cls.env.ref("gov_hr_base.group_gov_hr_director_general")
        cls.group_manager = cls.env.ref("gov_hr_base.group_gov_hr_manager")

        cls.requester_user = cls._make_user("requester", cls.group_user)
        cls.dept_manager_user = cls._make_user("dept.manager")
        cls.officer_user = cls._make_user("admin.officer", cls.group_officer)
        cls.admin_manager_user = cls._make_user("admin.manager", cls.group_admin_manager)
        cls.dg_user = cls._make_user("director.general", cls.group_dg)
        cls.config_manager_user = cls._make_user("gov.hr.manager", cls.group_manager)
        cls.participant_user = cls._make_user("participant")

        cls.requester_employee = cls._make_employee("Requester", cls.requester_user)
        cls.dept_manager_employee = cls._make_employee("Department Manager", cls.dept_manager_user)
        cls.officer_employee = cls._make_employee("Administrative Officer", cls.officer_user)
        cls.admin_manager_employee = cls._make_employee("Administrative Manager", cls.admin_manager_user)
        cls.dg_employee = cls._make_employee("Director General", cls.dg_user)
        cls.participant_employee = cls._make_employee("Participant Employee", cls.participant_user)

        cls.department = cls.env["hr.department"].create(
            {
                "name": "Information Department",
                "company_id": cls.company.id,
                "manager_id": cls.dept_manager_employee.id,
            }
        )
        cls.admin_department = cls.env["hr.department"].create(
            {
                "name": "Administrative Department",
                "company_id": cls.company.id,
                "manager_id": cls.admin_manager_employee.id,
            }
        )
        (cls.requester_employee | cls.participant_employee).write(
            {"department_id": cls.department.id}
        )
        (cls.officer_employee | cls.admin_manager_employee).write(
            {"department_id": cls.admin_department.id}
        )
        cls.company.write(
            {
                "gov_hr_administrative_department_id": cls.admin_department.id,
                "gov_hr_director_general_user_id": cls.dg_user.id,
                "gov_hr_default_administrative_officer_id": cls.officer_employee.id,
                "gov_hr_official_stamp": PNG_1X1,
                "gov_hr_official_stamp_filename": "stamp.png",
            }
        )
        cls.activity_type = cls.env.ref(
            "gov_hr_deputation.activity_type_official_mission"
        )
        cls.work_order_type = cls.env.ref(
            "gov_hr_deputation.basis_type_work_order"
        )

    @classmethod
    def _make_user(cls, login, group=None, company=None):
        company = company or cls.env.company
        groups = [cls.env.ref("base.group_user").id]
        if group:
            groups.append(group.id)
        return cls.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": login.replace(".", " ").title(),
                "login": "%s@gov.test" % login,
                "email": "%s@gov.test" % login,
                "company_id": company.id,
                "company_ids": [Command.set([company.id])],
                "group_ids": [Command.set(groups)],
            }
        )

    @classmethod
    def _make_employee(cls, name, user, company=None):
        return cls.env["hr.employee"].create(
            {
                "name": name,
                "user_id": user.id,
                "company_id": (company or cls.env.company).id,
                "job_title": "Engineer",
            }
        )

    def _create_deputation(self, user=None, company=None, department=None, officer=None):
        user = user or self.requester_user
        company = company or self.company
        department = department or self.department
        officer = officer or self.officer_employee
        requester = user.employee_ids.filtered(lambda employee: employee.company_id == company)[:1]
        participant = (
            self.participant_employee
            if company == self.company
            else requester
        )
        return self.env["gov.hr.deputation"].with_user(user).create(
            {
                "subject": "Official technical mission",
                "requester_employee_id": requester.id,
                "department_id": department.id,
                "company_id": company.id,
                "administrative_officer_id": officer.id,
                "deputation_activity_type_id": self.activity_type.id,
                "activity_description": "Review the government information system",
                "destination": "Basra",
                "date_from": fields.Date.today(),
                "date_to": fields.Date.add(fields.Date.today(), days=3),
                "participant_ids": [
                    Command.create(
                        {
                            "employee_public_id": participant.id,
                            "employee_id": participant.id,
                            "role_note": "Team member",
                        }
                    )
                ],
                "basis_line_ids": [
                    Command.create(
                        {
                            "type_id": self.work_order_type.id,
                            "reference_number": "WO-125",
                            "reference_date": fields.Date.today(),
                            "required": True,
                            "file_data": base64.b64encode(b"test supporting document"),
                            "filename": "work-order.pdf",
                        }
                    )
                ],
            }
        )

    def _reach_document_review(self, deputation):
        deputation.with_user(self.requester_user).action_submit()
        deputation.with_user(self.dept_manager_user).action_approve()
        deputation.with_user(self.dg_user).action_approve()
        deputation.with_user(self.admin_manager_user).action_approve()
        self.assertEqual(deputation.state, "document_review")

    def _reach_issuance(self, deputation):
        self._reach_document_review(deputation)
        basis = deputation.basis_line_ids
        basis.with_user(self.officer_user).write({"verification_status": "verified"})
        deputation.with_user(self.officer_user).action_verify_documents()
        deputation.with_user(self.officer_user).action_prepare_mission_order()
        deputation.with_user(self.admin_manager_user).action_approve()
        deputation.with_user(self.dg_user).action_approve()
        self.assertEqual(deputation.state, "awaiting_outgoing")
