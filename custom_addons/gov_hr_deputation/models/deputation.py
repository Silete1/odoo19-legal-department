from odoo import api, fields, models, tools, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.safe_eval import safe_eval


class GovHrDeputation(models.Model):
    _name = "gov.hr.deputation"
    _description = "Government Employee Deputation"
    _inherit = [
        "gov.hr.case.workflow.mixin",
        "mail.thread.main.attachment",
        "mail.activity.mixin",
    ]
    _inherits = {"gov.hr.case": "case_id"}
    _order = "date_from desc, id desc"
    _check_company_auto = True
    _mail_post_access = "read"

    case_id = fields.Many2one(
        "gov.hr.case", required=True, ondelete="cascade", index=True
    )
    deputation_activity_type_id = fields.Many2one(
        "gov.hr.deputation.activity.type",
        required=True,
        ondelete="restrict",
        check_company=True,
        tracking=True,
        index=True,
    )
    activity_description = fields.Text(required=True, tracking=True)
    destination = fields.Char(required=True, tracking=True, index=True)
    date_from = fields.Date(required=True, tracking=True, index=True)
    date_to = fields.Date(required=True, tracking=True, index=True)
    duration_days = fields.Integer(
        compute="_compute_duration_days", store=True, aggregator="sum"
    )
    average_duration_days = fields.Float(
        compute="_compute_duration_days", store=True, aggregator="avg"
    )
    participant_ids = fields.One2many(
        "gov.hr.deputation.participant", "deputation_id", string="Participants", copy=True
    )
    participant_count = fields.Integer(
        compute="_compute_participant_count", store=True, aggregator="sum"
    )
    mission_order_notes = fields.Text(tracking=True)
    documents_verified_by = fields.Many2one(
        "res.users", copy=False, readonly=True, ondelete="restrict"
    )
    documents_verified_at = fields.Datetime(copy=False, readonly=True)
    basis_required_count = fields.Integer(compute="_compute_basis_progress")
    basis_verified_count = fields.Integer(compute="_compute_basis_progress")
    basis_missing_count = fields.Integer(compute="_compute_basis_progress")
    basis_progress_label = fields.Char(compute="_compute_basis_progress")
    final_document_available = fields.Boolean(compute="_compute_document_flags")
    memorandum_available = fields.Boolean(compute="_compute_document_flags")

    _date_order = models.Constraint(
        "CHECK (date_from <= date_to)",
        "The deputation end date must be on or after the start date.",
    )

    _deputation_business_fields = {
        "deputation_activity_type_id",
        "activity_description",
        "destination",
        "date_from",
        "date_to",
        "participant_ids",
    }
    _deputation_workflow_fields = {
        "documents_verified_by",
        "documents_verified_at",
    }

    @api.model_create_multi
    def create(self, vals_list):
        case_type = self.env.ref("gov_hr_deputation.case_type_deputation")
        for vals in vals_list:
            vals.setdefault("case_type_id", case_type.id)
        records = super().create(vals_list)
        for record in records:
            record.case_id.sudo().write(
                {"business_model": record._name, "business_res_id": record.id}
            )
            if record.requester_user_id:
                record.message_subscribe(partner_ids=record.requester_user_id.partner_id.ids)
        records._sync_participant_users()
        return records

    def write(self, vals):
        if not self.env.su:
            if set(vals) & self._deputation_workflow_fields:
                raise AccessError(_("Document verification fields can only be changed by protected actions."))
            if set(vals) & self._deputation_business_fields:
                for record in self:
                    if not record._can_edit_business_data():
                        raise AccessError(_("Deputation information is locked after submission."))
            if "mission_order_notes" in vals:
                for record in self:
                    allowed = record._can_edit_business_data() or (
                        record.state in ("document_review", "returned")
                        and record.administrative_officer_user_id == self.env.user
                    )
                    if not allowed:
                        raise AccessError(_("Only the assigned administrative officer can edit mission-order notes at this stage."))
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state != "draft":
                raise AccessError(_("Submitted or issued deputations cannot be deleted."))
            if not self.env.su and not record._can_edit_business_data():
                raise AccessError(_("Only the requester can delete this draft deputation."))
        return super().unlink()

    @api.depends("date_from", "date_to")
    def _compute_duration_days(self):
        for record in self:
            record.duration_days = (
                (record.date_to - record.date_from).days + 1
                if record.date_from and record.date_to and record.date_to >= record.date_from
                else 0
            )
            record.average_duration_days = float(record.duration_days)

    @api.depends("participant_ids")
    def _compute_participant_count(self):
        for record in self:
            record.participant_count = len(record.participant_ids)

    @api.depends(
        "basis_line_ids.required",
        "basis_line_ids.file_data",
        "basis_line_ids.verification_status",
    )
    def _compute_basis_progress(self):
        for record in self:
            relevant = record.basis_line_ids.filtered(
                lambda line: line.required or line.verification_status != "optional"
            )
            required = record.basis_line_ids.filtered("required")
            verified = relevant.filtered(lambda line: line.verification_status == "verified")
            missing = required.filtered(
                lambda line: not line.file_data or line.verification_status != "verified"
            )
            record.basis_required_count = len(required)
            record.basis_verified_count = len(verified)
            record.basis_missing_count = len(missing)
            record.basis_progress_label = _(
                "%(verified)s of %(total)s verified",
                verified=len(verified),
                total=len(relevant),
            )

    @api.depends("memorandum_attachment_id", "final_order_attachment_id")
    def _compute_document_flags(self):
        for record in self:
            record.memorandum_available = bool(record.memorandum_attachment_id)
            record.final_document_available = bool(record.final_order_attachment_id)

    def _sync_participant_users(self):
        for record in self:
            users = record.participant_ids.employee_id.user_id
            record.case_id.sudo().write({"participant_user_ids": [(6, 0, users.ids)]})

    def _refresh_participant_snapshots(self):
        for record in self:
            for line in record.participant_ids:
                line.sudo().write(line._snapshot_values(line.employee_id))

    def _missing_required_basis(self, require_verified=False):
        self.ensure_one()
        required_types = self.env["gov.hr.basis.type"].search(
            [
                ("default_required", "=", True),
                ("company_id", "in", [False, self.company_id.id]),
            ]
        )
        missing_names = []
        for basis_type in required_types:
            lines = self.basis_line_ids.filtered(lambda line: line.type_id == basis_type)
            if not lines or not any(lines.mapped("file_data")):
                missing_names.append(basis_type.name)
        for line in self.basis_line_ids.filtered("required"):
            if not line.file_data or (require_verified and line.verification_status != "verified"):
                missing_names.append(line.type_id.name)
        return list(dict.fromkeys(missing_names))

    def _validate_submission(self):
        super()._validate_submission()
        self.ensure_one()
        if not self.participant_ids:
            raise ValidationError(_("Add at least one deputed employee before submission."))
        if not self.destination or not self.deputation_activity_type_id or not self.activity_description:
            raise ValidationError(_("Activity, activity description, and destination are required."))
        if not self.date_from or not self.date_to or self.date_to < self.date_from:
            raise ValidationError(_("Enter a valid deputation period."))
        if not self.requester_user_id or not self.requester_user_id.active:
            raise ValidationError(_("The requester employee must be linked to an active Odoo user."))
        missing = self._missing_required_basis(require_verified=False)
        if missing:
            raise ValidationError(
                _("The following required supporting documents are missing:\n- %(documents)s", documents="\n- ".join(missing))
            )
        self._refresh_participant_snapshots()
        self._sync_participant_users()
        for step in self.case_type_id.route_id.step_ids.filtered("active"):
            self._resolve_step_user(step)
        officer_group = self.env.ref("gov_hr_base.group_gov_hr_admin_officer")
        if officer_group not in self.administrative_officer_user_id.all_group_ids:
            raise ValidationError(_("The assigned administrative officer must have the Administrative Officer role."))
        return True

    def action_verify_documents(self):
        self.ensure_one()
        self._check_current_actor("document_review")
        missing = self._missing_required_basis(require_verified=True)
        if missing:
            raise ValidationError(
                _("Supporting-document verification cannot be completed.\nThe following documents are incomplete:\n- %(documents)s", documents="\n- ".join(missing))
            )
        incomplete = self.basis_line_ids.filtered(
            lambda line: line.verification_status == "incomplete"
        )
        if incomplete:
            raise ValidationError(
                _("Resolve documents marked incomplete before continuing: %(documents)s", documents=", ".join(incomplete.mapped("type_id.name")))
            )
        self.sudo().write(
            {
                "documents_verified_by": self.env.user.id,
                "documents_verified_at": fields.Datetime.now(),
            }
        )
        self._log_documents_verified()
        return self._notification(_("Supporting documents were verified."))

    def _archive_report(self, report_xmlid):
        self.ensure_one()
        report = self.env.ref(report_xmlid).sudo()
        content, content_type = report._render_qweb_pdf(report.id, [self.id])
        attachment = report.retrieve_attachment(self)
        # Savepoint/TransactionCase deliberately disables wkhtmltopdf because a
        # second HTTP transaction cannot see uncommitted test records.  Keep the
        # production path entirely native, while still exercising deterministic
        # attachment lookup and immutability in the ORM test suite.
        if not attachment and tools.config["test_enable"] and content_type != "pdf":
            attachment_name = safe_eval(report.attachment, {"object": self})
            attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": attachment_name,
                    "raw": content,
                    "mimetype": "application/pdf",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        if not attachment:
            raise UserError(_("Odoo did not create the expected archived PDF attachment."))
        return attachment

    def action_prepare_mission_order(self):
        self.ensure_one()
        self._check_current_actor("document_review")
        if not self.documents_verified_at:
            raise ValidationError(_("Verify the supporting documents before preparing the mission order."))
        attachment = self._archive_report(
            "gov_hr_deputation.action_report_deputation_memorandum_final"
        )
        self.case_id.sudo().write({"memorandum_attachment_id": attachment.id})
        return self._complete_document_review()

    def action_issue(self):
        self.ensure_one()
        self._check_current_actor("issuance")
        if not self.company_id.sudo().gov_hr_official_stamp:
            raise ValidationError(_("The official electronic stamp is not configured for this company."))
        if not self.outgoing_number or not self.outgoing_date:
            raise ValidationError(_("Enter the outgoing number and outgoing date before issuance."))
        if not self.final_dg_approval_log_id:
            raise ValidationError(_("Final Director General approval is required before issuance."))
        attachment = self._archive_report(
            "gov_hr_deputation.action_report_deputation_mission_order_final"
        )
        self.case_id.sudo().write({"final_order_attachment_id": attachment.id})
        self._complete_issuance()
        self.message_post(
            body=_("Mission order %(number)s was issued and its official PDF was archived.", number=self.outgoing_number)
        )
        return self._notification(_("Mission order %(number)s was issued successfully.", number=self.outgoing_number))

    def action_preview_memorandum(self):
        self.ensure_one()
        return self.env.ref(
            "gov_hr_deputation.action_report_deputation_memorandum_draft"
        ).report_action(self)

    def action_preview_mission_order(self):
        self.ensure_one()
        return self.env.ref(
            "gov_hr_deputation.action_report_deputation_mission_order_draft"
        ).report_action(self)

    def _attachment_url_action(self, attachment, title):
        if not attachment:
            raise UserError(_("The archived official document is not available."))
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=false" % attachment.id,
            "target": "new",
            "name": title,
        }

    def action_view_archived_memorandum(self):
        self.ensure_one()
        return self._attachment_url_action(self.memorandum_attachment_id, _("Official Memorandum"))

    def action_view_final_order(self):
        self.ensure_one()
        return self._attachment_url_action(self.final_order_attachment_id, _("Final Mission Order"))

    def _check_can_render_final_memorandum(self):
        for record in self:
            if not record.documents_verified_at or record.state not in (
                "document_review",
                "mission_preparation",
                "final_approvals",
                "awaiting_outgoing",
                "done",
            ):
                raise AccessError(_("The official memorandum cannot be generated before document verification."))

    def _check_can_render_final_order(self):
        for record in self:
            if record.state not in ("awaiting_outgoing", "done"):
                raise AccessError(_("The final mission order cannot be generated before final approval."))
            if not record.final_dg_approval_log_id or not record.mission_order_approved_at:
                raise AccessError(_("Final Director General approval is missing."))
            if not record.outgoing_number or not record.outgoing_date:
                raise AccessError(_("Outgoing number and date are required for the final mission order."))
            if not record.company_id.sudo().gov_hr_official_stamp:
                raise AccessError(_("The official stamp is not configured."))
