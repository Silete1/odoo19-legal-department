from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.legal_reports.report import report_models


#: Every analysis action this module mounts, with the model it must open.
ANALYSIS_ACTIONS = [
    ("legal_reports.action_legal_reports_case", "legal.case"),
    ("legal_reports.action_legal_reports_correspondence", "legal.correspondence"),
    ("legal_reports.action_legal_reports_lawsuit", "legal.lawsuit"),
    ("legal_reports.action_legal_reports_contract", "legal.contract"),
    ("legal_reports.action_legal_reports_request", "legal.request"),
    ("legal_reports.action_legal_reports_opinion", "legal.opinion"),
    ("legal_reports.action_legal_reports_obligation", "legal.obligation.instance"),
    ("legal_reports.action_legal_reports_fee", "legal.fee"),
]

#: Every printed artifact, with its model and its QWeb template.
PRINT_ACTIONS = [
    (
        "legal_reports.action_report_register_book",
        "legal.register",
        "legal_reports.report_register_book",
    ),
    (
        "legal_reports.action_report_case_cover",
        "legal.case",
        "legal_reports.report_case_cover",
    ),
    (
        "legal_reports.action_report_lawsuit_status",
        "legal.lawsuit",
        "legal_reports.report_lawsuit_status",
    ),
    (
        "legal_reports.action_report_contract_summary",
        "legal.contract",
        "legal_reports.report_contract_summary",
    ),
]

#: The Arabic label maps the prints use, against the selections they cover.
#: The suite's selections are closed vocabularies; if one grows a key, the
#: print must learn its Arabic before this test goes green again.
LABEL_MAPS = [
    ("legal.register", "direction", report_models.REGISTER_DIRECTION_AR),
    ("legal.register", "secrecy", report_models.SECRECY_AR),
    ("legal.correspondence", "state", report_models.ENTRY_STATE_AR),
    ("legal.case", "kind", report_models.CASE_KIND_AR),
    ("legal.case", "outcome", report_models.CASE_OUTCOME_AR),
    ("legal.fee", "state", report_models.FEE_STATE_AR),
    ("legal.case.document", "line_status", report_models.DOC_STATUS_AR),
    ("legal.action.log", "action", report_models.LOG_ACTION_AR),
    ("legal.lawsuit", "state", report_models.LAWSUIT_STATE_AR),
    ("legal.lawsuit", "our_capacity", report_models.CAPACITY_AR),
    ("legal.lawsuit.party", "role", report_models.PARTY_ROLE_AR),
    ("legal.hearing", "purpose", report_models.HEARING_PURPOSE_AR),
    ("legal.hearing", "attendance", report_models.ATTENDANCE_AR),
    ("legal.judgment", "ruling_type", report_models.RULING_TYPE_AR),
    ("legal.judgment", "in_our_favour", report_models.FAVOUR_AR),
    ("legal.judgment", "appeal_state", report_models.APPEAL_STATE_AR),
    ("legal.judgment", "remedy", report_models.REMEDY_AR),
    ("legal.contract", "state", report_models.CONTRACT_STATE_AR),
    ("legal.contract", "signature_status", report_models.SIGNATURE_STATUS_AR),
    ("legal.contract.party", "role", report_models.CONTRACT_ROLE_AR),
    ("legal.contract.obligation", "status", report_models.OBLIGATION_STATUS_AR),
    ("legal.contract.obligation", "responsible_party", report_models.OWED_BY_AR),
    ("legal.contract.obligation", "frequency", report_models.FREQUENCY_AR),
    ("legal.contract.modification", "state", report_models.MODIFICATION_STATE_AR),
]


