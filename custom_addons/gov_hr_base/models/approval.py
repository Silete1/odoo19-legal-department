from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class GovHrCaseType(models.Model):
    _name = "gov.hr.case.type"
    _description = "Government HR Case Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    route_id = fields.Many2one(
        "gov.hr.approval.route", required=True, ondelete="restrict"
    )
    sequence_code = fields.Char(
        required=True,
        help="Technical ir.sequence code used for the internal case reference.",
    )

    _unique_code = models.Constraint(
        "UNIQUE (code)", "Government case type codes must be unique."
    )


class GovHrApprovalRoute(models.Model):
    _name = "gov.hr.approval.route"
    _description = "Government HR Approval Route"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    step_ids = fields.One2many(
        "gov.hr.approval.step", "route_id", string="Approval Steps", copy=True
    )


class GovHrApprovalStep(models.Model):
    _name = "gov.hr.approval.step"
    _description = "Government HR Approval Step"
    _order = "phase, sequence, id"

    name = fields.Char(required=True, translate=True)
    route_id = fields.Many2one(
        "gov.hr.approval.route", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="route_id.company_id", store=True, index=True)
    phase = fields.Selection(
        [
            ("memo", "Memorandum"),
            ("mission", "Mission Order"),
            ("issuance", "Issuance"),
        ],
        required=True,
        index=True,
    )
    sequence = fields.Integer(required=True, default=10)
    step_kind = fields.Selection(
        [
            ("approval", "Approval"),
            ("document_review", "Document Review"),
            ("issuance", "Issuance"),
        ],
        required=True,
        default="approval",
    )
    role_code = fields.Selection(
        [
            ("concerned_department_manager", "Concerned Department Manager"),
            ("administrative_department_manager", "Administrative Department Manager"),
            ("director_general", "Director General"),
            ("assigned_administrative_officer", "Assigned Administrative Officer"),
            ("specific_user", "Specific User"),
            ("security_group", "Security Group"),
        ],
        required=True,
    )
    specific_user_id = fields.Many2one("res.users", ondelete="restrict")
    group_id = fields.Many2one("res.groups", ondelete="restrict")
    activity_summary = fields.Char(translate=True)
    active = fields.Boolean(default=True)

    _unique_route_phase_sequence = models.Constraint(
        "UNIQUE (route_id, phase, sequence)",
        "Approval step sequence must be unique within each route phase.",
    )

    @api.constrains("role_code", "specific_user_id", "group_id")
    def _check_role_configuration(self):
        for step in self:
            if step.role_code == "specific_user" and not step.specific_user_id:
                raise ValidationError(_("A specific user is required for this approval step."))
            if step.role_code == "security_group" and not step.group_id:
                raise ValidationError(_("A security group is required for this approval step."))


class GovHrApprovalLog(models.Model):
    _name = "gov.hr.approval.log"
    _description = "Government HR Approval Log"
    _order = "decision_at desc, id desc"

    case_id = fields.Many2one(
        "gov.hr.case", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="case_id.company_id", store=True, index=True)
    phase = fields.Selection(
        [("memo", "Memorandum"), ("mission", "Mission Order"), ("issuance", "Issuance")],
        required=True,
        index=True,
    )
    step_id = fields.Many2one("gov.hr.approval.step", ondelete="restrict", index=True)
    step_name = fields.Char(required=True)
    sequence = fields.Integer()
    round_number = fields.Integer(required=True, index=True)
    approver_user_id = fields.Many2one("res.users", required=True, ondelete="restrict")
    approver_employee_id = fields.Many2one("hr.employee", ondelete="restrict")
    action = fields.Selection(
        [
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("returned", "Returned for Correction"),
            ("rejected", "Rejected"),
            ("restarted", "Resubmitted"),
            ("documents_verified", "Documents Verified"),
            ("mission_order_prepared", "Mission Order Prepared"),
            ("issued", "Issued"),
        ],
        required=True,
        index=True,
    )
    decision_at = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    reason = fields.Text()
    previous_state = fields.Char()
    new_state = fields.Char()
    is_superseded = fields.Boolean(compute="_compute_is_superseded")

    @api.depends("round_number", "case_id.round_number")
    def _compute_is_superseded(self):
        for log in self:
            log.is_superseded = log.round_number < log.case_id.round_number

    def write(self, vals):
        raise AccessError(_("Approval history is immutable and cannot be changed."))

    def unlink(self):
        raise AccessError(_("Approval history is immutable and cannot be deleted."))
