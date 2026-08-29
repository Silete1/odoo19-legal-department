# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.tests.common import TransactionCase, new_test_user


class DmaAccreditationCommon(TransactionCase):
    """One user per role plus a ready to use request, shared by every test."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.partner = cls.env["res.partner"].create({
            "name": "Test Demining Company",
            "is_company": True,
            "email": "contact@test-demining.example.com",
        })
        cls.contact = cls.env["res.partner"].create({
            "name": "Test Representative",
            "parent_id": cls.partner.id,
            "email": "rep@test-demining.example.com",
        })

        cls.user_reception = cls._new_role_user("reception", "group_dma_reception")
        cls.user_gd = cls._new_role_user("gd", "group_dma_general_director")
        cls.user_legal = cls._new_role_user("legal", "group_dma_legal_director")
        cls.user_cert = cls._new_role_user("cert", "group_dma_cert_officer")
        cls.user_operations = cls._new_role_user("operations", "group_dma_operations")
        cls.user_finance = cls._new_role_user("finance", "group_dma_finance")
        cls.user_committee = cls._new_role_user("committee", "group_dma_committee")
        cls.user_manager = cls._new_role_user("manager", "group_dma_manager")

        cls.scopes = (
            cls.env.ref("dma_accreditation.scope_manual_clearance")
            + cls.env.ref("dma_accreditation.scope_eod")
        )

    @classmethod
    def _new_role_user(cls, key, group):
        return new_test_user(
            cls.env,
            login=f"dma_test_{key}",
            name=f"DMA Test {key}",
            email=f"dma_test_{key}@example.com",
            groups=f"base.group_user,dma_accreditation.{group}",
        )

    # ------------------------------------------------------------------
    # Factories / workflow shortcuts
    # ------------------------------------------------------------------
    def _new_request(self, **values):
        vals = {
            "partner_id": self.partner.id,
            "contact_partner_id": self.contact.id,
            "scope_ids": [(6, 0, self.scopes.ids)],
        }
        vals.update(values)
        return self.env["dma.accreditation.request"].with_user(self.user_reception).create(vals)

    def _as(self, request, user):
        return request.with_user(user)

    def _accept_all_documents(self, request):
        request.with_user(self.user_cert).document_ids.write({
            "is_provided": True,
            "review_result": "accepted",
        })

    def _add_confirmed_fee(self, request, fee_type, receipt="REC/TEST/0001"):
        fee = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": fee_type,
            "amount": 100.0,
            "receipt_number": receipt,
            "receipt_date": fields.Date.context_today(request),
        })
        fee.action_confirm()
        return fee

    def _attach_sop(self, request):
        attachment = self.env["ir.attachment"].create({
            "name": "SOP.pdf",
            "type": "binary",
            "raw": b"%PDF-1.4\ntest\n",
            "mimetype": "application/pdf",
            "res_model": request._name,
            "res_id": request.id,
        })
        request.sudo().write({"sop_attachment_ids": [(6, 0, attachment.ids)]})
        return attachment

    def _drive_to_office_granted(self, request):
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        self._accept_all_documents(request)
        self._as(request, self.user_cert).action_grant_office_accreditation()
        return request

    def _drive_to_dual_confirm(self, request):
        self._drive_to_office_granted(request)
        self._as(request, self.user_operations).action_start_operational_phase()
        self._attach_sop(request)
        self._as(request, self.user_operations).action_register_paper_sop()
        self._as(request, self.user_operations).action_sop_received()
        self._add_confirmed_fee(request, "sop_reading", "REC/TEST/SOP")
        self._as(request, self.user_finance).action_sop_fee_registered()
        return request
