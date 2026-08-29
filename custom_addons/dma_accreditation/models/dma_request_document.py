# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

#: Fields that carry the verification itself. Reception may assemble the file
#: - attach the documents, tick "provided" - but only the Certifications
#: Division decides whether a document counts, and whether it is mandatory.
#: Without this, the office accreditation hard gate could be opened by the very
#: department that submitted the file.
VERIFICATION_FIELDS = frozenset({"is_required", "review_result"})

REVIEW_RESULT_SELECTION = [
    ("pending", "Pending"),
    ("accepted", "Accepted"),
    ("missing", "Missing"),
    ("invalid", "Invalid"),
]


class DmaRequestDocument(models.Model):
    """One line of the office accreditation prerequisites checklist (الأوليات)."""

    _name = "dma.request.document"
    _description = "Accreditation Request Document"
    _order = "sequence, id"

    request_id = fields.Many2one(
        "dma.accreditation.request",
        string="Request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    type_id = fields.Many2one(
        "dma.document.type", string="Document Type", required=True,
        ondelete="restrict",
    )
    sequence = fields.Integer(default=10)
    is_required = fields.Boolean(
        string="Required",
        default=True,
        help="Required documents block the Office Accreditation until they are "
             "provided and accepted.",
    )
    is_provided = fields.Boolean(
        string="Provided",
        help="The applicant handed the document over to the Directorate.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "dma_request_document_attachment_rel",
        "document_id",
        "attachment_id",
        string="Files",
    )
    review_result = fields.Selection(
        REVIEW_RESULT_SELECTION, string="Review Result", default="pending",
        required=True, copy=False,
    )
    reviewed_by = fields.Many2one("res.users", string="Reviewed By", readonly=True, copy=False)
    reviewed_on = fields.Datetime(string="Reviewed On", readonly=True, copy=False)
    notes = fields.Text()
    company_id = fields.Many2one(related="request_id.company_id")

    @api.depends("type_id", "request_id")
    def _compute_display_name(self):
        for line in self:
            line.display_name = line.type_id.display_name or self.env._("Document")

    @api.onchange("type_id")
    def _onchange_type_id(self):
        for line in self:
            if line.type_id:
                line.is_required = line.type_id.required_default
                line.sequence = line.type_id.sequence

    @api.constrains("is_provided", "review_result")
    def _check_review_consistency(self):
        for line in self:
            if line.review_result == "accepted" and not line.is_provided:
                raise ValidationError(self.env._(
                    "Document “%s” cannot be accepted before it is marked as provided.",
                    line.type_id.display_name,
                ))

    def _stamp_review(self, vals):
        """Stamp reviewer/date whenever the review outcome actually changes."""
        if "review_result" in vals:
            vals = dict(
                vals,
                reviewed_by=self.env.user.id,
                reviewed_on=fields.Datetime.now(),
            )
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._stamp_review(vals) if vals.get("review_result") not in (None, "pending") else vals
            for vals in vals_list
        ]
        return super().create(vals_list)

    def _check_verification_role(self, action_label):
        user = self.env.user
        if self.env.su:
            return
        if (
            user.has_group("dma_accreditation.group_dma_cert_officer")
            or user.has_group("dma_accreditation.group_dma_manager")
        ):
            return
        raise AccessError(self.env._(
            "%s is reserved to the Certifications Division.", action_label,
        ))

    def write(self, vals):
        if VERIFICATION_FIELDS.intersection(vals):
            self._check_verification_role(self.env._("Verifying a document"))
        if "review_result" in vals:
            vals = self._stamp_review(vals)
        return super().write(vals)

    def unlink(self):
        self._check_verification_role(self.env._("Removing a checklist line"))
        return super().unlink()

    def action_mark_provided(self):
        """Quick action from the checklist list view."""
        self.write({"is_provided": True})

    def action_accept(self):
        """Accept the document (Certifications Division)."""
        self.write({"is_provided": True, "review_result": "accepted"})

    def action_mark_missing(self):
        self.write({"is_provided": False, "review_result": "missing"})
