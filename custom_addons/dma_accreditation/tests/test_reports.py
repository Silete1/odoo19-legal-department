# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationReports(DmaAccreditationCommon):
    """Smoke tests for the sequences, the QWeb documents and the settings.

    The reports are rendered to HTML rather than to PDF: the rendering of the
    QWeb templates is what we want to cover, and a CI machine has no reason to
    ship wkhtmltopdf.
    """

    def _render(self, report_xmlid, request):
        report = self.env.ref(report_xmlid)
        html, content_type = report._render_qweb_html(report_xmlid, request.ids)
        self.assertEqual(content_type, "html")
        return html.decode() if isinstance(html, bytes) else html

    def test_01_sequences_are_unique_and_prefixed(self):
        first = self._new_request()
        second = self._new_request()
        self.assertNotEqual(first.name, second.name)
        for request in (first, second):
            self.assertTrue(request.name.startswith("DMA/ACC/"))
        self.assertEqual(
            len(first.name.rsplit("/", 1)[-1]), 4, "The counter is padded to 4 digits",
        )

    def test_02_office_letter_shows_nothing_official_before_it_is_granted(self):
        """A file that has not been granted must not print like a letter."""
        request = self._new_request()
        html = self._render("dma_accreditation.action_report_office_letter", request)
        self.assertIn("NOT GRANTED", html)
        self.assertNotIn("م / منح التفويض المكتبي", html)
        cert = self._render("dma_accreditation.action_report_certificate", request)
        self.assertIn("NOT ISSUED", cert)
        self.assertNotIn("شهادة تفويض العمليات", cert)

    def test_02b_office_letter_renders_with_the_qr_code(self):
        request = self._drive_to_office_granted(self._new_request())
        html = self._render("dma_accreditation.action_report_office_letter", request)
        self.assertIn(request.office_ref, html)
        self.assertIn(request.partner_id.name, html)
        self.assertIn("التفويض المكتبي", html)
        self.assertIn(
            f"/report/barcode/QR/{request.verification_token}", html,
            "The letter must carry the verification QR code",
        )
        for scope in request.scope_ids:
            self.assertIn(scope.name, html)

    def test_03_certificate_renders_with_its_references(self):
        request = self._drive_to_dual_confirm(self._new_request())
        self._as(request, self.user_finance).action_finance_confirm()
        self._as(request, self.user_operations).action_operations_confirm()
        self._as(request, self.user_finance).action_dual_confirm_done()
        self._add_confirmed_fee(request, "operational_demo", "REC/TEST/RPT")
        self._as(request, self.user_finance).action_demo_fee_registered()
        request.sudo().write({
            "committee_decision": "approve",
            "committee_date": fields.Date.context_today(request),
            "decision_text": "<p>Approved.</p>",
        })
        self._as(request, self.user_committee).action_committee_decision()
        request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
        self._as(request, self.user_legal).action_issue_authorization()

        html = self._render("dma_accreditation.action_report_certificate", request)
        self.assertIn(request.certificate_ref, html)
        self.assertIn("تفويض العمليات", html)
        self.assertIn(f"/report/barcode/QR/{request.verification_token}", html)

    def test_04_summary_lists_the_whole_file(self):
        request = self._drive_to_dual_confirm(self._new_request())
        html = self._render("dma_accreditation.action_report_request_summary", request)
        self.assertIn(request.name, html)
        self.assertIn(request.partner_id.name, html)
        self.assertIn("REC/TEST/SOP", html, "The fees table is expected")
        self.assertIn(
            request.document_ids[0].type_id.name, html,
            "The prerequisites checklist is expected",
        )
        self.assertIn(
            self.user_gd.name, html, "The approvals log is expected in the summary",
        )

    def test_05_reports_are_rtl_and_arabic_first(self):
        request = self._drive_to_office_granted(self._new_request())
        for xmlid in (
            "dma_accreditation.action_report_office_letter",
            "dma_accreditation.action_report_request_summary",
        ):
            with self.subTest(report=xmlid):
                html = self._render(xmlid, request)
                self.assertIn('dir="rtl"', html)
                self.assertIn("دائرة شؤون الألغام", html)

    def test_06_verification_url_uses_the_token(self):
        request = self._new_request()
        url = request.get_verification_url()
        self.assertTrue(url.endswith(request.verification_token))
        self.assertIn("/dma/verify/", url)

    def test_07_fee_defaults_come_from_the_settings(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("dma_accreditation.sop_fee", "333.0")
        params.set_param("dma_accreditation.demo_fee", "777.0")
        request = self._new_request()
        sop = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": "sop_reading",
        })
        demo = self.env["dma.fee.payment"].with_user(self.user_finance).create({
            "request_id": request.id,
            "fee_type": "operational_demo",
        })
        self.assertEqual(sop.amount, 333.0)
        self.assertEqual(demo.amount, 777.0)

    def test_08_settings_round_trip(self):
        """The Accreditation Manager - not only a system administrator - saves."""
        Settings = self.env["dma.accreditation.settings"].with_user(self.user_manager)
        settings = Settings.create({
            "sop_fee": 275.0,
            "demo_fee": 610.0,
            "validity_months": 24,
        })
        settings.action_apply()
        params = self.env["ir.config_parameter"].sudo()
        self.assertEqual(float(params.get_param("dma_accreditation.sop_fee")), 275.0)
        self.assertEqual(float(params.get_param("dma_accreditation.demo_fee")), 610.0)
        self.assertEqual(int(params.get_param("dma_accreditation.validity_months")), 24)
        # Reopening the dialog shows what was saved.
        self.assertEqual(Settings.default_get(["sop_fee"])["sop_fee"], 275.0)
        self.assertEqual(Settings.default_get(["validity_months"])["validity_months"], 24)

    def test_08b_settings_reject_nonsense_and_non_managers(self):
        Settings = self.env["dma.accreditation.settings"]
        bad = Settings.with_user(self.user_manager).create({"validity_months": 0})
        with self.assertRaises(ValidationError):
            bad.action_apply()
        negative = Settings.with_user(self.user_manager).create({"sop_fee": -1.0})
        with self.assertRaises(ValidationError):
            negative.action_apply()
        with self.assertRaises(AccessError):
            Settings.with_user(self.user_finance).create({"sop_fee": 1.0})

    def test_09_validity_setting_drives_the_expiry_date(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "dma_accreditation.validity_months", "6",
        )
        request = self._new_request()
        issue = fields.Date.from_string("2026-01-01")
        self.assertEqual(
            request._compute_expiry_date(issue),
            fields.Date.from_string("2026-06-30"),
        )

    def test_10_every_view_of_the_module_is_valid(self):
        """get_views() compiles the arch of every view we ship."""
        request_model = self.env["dma.accreditation.request"].with_user(self.user_manager)
        request_model.get_views([
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_form").id, "form"),
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_list").id, "list"),
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_kanban").id, "kanban"),
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_search").id, "search"),
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_activity").id, "activity"),
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_graph").id, "graph"),
            (self.env.ref("dma_accreditation.dma_accreditation_request_view_pivot").id, "pivot"),
        ])
        self.env["dma.fee.payment"].with_user(self.user_finance).get_views([
            (self.env.ref("dma_accreditation.dma_fee_payment_view_form").id, "form"),
            (self.env.ref("dma_accreditation.dma_fee_payment_view_list").id, "list"),
            (self.env.ref("dma_accreditation.dma_fee_payment_view_search").id, "search"),
        ])
        self.env["dma.decision.reason"].with_user(self.user_gd).get_views([
            (self.env.ref("dma_accreditation.dma_decision_reason_view_form").id, "form"),
        ])
        self.env["dma.accreditation.settings"].with_user(self.user_manager).get_views([
            (self.env.ref("dma_accreditation.dma_accreditation_settings_view_form").id, "form"),
        ])
