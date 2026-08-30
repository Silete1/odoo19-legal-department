# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Replacing a document, with the reason on the record.

A returned file comes back with corrected paperwork. Dropping the new scan on
the checklist line works and is properly recorded, but it captures nothing
about *why* the old one was not good enough - and that is the one thing the
next reviewer, and the auditor after them, will want to read.

So the checklist offers this dialog: the new files, what the new document says
about itself, and a reason. The reason travels to the version that is being
superseded, where it belongs.
"""
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DmaDocumentReplacement(models.TransientModel):
    _name = "dma.document.replacement"
    _description = "Replace an Accreditation Document"

    document_id = fields.Many2one(
        "dma.request.document", string="Checklist Line", required=True,
        ondelete="cascade",
    )
    request_id = fields.Many2one(
        related="document_id.request_id", string="Request", readonly=True,
    )
    type_id = fields.Many2one(
        related="document_id.type_id", string="Document", readonly=True,
    )
    current_version = fields.Integer(
        related="document_id.version", string="Current Version", readonly=True,
    )
    current_review = fields.Selection(
        related="document_id.review_result", string="Current Review", readonly=True,
    )
    has_validity = fields.Boolean(related="document_id.type_id.has_validity", readonly=True)

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "dma_document_replacement_attachment_rel",
        "wizard_id",
        "attachment_id",
        string="New Files",
        required=True,
    )
    reference = fields.Char(string="Document Number")
    issuer = fields.Char(string="Issued By")
    issue_date = fields.Date(string="Issue Date")
    expiry_date = fields.Date(string="Expiry Date")
    reason = fields.Text(
        string="Reason for Replacement", required=True,
        help="Why the previous version was not accepted, or what changed.",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        document = self.env["dma.request.document"].browse(
            values.get("document_id")
            or self.env.context.get("default_document_id")
            or self.env.context.get("active_id")
        )
        if document.exists():
            values.setdefault("document_id", document.id)
            # Carry the metadata over: most of a replacement is the same
            # document with a new number and a later expiry.
            values.setdefault("issuer", document.issuer)
        return values

    @api.constrains("issue_date", "expiry_date")
    def _check_dates(self):
        for wizard in self:
            if wizard.issue_date and wizard.expiry_date and (
                wizard.expiry_date < wizard.issue_date
            ):
                raise ValidationError(self.env._(
                    "The expiry date of a document cannot precede its issue date."
                ))

    def action_replace(self):
        """File the old version away and put the new one on the line."""
        self.ensure_one()
        document = self.document_id
        if not document.exists():
            raise UserError(self.env._("The checklist line no longer exists."))
        if not self.attachment_ids:
            raise ValidationError(self.env._(
                "Attach the replacement document before confirming."
            ))
        # The reason rides on the context so it lands on the version that is
        # about to be superseded, which is the one it explains.
        line = document.with_context(dma_replacement_reason=self.reason.strip())
        values = {
            "attachment_ids": [fields.Command.set(self.attachment_ids.ids)],
            "is_provided": True,
        }
        for field_name in ("reference", "issuer", "issue_date", "expiry_date"):
            if self[field_name]:
                values[field_name] = self[field_name]
        line.write(values)
        # Point the new files at the checklist line, so their access follows
        # the accreditation file rather than the wizard that is about to be
        # vacuumed away.
        self.attachment_ids.sudo().write({
            "res_model": document._name, "res_id": document.id,
        })
        return {"type": "ir.actions.act_window_close"}
