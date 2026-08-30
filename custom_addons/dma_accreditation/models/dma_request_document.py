# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .dma_constants import state_label

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
    #: One badge instead of three columns. "Not provided" and "Awaiting review"
    #: are the two states the office accreditation gate actually turns on, and
    #: they were indistinguishable while the reader had to combine
    #: ``is_required``, ``is_provided`` and ``review_result`` by eye.
    line_status = fields.Selection(
        [
            ("optional", "Optional"),
            ("to_provide", "Not provided"),
            ("to_review", "Awaiting review"),
            ("accepted", "Accepted"),
            ("missing", "Missing"),
            ("invalid", "Invalid"),
        ],
        string="Status", compute="_compute_line_status", store=True,
    )
    reviewed_by = fields.Many2one("res.users", string="Reviewed By", readonly=True, copy=False)
    reviewed_on = fields.Datetime(string="Reviewed On", readonly=True, copy=False)
    notes = fields.Text(
        string="Reviewer Note",
        help="Why the document was refused, or anything the Certifications "
             "Division wants on file about it.",
    )
    attachment_count = fields.Integer(
        # Not "Files": that is the label of attachment_ids, and two fields of
        # one model sharing a label make an ambiguous export and an ambiguous
        # optional-column menu.
        string="Files Attached", compute="_compute_attachment_count",
    )
    company_id = fields.Many2one(related="request_id.company_id")

    @api.depends("is_required", "is_provided", "review_result")
    def _compute_line_status(self):
        for line in self:
            if line.review_result in ("missing", "invalid"):
                line.line_status = line.review_result
            elif line.review_result == "accepted":
                line.line_status = "accepted"
            elif not line.is_required:
                line.line_status = "optional"
            elif line.is_provided:
                line.line_status = "to_review"
            else:
                line.line_status = "to_provide"

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for line in self:
            line.attachment_count = len(line.attachment_ids)

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

    @api.constrains("review_result", "notes")
    def _check_invalid_carries_a_reason(self):
        """"Delivered but does not qualify" is not self-explanatory.

        The module refuses to let any request level negative decision happen
        without a reason - the return and reject wizard requires one - and the
        outcome of this one is printed to the applicant on the office letter.
        "Missing" needs no note: never handed over says itself.
        """
        for line in self:
            if line.review_result == "invalid" and not (line.notes or "").strip():
                raise ValidationError(self.env._(
                    "Say why “%s” does not meet the requirement: the reason is "
                    "printed on the letter the applicant receives.",
                    line.type_id.display_name,
                ))

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

    def _check_verification_state(self):
        """A prerequisite is verified at the Certifications step and nowhere else.

        The inline row buttons already say so, but the checklist is also
        reachable through the row dialog and over RPC, and the role check alone
        let a Certifications officer sign a file off while it was still with the
        General Director - so it arrived at ``cert_check`` with its hard gate
        already open and nothing in the approvals log.
        """
        if self.env.su or self.env.user.has_group("dma_accreditation.group_dma_manager"):
            return
        early = self.filtered(lambda line: line.request_id.state != "cert_check")
        if early:
            request = early[0].request_id
            raise UserError(self.env._(
                "A prerequisite can only be verified while the file is with the "
                "Certifications Division. %(request)s is at “%(state)s”.",
                request=request.name,
                state=state_label(self.env, request.state),
            ))

    def _check_not_closed(self):
        """The checklist of an issued or refused accreditation is history."""
        if self.env.su:
            return
        closed = self.filtered(
            lambda line: line.request_id.state in ("authorized", "rejected")
        )
        if closed:
            request = closed[0].request_id
            raise UserError(self.env._(
                "The prerequisites of %(request)s can no longer be changed: the "
                "file is closed (%(state)s).",
                request=request.name,
                state=state_label(self.env, request.state),
            ))

    def write(self, vals):
        self._check_not_closed()
        if VERIFICATION_FIELDS.intersection(vals):
            self._check_verification_role(self.env._("Verifying a document"))
            self._check_verification_state()
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
        """The applicant never handed the document over."""
        self.write({"is_provided": False, "review_result": "missing"})

    def action_mark_invalid(self):
        """The document was handed over but does not meet the requirement.

        Kept apart from "missing": a policy that expired last year was
        delivered, and the office letter has to say so rather than claim the
        applicant sent nothing.
        """
        self.write({"review_result": "invalid"})

    def action_open_files(self):
        """Open the line in a dialog, where the upload widget has room to work."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            # Pinned: without it any lower-priority form added later silently
            # hijacks the dialog the paperclip opens.
            "view_id": self.env.ref(
                "dma_accreditation.dma_request_document_view_form"
            ).id,
            "target": "new",
            "context": {"dialog_size": "medium"},
        }
