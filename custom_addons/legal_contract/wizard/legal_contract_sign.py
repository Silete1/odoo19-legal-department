from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LegalContractSign(models.TransientModel):
    """File the signed contract into the permanent document register.

    The signed PDF belongs in ``legal.document`` - the company's one register of
    dated artefacts - and not as a loose attachment on the contract, so that its
    expiry is chased on the same renewal board as every licence and identity. The
    wizard is where the signature date, the register document type and the scan
    are captured in one step, and it refuses to file twice.
    """

    _name = "legal.contract.sign"
    _description = "File Signed Contract"

    contract_id = fields.Many2one(
        "legal.contract", required=True, ondelete="cascade"
    )
    document_type_id = fields.Many2one(
        "legal.document.type",
        string="Register As",
        required=True,
        default=lambda self: self.env.ref(
            "legal_contract.doctype_signed_contract", raise_if_not_found=False
        ),
        help="The document type the signed contract is filed under in the register.",
    )
    signature_date = fields.Date(
        required=True, default=fields.Date.context_today
    )
    fully_signed = fields.Boolean(
        string="Signed By Both Sides",
        default=True,
        help="Leave unset if only we have signed so far; the contract is then "
        "marked 'signed by us' until the counter-signed copy is in.",
    )
    attachment = fields.Binary(string="Signed PDF", attachment=True)
    attachment_name = fields.Char(string="File Name")
    note = fields.Char(string="Remark")

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group("legal_core.group_legal_approver"):
            raise UserError(
                _("Only an approver or the legal manager may file a signed contract.")
            )
        contract = self.contract_id
        if contract.signed_document_id:
            raise UserError(
                _(
                    "The signed contract is already filed as %s. Supersede that "
                    "register entry rather than filing a second one.",
                    contract.signed_document_id.display_name,
                )
            )
        document = self.env["legal.document"].create(
            {
                "name": "%s - %s" % (contract.name, contract.title or ""),
                "document_type_id": self.document_type_id.id,
                "entity_id": contract.entity_id.id,
                "issue_date": self.signature_date,
                "expiry_date": contract.expiry_date,
                "company_id": contract.company_id.id,
            }
        )
        if self.attachment:
            attachment = self.env["ir.attachment"].create(
                {
                    "name": self.attachment_name or (contract.name + ".pdf"),
                    "datas": self.attachment,
                    "res_model": "legal.document",
                    "res_id": document.id,
                }
            )
            document.attachment_ids = [(4, attachment.id)]
        contract.write(
            {
                "signed_document_id": document.id,
                "signature_date": self.signature_date,
                "signature_status": "fully_signed" if self.fully_signed else "ours_signed",
                "state": "signed" if contract.state in ("to_sign", "counterparty_review") else contract.state,
            }
        )
        contract.message_post(
            body=_("Signed contract filed in the register as %s.", document.display_name)
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "legal.document",
            "res_id": document.id,
            "view_mode": "form",
        }
