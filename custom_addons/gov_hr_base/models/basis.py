from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class GovHrBasisType(models.Model):
    _name = "gov.hr.basis.type"
    _description = "Government HR Basis Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    default_required = fields.Boolean(string="Required by Default")
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    _unique_code_company = models.Constraint(
        "UNIQUE (company_id, code)", "Basis type codes must be unique per company."
    )


class GovHrCaseBasis(models.Model):
    _name = "gov.hr.case.basis"
    _description = "Government HR Supporting Document"
    _order = "sequence, id"
    _check_company_auto = True

    case_id = fields.Many2one(
        "gov.hr.case", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(related="case_id.company_id", store=True, index=True)
    type_id = fields.Many2one(
        "gov.hr.basis.type",
        required=True,
        ondelete="restrict",
        check_company=True,
    )
    reference_number = fields.Char()
    reference_date = fields.Date()
    issuer = fields.Char()
    description = fields.Char()
    file_data = fields.Binary(attachment=True)
    filename = fields.Char()
    required = fields.Boolean(default=False)
    verification_status = fields.Selection(
        [
            ("pending", "Pending"),
            ("verified", "Verified"),
            ("incomplete", "Incomplete"),
            ("optional", "Optional"),
        ],
        default="pending",
        required=True,
        index=True,
    )
    verified_by = fields.Many2one("res.users", readonly=True, ondelete="restrict")
    verified_at = fields.Datetime(readonly=True)
    notes = fields.Text()
    sequence = fields.Integer(default=10)

    @api.onchange("type_id")
    def _onchange_type_id(self):
        if self.type_id:
            self.required = self.type_id.default_required

    @api.constrains("verification_status", "file_data")
    def _check_verified_file(self):
        for line in self:
            if line.verification_status == "verified" and not line.file_data:
                raise ValidationError(_("A document cannot be verified before a file is uploaded."))

    def _check_edit(self, vals=None):
        vals = vals or {}
        for line in self:
            case = line.case_id
            verification_fields = {
                "verification_status",
                "verified_by",
                "verified_at",
                "notes",
            }
            if set(vals) & verification_fields:
                if not case._is_assigned_administrative_officer():
                    raise AccessError(_("Only the assigned administrative officer can verify supporting documents."))
                if case.state not in ("document_review", "returned"):
                    raise AccessError(_("Supporting-document verification is not available at this stage."))
            elif not case._can_edit_business_data() and not (
                case.state == "document_review" and case._is_assigned_administrative_officer()
            ):
                raise AccessError(_("Supporting documents are locked after submission."))

    @api.model_create_multi
    def create(self, vals_list):
        cases = self.env["gov.hr.case"].browse([vals.get("case_id") for vals in vals_list])
        for case in cases:
            if not case._can_edit_business_data() and not (
                case.state == "document_review" and case._is_assigned_administrative_officer()
            ):
                raise AccessError(_("Supporting documents are locked after submission."))
        return super().create(vals_list)

    def write(self, vals):
        self._check_edit(vals)
        if vals.get("verification_status") == "verified":
            vals = dict(vals, verified_by=self.env.user.id, verified_at=fields.Datetime.now())
        elif vals.get("verification_status") in ("pending", "incomplete", "optional"):
            vals = dict(vals, verified_by=False, verified_at=False)
        return super().write(vals)

    def unlink(self):
        self._check_edit()
        return super().unlink()
