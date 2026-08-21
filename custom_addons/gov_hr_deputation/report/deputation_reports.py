from odoo import api, models
from odoo.tools.image import image_data_uri


class DeputationMemorandumFinalReport(models.AbstractModel):
    _name = "report.gov_hr_deputation.report_deputation_memorandum_final"
    _description = "Final Deputation Memorandum Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["gov.hr.deputation"].browse(docids)
        docs._check_can_render_final_memorandum()
        return {
            "doc_ids": docids,
            "doc_model": "gov.hr.deputation",
            "docs": docs,
            "is_final": True,
        }


class DeputationMissionOrderFinalReport(models.AbstractModel):
    _name = "report.gov_hr_deputation.report_deputation_mission_order_final"
    _description = "Final Deputation Mission Order Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env["gov.hr.deputation"].browse(docids)
        docs._check_can_render_final_order()
        stamps = {
            doc.id: image_data_uri(doc.company_id.sudo().gov_hr_official_stamp)
            for doc in docs
        }
        signatures = {
            doc.id: image_data_uri(doc.company_id.sudo().gov_hr_director_general_signature)
            if doc.company_id.sudo().gov_hr_director_general_signature
            else False
            for doc in docs
        }
        return {
            "doc_ids": docids,
            "doc_model": "gov.hr.deputation",
            "docs": docs,
            "is_final": True,
            "stamp_by_id": stamps,
            "signature_by_id": signatures,
        }
