# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The superseded versions of a piece of accreditation evidence.

A returned file comes back with corrected paperwork, and the corrected copy
must not be able to quietly take the place of the one an officer actually
looked at. So whenever the evidence behind a checklist line changes, the state
it was in is frozen into one of these rows first: which files were attached,
what the Certifications Division had made of them, who decided that and when.

What this model is *not*
------------------------
It is not a copy of the files. The attachments are referenced, never
duplicated, so a dossier that carries four versions of an insurance policy
still holds exactly four files in the filestore. And it is not the current
version: the checklist line itself is always the current version, which is what
keeps the existing review gate, the existing views and the other departments'
screens working exactly as they did.

The rows are immutable for the same reason ``dma.approval.line`` is: they are
evidence of what happened, and an audit that can be edited is not an audit.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError

from .dma_request_document import REVIEW_RESULT_SELECTION


class DmaDocumentSubmission(models.Model):
    """One superseded version of the evidence behind a checklist line."""

    _name = "dma.document.submission"
    _description = "Accreditation Document Version"
    _order = "document_id, version desc, id desc"

    document_id = fields.Many2one(
        "dma.request.document", string="Checklist Line", required=True,
        ondelete="cascade", index=True,
    )
    # Stored related fields: the dossier, the document health figures and the
    # searches all start from the file rather than from the checklist line, and
    # a stored copy keeps them one indexed lookup instead of a join per row.
    request_id = fields.Many2one(
        related="document_id.request_id", string="Request", store=True, index=True,
    )
    type_id = fields.Many2one(
        related="document_id.type_id", string="Document Type", store=True, index=True,
    )
    company_id = fields.Many2one(related="document_id.company_id", store=True, index=True)

    version = fields.Integer(
        string="Version", required=True, default=1, readonly=True,
        help="1 is the first set of files the applicant handed in.",
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "dma_document_submission_attachment_rel",
        "submission_id",
        "attachment_id",
        string="Files",
        help="The files exactly as they were. They are referenced, not copied: "
             "an old version costs no extra space in the filestore.",
    )
    attachment_count = fields.Integer(
        string="Number of Files", compute="_compute_attachment_count",
    )

    # ------------------------------------------------------------------
    # What the Directorate had made of it
    # ------------------------------------------------------------------
    review_result = fields.Selection(
        REVIEW_RESULT_SELECTION, string="Review Result", required=True,
        default="pending", readonly=True,
    )
    reviewed_by = fields.Many2one("res.users", string="Reviewed By", readonly=True)
    reviewed_on = fields.Datetime(string="Reviewed On", readonly=True)
    notes = fields.Text(string="Review Notes", readonly=True)

    # ------------------------------------------------------------------
    # What the document itself said
    # ------------------------------------------------------------------
    reference = fields.Char(string="Document Number", readonly=True)
    issuer = fields.Char(string="Issued By", readonly=True)
    issue_date = fields.Date(string="Issue Date", readonly=True)
    expiry_date = fields.Date(string="Expiry Date", readonly=True)

    # ------------------------------------------------------------------
    # How it came to be superseded
    # ------------------------------------------------------------------
    superseded_on = fields.Datetime(
        string="Replaced On", required=True, default=fields.Datetime.now, readonly=True,
        index=True,
    )
    superseded_by = fields.Many2one(
        "res.users", string="Replaced By", required=True, readonly=True,
        default=lambda self: self.env.user,
    )
    replacement_reason = fields.Text(
        string="Reason for Replacement", readonly=True,
        help="Why this version was replaced, when the officer gave a reason.",
    )

    _unique_version = models.UniqueIndex(
        "(document_id, version)",
        "This version of the document has already been recorded.",
    )

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for submission in self:
            submission.attachment_count = len(submission.attachment_ids)

    @api.depends("type_id", "version")
    def _compute_display_name(self):
        for submission in self:
            submission.display_name = self.env._(
                "%(document)s - version %(version)s",
                document=submission.type_id.display_name or "",
                version=submission.version,
            )

    # ------------------------------------------------------------------
    # Immutability
    # ------------------------------------------------------------------
    def write(self, vals):
        raise UserError(self.env._(
            "A previous version of a document records what was actually "
            "submitted and reviewed at the time; it can never be modified."
        ))

    def unlink(self):
        raise UserError(self.env._(
            "A previous version of a document is part of the evidence trail of "
            "the accreditation and can never be deleted."
        ))

    def action_open_files(self):
        """Show the files of this version, read only."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.display_name,
            "res_model": "ir.attachment",
            "view_mode": "kanban,list,form",
            "domain": [("id", "in", self.attachment_ids.ids)],
            "context": {"create": False, "edit": False},
        }
