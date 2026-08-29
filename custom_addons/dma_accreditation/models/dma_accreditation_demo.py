# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Demo helper.

The demo files could set ``state`` directly, but then the approval log, the
chatter and the activities of the demo records would be empty and the module
would demo badly. Instead the demo data drives the *real* workflow methods,
each one impersonating the department that owns the step, so a freshly
installed demo database looks exactly like one that has been used.

This module is loaded in every database but the method below only ever runs
when the demo data file calls it.
"""
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class DmaAccreditationRequest(models.Model):
    _inherit = "dma.accreditation.request"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _demo_as(self, xmlid):
        """Return this request in the environment of a demo user."""
        user = self.env.ref(xmlid)
        return self.with_user(user)

    def _demo_accept_documents(self, limit=None):
        """Mark checklist lines as provided and accepted, oldest first."""
        lines = self.document_ids.sorted("sequence")
        if limit is not None:
            lines = lines[:limit]
        lines.write({"is_provided": True, "review_result": "accepted"})

    def _demo_add_fee(self, fee_type, receipt_number, confirm=True):
        """Register a fee as the Finance Department, which owns that model."""
        finance = self.env.ref("dma_accreditation.demo_user_finance")
        fee = self.env["dma.fee.payment"].with_user(finance).create({
            "request_id": self.id,
            "fee_type": fee_type,
            "receipt_number": receipt_number,
            "receipt_date": fields.Date.context_today(self),
        })
        if confirm:
            fee.action_confirm()
        return fee

    # ------------------------------------------------------------------
    # Demo scenario
    # ------------------------------------------------------------------
    @api.model
    def _load_demo_workflow(self):
        """Drive the demo requests through the workflow as the real roles."""
        ref = self.env.ref
        reception = "dma_accreditation.demo_user_reception"
        gd = "dma_accreditation.demo_user_general_director"
        legal = "dma_accreditation.demo_user_legal"
        cert = "dma_accreditation.demo_user_cert"
        operations = "dma_accreditation.demo_user_operations"
        committee = "dma_accreditation.demo_user_committee"

        scopes = {
            "manual": ref("dma_accreditation.scope_manual_clearance"),
            "bac": ref("dma_accreditation.scope_bac"),
            "eod": ref("dma_accreditation.scope_eod"),
            "nts": ref("dma_accreditation.scope_non_technical_survey"),
            "eore": ref("dma_accreditation.scope_eore"),
            "ts": ref("dma_accreditation.scope_technical_survey"),
        }

        def new_request(xmlid, partner_xmlid, contact_xmlid, scope_keys, request_type="new"):
            request = self.with_user(ref(reception)).create({
                "partner_id": ref(partner_xmlid).id,
                "contact_partner_id": ref(contact_xmlid).id,
                "request_type": request_type,
                "scope_ids": [(6, 0, [scopes[key].id for key in scope_keys])],
            })
            self.env["ir.model.data"]._update_xmlids([{
                "xml_id": f"dma_accreditation.{xmlid}",
                "record": request,
                "noupdate": True,
            }])
            return request

        # -- 1. A brand new file still on the desk of the reception ------
        new_request(
            "demo_request_draft", "dma_accreditation.demo_partner_alamal",
            "dma_accreditation.demo_partner_alamal_contact",
            ["manual", "eod"], request_type="renewal",
        )

        # -- 2. A file blocked on the prerequisites checklist ------------
        blocked = new_request(
            "demo_request_cert_check", "dma_accreditation.demo_partner_alamal",
            "dma_accreditation.demo_partner_alamal_contact",
            ["manual", "bac", "eod"],
        )
        blocked._demo_as(reception).action_submit()
        blocked._demo_as(reception).action_send_to_general_director()
        blocked._demo_as(gd).action_gd_accept()
        blocked._demo_as(legal).action_legal_approve()
        # Only part of the checklist is accepted: the office accreditation
        # stays blocked, which is exactly what the hard gate is for.
        blocked._demo_as(cert)._demo_accept_documents(limit=7)

        # -- 3. A file waiting for the second signature of the dual step -
        dual = new_request(
            "demo_request_dual_confirm", "dma_accreditation.demo_partner_sanad",
            "dma_accreditation.demo_partner_sanad_contact",
            ["bac", "nts", "eore"],
        )
        dual._demo_as(reception).action_submit()
        dual._demo_as(reception).action_send_to_general_director()
        dual._demo_as(gd).action_gd_accept()
        dual._demo_as(legal).action_legal_approve()
        dual._demo_as(cert)._demo_accept_documents()
        dual._demo_as(cert).action_grant_office_accreditation()
        dual._demo_as(operations).action_start_operational_phase()
        dual.sudo().write({
            "sop_reference": "SANAD-SOP-2026",
            "sop_version": "3.1",
            "sop_attachment_ids": [(6, 0, self._demo_attachment(
                dual, "Sanad-SOP-v3.1.pdf",
            ).ids)],
        })
        dual._demo_as(operations).action_register_paper_sop()
        dual._demo_as(operations).action_sop_received()
        dual._demo_add_fee("sop_reading", "REC/2026/0141")
        dual._demo_as("dma_accreditation.demo_user_finance").action_sop_fee_registered()
        # Finance signed off, Operations has not: the dual gate is visible.
        dual._demo_as("dma_accreditation.demo_user_finance").action_finance_confirm()

        # -- 4. A fully accredited organisation --------------------------
        done = new_request(
            "demo_request_authorized", "dma_accreditation.demo_partner_nahrain",
            "dma_accreditation.demo_partner_nahrain_contact",
            ["manual", "ts", "nts"],
        )
        done._demo_as(reception).action_submit()
        done._demo_as(reception).action_send_to_general_director()
        done._demo_as(gd).action_gd_accept()
        done._demo_as(legal).action_legal_approve()
        done._demo_as(cert)._demo_accept_documents()
        done._demo_as(cert).action_grant_office_accreditation()
        done._demo_as(operations).action_start_operational_phase()
        done.sudo().write({
            "sop_reference": "NAHRAIN-SOP-2026",
            "sop_version": "1.4",
            "sop_attachment_ids": [(6, 0, self._demo_attachment(
                done, "Nahrain-SOP-v1.4.pdf",
            ).ids)],
        })
        done._demo_as(operations).action_register_paper_sop()
        done._demo_as(operations).action_sop_received()
        done._demo_add_fee("sop_reading", "REC/2026/0155")
        done._demo_as("dma_accreditation.demo_user_finance").action_sop_fee_registered()
        done._demo_as("dma_accreditation.demo_user_finance").action_finance_confirm()
        done._demo_as(operations).action_operations_confirm()
        done._demo_as(operations).action_dual_confirm_done()
        done._demo_add_fee("operational_demo", "REC/2026/0162")
        done._demo_as("dma_accreditation.demo_user_finance").action_demo_fee_registered()
        done.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(self),
            "decision_text": (
                "<p>The Accreditation Committee approves the operational "
                "accreditation of Nahrain Clearance Group for manual clearance, "
                "technical survey and non-technical survey.</p>"
            ),
        })
        done._demo_as(committee).action_committee_decision()
        done.sudo().write({
            "refined_decision_text": (
                "<p>Pursuant to the decision of the Accreditation Committee and "
                "after legal refinement, the operational accreditation is granted "
                "for a renewable period, subject to the national mine action "
                "standards and to monitoring by the Directorate.</p>"
            ),
        })
        done._demo_as(legal).action_issue_authorization()

        # -- 5. A file returned to the applicant -------------------------
        returned = new_request(
            "demo_request_returned", "dma_accreditation.demo_partner_sanad",
            "dma_accreditation.demo_partner_sanad_contact",
            ["eod"], request_type="amendment",
        )
        returned._demo_as(reception).action_submit()
        returned._demo_as(reception).action_send_to_general_director()
        returned._demo_as(gd).action_return_to_applicant(
            "The organisational structure and the insurance policies attached to "
            "the application are outdated. Please provide the current versions."
        )
        _logger.info("DMA accreditation demo workflow loaded")
        return True

    @api.model
    def _demo_attachment(self, request, filename):
        """Create a tiny placeholder attachment so the SOP fields are not empty."""
        return self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "raw": b"%PDF-1.4\n% Demo placeholder for the DMA accreditation module.\n",
            "mimetype": "application/pdf",
            "res_model": request._name,
            "res_id": request.id,
        })