@tagged("post_install", "-at_install")
class TestLegalReports(TransactionCase):
    """The two promises of this module: the menus open, the paper prints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.body = cls.env["legal.gov.body"].create(
            {
                "name": "الهيئة العامة للضرائب - تقارير",
                "code": "RPT-GCT",
                "body_type_id": cls.env.ref("legal_core.body_type_commission").id,
                "jurisdiction_id": cls.env.ref("legal_core.jurisdiction_iq_federal").id,
            }
        )
        cls.entity = cls.env["legal.entity"].create(
            {
                "name": "شركة التقارير المحدودة",
                "jurisdiction_id": cls.env.ref("legal_core.jurisdiction_iq_federal").id,
            }
        )

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------
    def test_analysis_actions_resolve(self):
        """Every action exists, opens the right model, and its pivot and
        graph views compile against that model's real fields."""
        for xmlid, model in ANALYSIS_ACTIONS:
            action = self.env.ref(xmlid)
            self.assertEqual(action.res_model, model, xmlid)
            self.assertIn("pivot", action.view_mode, xmlid)
            self.assertIn("graph", action.view_mode, xmlid)
            self.assertTrue(action.view_ids, "%s binds no explicit views" % xmlid)
            for line in action.view_ids:
                result = self.env[model].get_view(
                    view_id=line.view_id.id, view_type=line.view_mode
                )
                self.assertTrue(result.get("arch"), "%s/%s" % (xmlid, line.view_mode))

    def test_analysis_actions_are_gated(self):
        """Officer sees the analyses, the auditor sees them too, and the fee
        figures stop below manager."""
        auditor = self.env.ref("legal_core.group_legal_auditor")
        for xmlid, _model in ANALYSIS_ACTIONS:
            action = self.env.ref(xmlid)
            self.assertIn(auditor, action.group_ids, xmlid)
        fee_action = self.env.ref("legal_reports.action_legal_reports_fee")
        self.assertIn(
            self.env.ref("legal_core.group_legal_manager"), fee_action.group_ids
        )
        self.assertNotIn(
            self.env.ref("legal_core.group_legal_officer"), fee_action.group_ids
        )

    def test_fee_reporting_columns_are_stored(self):
        """The two denormalised grouping columns this module adds to the fee
        must exist, be stored, and follow the case."""
        fee_fields = self.env["legal.fee"]._fields
        for name in ("body_id", "procedure_type_id"):
            self.assertIn(name, fee_fields)
            self.assertTrue(fee_fields[name].store, name)

    # ------------------------------------------------------------------
    # Prints
    # ------------------------------------------------------------------
    def test_print_actions_resolve(self):
        for action_xmlid, model, template_xmlid in PRINT_ACTIONS:
            action = self.env.ref(action_xmlid)
            self.assertEqual(action.report_type, "qweb-pdf", action_xmlid)
            self.assertEqual(action.model, model, action_xmlid)
            self.assertEqual(
                action.binding_model_id.model, model, "%s is not in the Print menu" % action_xmlid
            )
            template = self.env.ref(template_xmlid)
            self.assertEqual(template._name, "ir.ui.view", template_xmlid)
            self.assertTrue(action.paperformat_id, action_xmlid)

    def test_print_labels_cover_the_selections(self):
        """Every selection a print spells out in Arabic still matches the
        model's own vocabulary, key for key."""
        for model, field_name, labels in LABEL_MAPS:
            description = self.env[model]._fields[field_name].get_description(self.env)
            keys = {key for key, _label in description["selection"]}
            self.assertEqual(
                keys, set(labels), "%s.%s drifted from its print labels" % (model, field_name)
            )

    def test_register_book_prints(self):
        """The book renders with its entries in it, and the wizard hands back
        the same report for its chosen year."""
        register = self.env["legal.register"].create(
            {
                "name": "سجل الصادر - تقارير",
                "code": "RPT-OUT",
                "direction": "out",
                "prefix": "ق",
                "company_id": self.company.id,
            }
        )
        entry = self.env["legal.correspondence"].create(
            {
                "register_id": register.id,
                "kind_id": self.env.ref("legal_correspondence.kind_out_letter").id,
                "direction": "out",
                "gov_body_id": self.body.id,
                "entity_id": self.entity.id,
                "subject": "طلب براءة ذمة للتقارير",
                "our_date": date.today(),
            }
        )
        entry.action_register()
        self.assertEqual(entry.state, "registered")

        html = self.env["ir.actions.report"]._render_qweb_html(
            "legal_reports.report_register_book",
            register.ids,
            data={"year": date.today().year},
        )[0].decode("utf-8")
        self.assertIn(register.name, html)
        self.assertIn("طلب براءة ذمة للتقارير", html)

        wizard = self.env["legal.register.book.wizard"].create(
            {"register_id": register.id, "year": date.today().year}
        )
        action = wizard.action_print()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(action["report_name"], "legal_reports.report_register_book")
        self.assertEqual(action["data"]["year"], date.today().year)

    def test_register_book_wizard_year_guard(self):
        register = self.env["legal.register"].create(
            {
                "name": "سجل حراسة السنة",
                "code": "RPT-YR",
                "direction": "out",
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["legal.register.book.wizard"].create(
                {"register_id": register.id, "year": 1800}
            )

    def test_lawsuit_status_prints(self):
        lawsuit = self.env["legal.lawsuit"].create(
            {
                "title": "دعوى مطالبة بمبلغ - تقارير",
                "entity_id": self.entity.id,
                "our_capacity": "defendant",
                "claim_amount": 5000000,
            }
        )
        self.env["legal.hearing"].create(
            {
                "lawsuit_id": lawsuit.id,
                "date": "2026-03-15 07:30:00",
                "purpose": "pleading",
            }
        )
        html = self.env["ir.actions.report"]._render_qweb_html(
            "legal_reports.report_lawsuit_status", lawsuit.ids
        )[0].decode("utf-8")
        self.assertIn("تقرير موقف الدعوى", html)
        self.assertIn(lawsuit.title, html)
        self.assertIn("مدعى عليه", html)

    def test_contract_summary_prints(self):
        contract_type = self.env["legal.contract.type"].create(
            {"name": "عقد خدمات - تقارير", "code": "RPT-SRV"}
        )
        contract = self.env["legal.contract"].create(
            {
                "title": "عقد تجهيز قرطاسية",
                "type_id": contract_type.id,
                "value": 12000000,
            }
        )
        html = self.env["ir.actions.report"]._render_qweb_html(
            "legal_reports.report_contract_summary", contract.ids
        )[0].decode("utf-8")
        self.assertIn("خلاصة العقد", html)
        self.assertIn(contract.title, html)

    def test_menu_tree_mounts(self):
        root = self.env.ref("legal_reports.menu_legal_reports_root")
        self.assertEqual(
            root.parent_id, self.env.ref("legal_core.menu_legal_root")
        )
        for xmlid in (
            "legal_reports.menu_legal_reports_cases",
            "legal_reports.menu_legal_reports_correspondence",
            "legal_reports.menu_legal_reports_litigation",
            "legal_reports.menu_legal_reports_contracts",
            "legal_reports.menu_legal_reports_requests_opinions",
            "legal_reports.menu_legal_reports_compliance_fees",
        ):
            self.assertEqual(self.env.ref(xmlid).parent_id, root, xmlid)
