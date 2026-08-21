from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class GovHrDeputationParticipant(models.Model):
    _name = "gov.hr.deputation.participant"
    _description = "Deputation Participant"
    _order = "sequence, id"
    _check_company_auto = True

    deputation_id = fields.Many2one(
        "gov.hr.deputation", required=True, ondelete="cascade", index=True
    )
    case_id = fields.Many2one(
        related="deputation_id.case_id", store=True, index=True
    )
    company_id = fields.Many2one(
        related="deputation_id.company_id", store=True, index=True
    )
    employee_id = fields.Many2one(
        "hr.employee", string="Internal Employee Reference", required=True, ondelete="restrict", check_company=True, index=True
    )
    employee_public_id = fields.Many2one(
        "hr.employee.public",
        string="Employee",
        required=True,
        ondelete="restrict",
        index=True,
    )
    department_id = fields.Many2one(
        "hr.department", string="Department at Submission", ondelete="restrict", check_company=True
    )
    job_id = fields.Many2one(
        "hr.job", string="Job at Submission", ondelete="restrict", check_company=True
    )
    employee_name = fields.Char(required=True)
    department_name = fields.Char()
    job_title = fields.Char()
    employee_identifier = fields.Char()
    role_note = fields.Char()
    sequence = fields.Integer(default=10)

    _unique_employee_deputation = models.Constraint(
        "UNIQUE (deputation_id, employee_id)",
        "An employee can only be added once to the same deputation.",
    )

    @api.model
    def _snapshot_values(self, employee):
        employee = employee.sudo()
        return {
            "department_id": employee.department_id.id,
            "job_id": employee.job_id.id,
            "employee_name": employee.name,
            "department_name": employee.department_id.display_name,
            "job_title": employee.job_title or employee.job_id.name,
            "employee_identifier": employee.barcode,
        }

    @api.onchange("employee_public_id")
    def _onchange_employee_public_id(self):
        if self.employee_public_id:
            employee = self.env["hr.employee"].sudo().browse(self.employee_public_id.id)
            self.update(self._snapshot_values(employee))

    def _check_editable(self):
        for line in self:
            if not line.deputation_id._can_edit_business_data():
                raise AccessError(_("Participants are locked after submission."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            deputation = self.env["gov.hr.deputation"].browse(vals.get("deputation_id"))
            if deputation and not deputation._can_edit_business_data():
                raise AccessError(_("Participants are locked after submission."))
            if vals.get("employee_public_id") and not vals.get("employee_id"):
                vals["employee_id"] = vals["employee_public_id"]
            if vals.get("employee_id") and not vals.get("employee_public_id"):
                vals["employee_public_id"] = vals["employee_id"]
            employee = self.env["hr.employee"].sudo().browse(vals.get("employee_id"))
            if employee:
                vals.update(self._snapshot_values(employee))
        records = super().create(vals_list)
        records.mapped("deputation_id")._sync_participant_users()
        return records

    def write(self, vals):
        self._check_editable()
        if vals.get("employee_public_id"):
            vals["employee_id"] = vals["employee_public_id"]
        if vals.get("employee_id"):
            vals.setdefault("employee_public_id", vals["employee_id"])
            vals = dict(vals, **self._snapshot_values(self.env["hr.employee"].sudo().browse(vals["employee_id"])))
        result = super().write(vals)
        self.mapped("deputation_id")._sync_participant_users()
        return result

    def unlink(self):
        deputations = self.mapped("deputation_id")
        self._check_editable()
        result = super().unlink()
        deputations._sync_participant_users()
        return result

    @api.constrains("employee_id", "employee_public_id", "company_id")
    def _check_employee_company(self):
        for line in self:
            if line.employee_id.company_id != line.company_id:
                raise ValidationError(_("Every participant must belong to the deputation company."))
            if line.employee_id.id != line.employee_public_id.id:
                raise ValidationError(_("The public and internal employee references must identify the same employee."))
