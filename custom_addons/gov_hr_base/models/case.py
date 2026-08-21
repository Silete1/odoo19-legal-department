from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


CASE_STATES = [
    ("draft", "Draft"),
    ("initial_approvals", "Initial Approvals"),
    ("document_review", "Document Review"),
    ("mission_preparation", "Mission Order Preparation"),
    ("final_approvals", "Final Approvals"),
    ("awaiting_outgoing", "Awaiting Outgoing Registration"),
    ("done", "Completed"),
    ("returned", "Returned for Correction"),
    ("rejected", "Rejected"),
]


class GovHrCase(models.Model):
    _name = "gov.hr.case"
    _description = "Government HR Administrative Case"
    _order = "create_date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Case Reference", required=True, default="New", copy=False, index="btree"
    )
    case_type_id = fields.Many2one(
        "gov.hr.case.type", required=True, ondelete="restrict", index=True
    )
    subject = fields.Char(required=True)
    requester_employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        check_company=True,
        ondelete="restrict",
        default=lambda self: self.env.user.employee_id,
        index=True,
    )
    requester_user_id = fields.Many2one(
        "res.users",
        string="Requester User",
        related="requester_employee_id.user_id",
        store=True,
        index=True,
    )
    department_id = fields.Many2one(
        "hr.department", required=True, check_company=True, ondelete="restrict", index=True
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        ondelete="restrict",
    )
    administrative_officer_id = fields.Many2one(
        "hr.employee", check_company=True, ondelete="restrict", index=True
    )
    administrative_officer_user_id = fields.Many2one(
        "res.users", string="Administrative Officer User", related="administrative_officer_id.user_id", store=True, index=True
    )
    participant_user_ids = fields.Many2many(
        "res.users",
        "gov_hr_case_participant_user_rel",
        "case_id",
        "user_id",
        string="Participant Users",
        copy=False,
    )
    state = fields.Selection(
        CASE_STATES, required=True, default="draft", copy=False, index=True
    )
    phase = fields.Selection(
        [("memo", "Memorandum"), ("mission", "Mission Order"), ("issuance", "Issuance")],
        default="memo",
        required=True,
        copy=False,
        index=True,
    )
    current_step_id = fields.Many2one(
        "gov.hr.approval.step", copy=False, ondelete="restrict", index=True
    )
    current_stage_name = fields.Char(related="current_step_id.name")
    current_step_kind = fields.Selection(related="current_step_id.step_kind")
    current_step_role_code = fields.Selection(related="current_step_id.role_code")
    current_approver_user_id = fields.Many2one(
        "res.users", copy=False, ondelete="restrict", index=True
    )
    current_activity_id = fields.Many2one(
        "mail.activity", copy=False, ondelete="set null"
    )
    correction_user_id = fields.Many2one(
        "res.users", copy=False, ondelete="restrict", index=True
    )
    returned_from_phase = fields.Selection(
        [("memo", "Memorandum"), ("mission", "Mission Order"), ("issuance", "Issuance")],
        copy=False,
    )
    returned_from_step_id = fields.Many2one(
        "gov.hr.approval.step", copy=False, ondelete="restrict"
    )
    round_number = fields.Integer(default=0, required=True, copy=False, index=True)
    basis_line_ids = fields.One2many(
        "gov.hr.case.basis", "case_id", string="Supporting Documents", copy=True
    )
    approval_log_ids = fields.One2many(
        "gov.hr.approval.log", "case_id", string="Approval History", copy=False
    )
    outgoing_number = fields.Char(copy=False, index="btree")
    outgoing_date = fields.Date(copy=False, index=True)
    submitted_at = fields.Datetime(copy=False)
    memo_completed_at = fields.Datetime(copy=False)
    mission_order_approved_at = fields.Datetime(copy=False)
    issued_at = fields.Datetime(copy=False)
    completed_at = fields.Datetime(copy=False)
    processing_duration_hours = fields.Float(copy=False, readonly=True, aggregator="avg")
    final_dg_approval_log_id = fields.Many2one(
        "gov.hr.approval.log", copy=False, ondelete="restrict"
    )
    memorandum_attachment_id = fields.Many2one(
        "ir.attachment", copy=False, ondelete="restrict"
    )
    final_order_attachment_id = fields.Many2one(
        "ir.attachment", copy=False, ondelete="restrict"
    )
    business_model = fields.Char(copy=False, index=True)
    business_res_id = fields.Integer(copy=False, index=True)
    workflow_display = fields.Json(compute="_compute_workflow_display")
    task_title = fields.Char(compute="_compute_user_context_fields")
    task_instruction = fields.Char(compute="_compute_user_context_fields")
    can_current_user_act = fields.Boolean(compute="_compute_user_context_fields")
    can_current_user_resubmit = fields.Boolean(compute="_compute_user_context_fields")
    can_edit_business = fields.Boolean(compute="_compute_user_context_fields")
    can_edit_basis = fields.Boolean(compute="_compute_user_context_fields")
    can_manage_configuration = fields.Boolean(compute="_compute_user_context_fields")
    has_official_stamp = fields.Boolean(compute="_compute_has_official_stamp", compute_sudo=True)

    _unique_outgoing_company = models.Constraint(
        "UNIQUE (company_id, outgoing_number)",
        "The outgoing number must be unique within the company.",
    )
    _business_reference_index = models.Index("(business_model, business_res_id)")

    _workflow_fields = {
        "state",
        "phase",
        "current_step_id",
        "current_approver_user_id",
        "current_activity_id",
        "correction_user_id",
        "returned_from_phase",
        "returned_from_step_id",
        "round_number",
        "submitted_at",
        "memo_completed_at",
        "mission_order_approved_at",
        "issued_at",
        "completed_at",
        "processing_duration_hours",
        "final_dg_approval_log_id",
        "memorandum_attachment_id",
        "final_order_attachment_id",
        "business_model",
        "business_res_id",
        "participant_user_ids",
    }
    _issuance_fields = {"outgoing_number", "outgoing_date"}
    _business_fields = {
        "subject",
        "requester_employee_id",
        "department_id",
        "company_id",
        "administrative_officer_id",
        "basis_line_ids",
    }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(
                vals.get("company_id") or self.env.company.id
            )
            if not self.env.su and company not in self.env.companies:
                raise AccessError(_("You cannot create a case for a company outside your allowed companies."))
            requester = self.env["hr.employee"].browse(
                vals.get("requester_employee_id") or self.env.user.employee_id.id
            )
            if (
                not self.env.su
                and not self.env.user.has_group("gov_hr_base.group_gov_hr_manager")
                and requester.user_id != self.env.user
            ):
                raise AccessError(_("You can only create a government case for your own employee record."))
            if vals.get("name", "New") == "New":
                case_type = self.env["gov.hr.case.type"].browse(vals.get("case_type_id"))
                vals["name"] = (
                    self.env["ir.sequence"].with_company(company).next_by_code(case_type.sequence_code)
                    if case_type
                    else False
                ) or _("New")
            default_officer_id = company.gov_hr_default_administrative_officer_id.id
            if self.env.su or self.env.user.has_group(
                "gov_hr_base.group_gov_hr_admin_manager"
            ):
                vals.setdefault("administrative_officer_id", default_officer_id)
            else:
                vals["administrative_officer_id"] = default_officer_id
        return super().create(vals_list)

    def write(self, vals):
        reassigned_cases = self.env["gov.hr.case"]
        if not self.env.su:
            if set(vals) & self._workflow_fields:
                raise AccessError(_("Workflow fields can only be changed by protected case actions."))
            for case in self:
                if set(vals) & self._issuance_fields:
                    if case.state != "awaiting_outgoing" or not case._is_assigned_administrative_officer():
                        raise AccessError(_("Only the assigned administrative officer can enter outgoing information at the issuance stage."))
                if set(vals) & self._business_fields:
                    officer_assignment_only = set(vals) <= {"administrative_officer_id"}
                    if officer_assignment_only and vals.get("administrative_officer_id") != case.administrative_officer_id.id:
                        if not self.env.user.has_group(
                            "gov_hr_base.group_gov_hr_admin_manager"
                        ) or case.state in ("done", "rejected"):
                            raise AccessError(_("Only the Administrative Department Manager can reassign an active case."))
                        officer = self.env["hr.employee"].browse(vals["administrative_officer_id"])
                        officer_group = self.env.ref("gov_hr_base.group_gov_hr_admin_officer")
                        if (
                            not officer
                            or officer.company_id != case.company_id
                            or not officer.user_id.active
                            or officer.user_id.share
                            or officer_group not in officer.user_id.all_group_ids
                        ):
                            raise ValidationError(
                                _("The reassigned employee must be an active internal user with the Administrative Officer role in this company.")
                            )
                        reassigned_cases |= case
                        continue
                    if not case._can_edit_business_data():
                        raise AccessError(_("The substantive case information is locked at this stage."))
        result = super().write(vals)
        for case in reassigned_cases:
            if (
                case.current_step_id.role_code == "assigned_administrative_officer"
                and case.business_model
                and case.business_res_id
            ):
                business_record = self.env[case.business_model].browse(case.business_res_id)
                business_record._complete_activity()
                business_record._enter_step(case.current_step_id)
        return result

    def unlink(self):
        for case in self:
            if case.state != "draft":
                raise AccessError(_("Submitted or completed government cases cannot be deleted."))
            if not self.env.su and not (
                case.requester_user_id == self.env.user
                or self.env.user.has_group("gov_hr_base.group_gov_hr_manager")
            ):
                raise AccessError(_("Only the requester can delete this draft case."))
        return super().unlink()

    def _can_edit_business_data(self):
        self.ensure_one()
        if self.env.su:
            return True
        if self.state == "draft":
            # The delegated case does not have a database identity during the
            # first form onchange.  Allow the current employee to fill that
            # unsaved draft; create() still enforces requester ownership.
            return self.requester_user_id == self.env.user or bool(
                not self._origin.id
                and not self.requester_user_id
                and self.env.user.employee_id
            )
        if self.state == "returned":
            return self.returned_from_phase == "memo" and self.correction_user_id == self.env.user
        return False

    def _is_assigned_administrative_officer(self):
        self.ensure_one()
        return bool(
            self.administrative_officer_user_id
            and self.administrative_officer_user_id == self.env.user
            and self.administrative_officer_id.company_id == self.company_id
        )

    @api.depends_context("uid", "allowed_company_ids")
    @api.depends(
        "state",
        "requester_employee_id",
        "requester_user_id",
        "company_id",
        "current_step_id",
        "current_approver_user_id",
        "correction_user_id",
        "administrative_officer_user_id",
    )
    def _compute_user_context_fields(self):
        labels = dict(CASE_STATES)
        for case in self:
            case.can_current_user_act = bool(
                case.current_approver_user_id == self.env.user
                and case.company_id in self.env.companies
            )
            case.can_current_user_resubmit = bool(
                case.company_id in self.env.companies
                and (
                    (case.state == "draft" and case._can_edit_business_data())
                    or (case.state == "returned" and case.correction_user_id == self.env.user)
                )
            )
            case.can_edit_business = case._can_edit_business_data()
            case.can_edit_basis = case.can_edit_business or bool(
                case.state == "document_review"
                and case.current_approver_user_id == self.env.user
                and case.current_step_id.step_kind == "document_review"
            )
            case.can_manage_configuration = self.env.user.has_group(
                "gov_hr_base.group_gov_hr_manager"
            )
            case.task_title = _("What you need to do now")
            if case.state == "draft":
                case.task_instruction = _("Complete the deputation information and send it for approval.")
            elif case.state == "returned":
                case.task_instruction = _("Correct the request according to the recorded return reason, then resubmit it.")
            elif case.current_step_id and case.current_approver_user_id == self.env.user:
                case.task_instruction = case.current_step_id.activity_summary or _(
                    "Review the case and complete the action assigned to you."
                )
            elif case.state == "done":
                case.task_instruction = _("This case is complete and its official document is archived.")
            else:
                case.task_instruction = _("Current status: %(status)s", status=labels.get(case.state, case.state))

    @api.depends("company_id.gov_hr_official_stamp")
    def _compute_has_official_stamp(self):
        for case in self:
            # The image itself is restricted to configuration managers.  Other
            # workflow roles may only learn whether configuration is complete.
            case.has_official_stamp = bool(case.company_id.sudo().gov_hr_official_stamp)

    @api.depends(
        "case_type_id.route_id.step_ids",
        "current_step_id",
        "round_number",
        "approval_log_ids.action",
        "approval_log_ids.decision_at",
        "approval_log_ids.reason",
        "approval_log_ids.round_number",
    )
    def _compute_workflow_display(self):
        completed_actions = {"approved", "mission_order_prepared", "issued"}
        for case in self:
            logs_by_step = {}
            for log in case.approval_log_ids.filtered(
                lambda item: item.round_number == case.round_number
            ).sorted("decision_at"):
                if log.step_id:
                    logs_by_step[log.step_id.id] = log
            steps = []
            for step in case.case_type_id.route_id.step_ids.filtered("active").sorted(
                key=lambda s: ({"memo": 1, "mission": 2, "issuance": 3}[s.phase], s.sequence)
            ):
                log = logs_by_step.get(step.id)
                status = "pending"
                if log and log.action in completed_actions:
                    status = "completed"
                if case.current_step_id == step:
                    status = "current"
                if log and log.action == "returned" and log.round_number == case.round_number:
                    status = "returned"
                steps.append(
                    {
                        "id": step.id,
                        "label": step.name,
                        "phase": step.phase,
                        "status": status,
                        "approver": log.approver_user_id.name if log else False,
                        "date": fields.Datetime.to_string(log.decision_at) if log else False,
                        "round": log.round_number if log else case.round_number,
                        "reason": log.reason if log else False,
                    }
                )
            case.workflow_display = {"rtl": True, "steps": steps}


