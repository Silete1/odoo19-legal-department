from odoo import models, _
from odoo.exceptions import AccessError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _is_gov_hr_official_archive(self):
        if not self:
            return False
        return bool(
            self.env["gov.hr.case"].sudo().search_count(
                [
                    "|",
                    ("memorandum_attachment_id", "in", self.ids),
                    ("final_order_attachment_id", "in", self.ids),
                ],
                limit=1,
            )
        )

    def write(self, vals):
        if not self.env.su and self._is_gov_hr_official_archive():
            raise AccessError(_("Archived official government documents are immutable."))
        return super().write(vals)

    def unlink(self):
        if not self.env.su and self._is_gov_hr_official_archive():
            raise AccessError(_("Archived official government documents cannot be deleted."))
        return super().unlink()
