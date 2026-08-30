# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Feeding the printed dossier index the very same structure the screen uses.

The report renders ``_dossier_index()`` and nothing else, so the cover sheet an
auditor is handed, the panel the officer reads on the form and the archive that
is downloaded are three renderings of one reading of the file. They cannot
disagree about what the dossier contains.
"""
from odoo import api, models


class ReportDossierIndex(models.AbstractModel):
    _name = "report.dma_accreditation.report_dossier_index"
    _description = "Accreditation Dossier Index"

    @api.model
    def _get_report_values(self, docids, data=None):
        requests = self.env["dma.accreditation.request"].browse(docids)
        dossier = {}
        for request in requests:
            sections = request._dossier_index()
            prerequisites = next(
                (section for section in sections if section["key"] == "prerequisites"),
                {},
            )
            dossier[request.id] = {
                "sections": sections,
                "file_count": sum(
                    len(section.get("entries", [])) for section in sections
                ),
                "missing": [
                    block["label"] for block in prerequisites.get("documents", [])
                    if block["required"] and not block["satisfied"]
                ],
            }
        return {
            "doc_ids": docids,
            "doc_model": "dma.accreditation.request",
            "docs": requests,
            "dossier_data": dossier,
        }