class GovHrCaseWorkflowMixin(models.AbstractModel):
    _name = "gov.hr.case.workflow.mixin"
    _description = "Government HR Case Workflow Mixin"

    def _get_case(self):
        self.ensure_one()
        return self.case_id

    def _can_edit_business_data(self):
        self.ensure_one()
        return self.case_id._can_edit_business_data()

    def _is_assigned_administrative_officer(self):
        self.ensure_one()
        return self.case_id._is_assigned_administrative_officer()

    def _validate_submission(self):
        return True

    def _validate_resubmission(self):
        return self._validate_submission()

    def _check_company_access(self):
        for record in self:
            if record.company_id not in self.env.companies:
                raise AccessError(_("You cannot process a case outside your allowed companies."))

    def _route_steps(self, phase):
        self.ensure_one()
        return self.case_type_id.route_id.step_ids.filtered(
            lambda step: step.active and step.phase == phase
        ).sorted("sequence")

    def _resolve_step_user(self, step):
        self.ensure_one()
        company = self.company_id
        employee = self.env["hr.employee"]
        user = self.env["res.users"]
        if step.role_code == "concerned_department_manager":
            employee = self.department_id.manager_id
            user = employee.user_id
            message = _("The concerned department '%(department)s' must have a manager linked to an active Odoo user.", department=self.department_id.display_name)
        elif step.role_code == "administrative_department_manager":
            department = company.gov_hr_administrative_department_id
            employee = department.manager_id
            user = employee.user_id
            message = _("Configure an Administrative Department whose manager is linked to an active Odoo user.")
        elif step.role_code == "director_general":
            user = company.gov_hr_director_general_user_id
            employee = user.employee_id
            message = _("Configure an active Director General user in the company settings.")
        elif step.role_code == "assigned_administrative_officer":
            employee = self.administrative_officer_id
            user = employee.user_id
            message = _("Assign an administrative officer linked to an active Odoo user.")
        elif step.role_code == "specific_user":
            user = step.specific_user_id
            employee = user.employee_id
            message = _("Configure an active specific user for the approval step '%(step)s'.", step=step.name)
        else:
            candidates = step.group_id.all_user_ids.filtered(
                lambda candidate: candidate.active
                and not candidate.share
                and company in candidate.company_ids
            ).sorted("id")
            user = step.specific_user_id or candidates[:1]
            employee = user.employee_id
            message = _("The approval group for '%(step)s' has no active internal user in this company.", step=step.name)
        if not user or not user.active or user.share or company not in user.company_ids:
            raise ValidationError(message)
        return user, employee

    def _is_authorized_for_step(self, step):
        self.ensure_one()
        if not step or self.current_step_id != step:
            return False
        resolved_user, _employee = self._resolve_step_user(step)
        return resolved_user == self.env.user and self.current_approver_user_id == self.env.user

    def _check_current_actor(self, expected_kind=None):
        self.ensure_one()
        self._check_company_access()
        step = self.current_step_id
        if not step or not self._is_authorized_for_step(step):
            raise AccessError(_("You are not the authorized user for the active approval step."))
        if expected_kind and step.step_kind != expected_kind:
            raise UserError(_("This action is not valid for the active workflow step."))
        return step

    def _complete_activity(self):
        self.ensure_one()
        activity = self.current_activity_id.sudo()
        if activity and activity.exists() and activity.active:
            activity.action_feedback(feedback=_("Workflow action completed."))
        self.case_id.sudo().write({"current_activity_id": False})

    def _activity_summary(self, step):
        return step.activity_summary or _("Review government case %(reference)s", reference=self.name)

    def _state_for_step(self, step):
        if step.phase == "memo" and step.step_kind == "approval":
            return "initial_approvals"
        if step.step_kind == "document_review":
            return "document_review"
        if step.phase == "mission":
            return "final_approvals"
        if step.phase == "issuance":
            return "awaiting_outgoing"
        return self.state

    def _enter_step(self, step):
        self.ensure_one()
        user, _employee = self._resolve_step_user(step)
        self.case_id.sudo().write(
            {
                "state": self._state_for_step(step),
                "phase": step.phase,
                "current_step_id": step.id,
                "current_approver_user_id": user.id,
                "correction_user_id": False,
            }
        )
        existing = self.sudo().activity_ids.filtered(
            lambda activity: activity.active
            and activity.activity_type_id == self.env.ref("gov_hr_base.mail_activity_type_gov_hr_approval")
            and activity.user_id == user
            and activity.summary == self._activity_summary(step)
        )
        activity = existing[:1]
        if not activity:
            activity = self.sudo().activity_schedule(
                "gov_hr_base.mail_activity_type_gov_hr_approval",
                user_id=user.id,
                summary=self._activity_summary(step),
                note=_("Government case %(reference)s is waiting for your action at: %(step)s", reference=self.name, step=step.name),
            )
        self.case_id.sudo().write({"current_activity_id": activity.id})
        self.message_post(
            body=Markup("<p>%s</p>")
            % _("The case was routed to %(user)s for %(step)s.", user=user.name, step=step.name)
        )
        return user

    def _log_action(self, action, step=None, reason=None, previous_state=None, new_state=None):
        self.ensure_one()
        step = step or self.current_step_id
        employee = self.env.user.employee_ids.filtered(
            lambda item: item.company_id == self.company_id
        )[:1]
        return self.env["gov.hr.approval.log"].sudo().create(
            {
                "case_id": self.case_id.id,
                "phase": step.phase if step else self.phase,
                "step_id": step.id if step else False,
                "step_name": step.name if step else _("Submission"),
                "sequence": step.sequence if step else 0,
                "round_number": self.round_number,
                "approver_user_id": self.env.user.id,
                "approver_employee_id": employee.id,
                "action": action,
                "reason": reason,
                "previous_state": previous_state or self.state,
                "new_state": new_state or self.state,
            }
        )

    def _notification(self, message, notification_type="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Government HR"), "message": message, "type": notification_type, "sticky": False},
        }

    def action_submit(self):
        self.ensure_one()
        self._check_company_access()
        if self.state not in ("draft", "returned"):
            raise UserError(_("Only a draft or returned case can be submitted."))
        if self.state == "draft" and self.requester_user_id != self.env.user:
            raise AccessError(_("Only the requester can submit this draft."))
        if self.state == "returned" and self.correction_user_id != self.env.user:
            raise AccessError(_("Only the assigned correction user can resubmit this case."))
        if not self.case_type_id.route_id or not self.case_type_id.route_id.active:
            raise ValidationError(_("No active approval route is configured for this case type."))
        was_returned = self.state == "returned"
        returned_phase = self.returned_from_phase
        if was_returned:
            self._validate_resubmission()
            self._complete_activity()
        else:
            self._validate_submission()
        next_round = self.round_number + 1
        now = fields.Datetime.now()
        start_phase = "mission" if was_returned and returned_phase in ("mission", "issuance") else "memo"
        self.case_id.sudo().write(
            {
                "round_number": next_round,
                "submitted_at": self.submitted_at or now,
                "state": "mission_preparation" if start_phase == "mission" else "initial_approvals",
                "phase": start_phase,
                "returned_from_phase": False,
                "returned_from_step_id": False,
            }
        )
        self._log_action("restarted" if was_returned else "submitted", new_state=self.state)
        first_step = self._route_steps(start_phase)[:1]
        if not first_step:
            raise ValidationError(_("The approval route has no active step for phase '%(phase)s'.", phase=start_phase))
        user = self._enter_step(first_step)
        return self._notification(_("The case was sent to %(user)s.", user=user.name))

    def _next_step_in_phase(self, step):
        return self._route_steps(step.phase).filtered(lambda candidate: candidate.sequence > step.sequence)[:1]

    def action_approve(self):
        self.ensure_one()
        step = self._check_current_actor("approval")
        previous_state = self.state
        self._complete_activity()
        log = self._log_action("approved", step=step, previous_state=previous_state)
        if step.phase == "mission" and step.role_code == "director_general":
            self.case_id.sudo().write(
                {
                    "mission_order_approved_at": fields.Datetime.now(),
                    "final_dg_approval_log_id": log.id,
                }
            )
        next_step = self._next_step_in_phase(step)
        if not next_step and step.phase == "mission":
            next_step = self._route_steps("issuance")[:1]
        if not next_step:
            raise ValidationError(_("The approval route does not define the next required step."))
        user = self._enter_step(next_step)
        return self._notification(_("Approved and sent to %(user)s.", user=user.name))

    def action_open_return_wizard(self):
        self.ensure_one()
        self._check_current_actor()
        return {
            "type": "ir.actions.act_window",
            "name": _("Return for Correction"),
            "res_model": "gov.hr.return.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_res_model": self._name,
                "default_res_id": self.id,
                "default_step_name": self.current_step_id.name,
            },
        }

    def action_return(self, reason):
        self.ensure_one()
        step = self._check_current_actor()
        if step.step_kind == "issuance":
            raise UserError(_("An issuance task cannot be returned; complete the outgoing registration or contact the Administrative Manager."))
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError(_("A return reason is required."))
        if step.phase == "memo":
            correction_user = self.requester_user_id
        else:
            correction_user = self.administrative_officer_user_id
        if not correction_user:
            raise ValidationError(_("The correction user does not have an active Odoo account."))
        previous_state = self.state
        self._complete_activity()
        self._log_action(
            "returned", step=step, reason=reason, previous_state=previous_state, new_state="returned"
        )
        self.case_id.sudo().write(
            {
                "state": "returned",
                "returned_from_phase": step.phase,
                "returned_from_step_id": step.id,
                "current_step_id": False,
                "current_approver_user_id": False,
                "correction_user_id": correction_user.id,
            }
        )
        correction_activity = self.sudo().activity_schedule(
            "gov_hr_base.mail_activity_type_gov_hr_approval",
            user_id=correction_user.id,
            summary=_("Correct government case %(reference)s", reference=self.name),
            note=reason,
        )
        self.case_id.sudo().write({"current_activity_id": correction_activity.id})
        self.message_post(
            body=Markup("<p><strong>%s</strong></p><p>%s</p>")
            % (_("Returned for correction"), reason)
        )
        return self._notification(_("The case was returned to %(user)s for correction.", user=correction_user.name), "warning")

    def _log_documents_verified(self):
        self.ensure_one()
        step = self._check_current_actor("document_review")
        self._log_action("documents_verified", step=step)
        self.message_post(body=_("Supporting documents were verified by %(user)s.", user=self.env.user.name))

    def _complete_document_review(self):
        self.ensure_one()
        step = self._check_current_actor("document_review")
        self._complete_activity()
        self._log_action("mission_order_prepared", step=step, new_state="final_approvals")
        self.case_id.sudo().write(
            {"memo_completed_at": fields.Datetime.now(), "state": "mission_preparation", "phase": "mission"}
        )
        next_step = self._route_steps("mission")[:1]
        if not next_step:
            raise ValidationError(_("No mission-order approval step is configured."))
        user = self._enter_step(next_step)
        return self._notification(_("The mission order was prepared and sent to %(user)s.", user=user.name))

    def _complete_issuance(self):
        self.ensure_one()
        step = self._check_current_actor("issuance")
        if not self.final_dg_approval_log_id or self.final_dg_approval_log_id.action != "approved":
            raise ValidationError(_("Final Director General approval is required before issuance."))
        if not self.outgoing_number or not self.outgoing_date:
            raise ValidationError(_("Enter both the outgoing number and outgoing date before issuance."))
        self._complete_activity()
        self._log_action("issued", step=step, new_state="done")
        now = fields.Datetime.now()
        hours = (now - self.submitted_at).total_seconds() / 3600 if self.submitted_at else 0.0
        self.case_id.sudo().write(
            {
                "state": "done",
                "issued_at": now,
                "completed_at": now,
                "processing_duration_hours": hours,
                "current_step_id": False,
                "current_approver_user_id": False,
                "correction_user_id": False,
            }
        )
        return True
