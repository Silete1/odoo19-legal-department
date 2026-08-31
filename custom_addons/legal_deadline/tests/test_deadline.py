from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestLegalDeadline(TransactionCase):
    """The board materialises, projects honestly, and stays read-only.

    Builds its own showcase rows rather than leaning on the demo pack, so the
    assertions hold whether or not ``legal_iq_demo`` happens to be installed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Deadline Test Co B"})

        cls.clerk = new_test_user(
            cls.env,
            "ddl_clerk",
            groups="legal_core.group_legal_clerk",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )
        cls.auditor = new_test_user(
            cls.env,
            "ddl_auditor",
            groups="legal_core.group_legal_auditor",
            company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])],
        )

        # --- litigation showcase: a lawsuit with one upcoming hearing ------
        cls.jurisdiction = cls.env["legal.jurisdiction"].create(
            {"name": "Test Deadline Baghdad", "code": "TEST-DDL-BGD"}
        )
        cls.entity = cls.env["legal.entity"].create(
            {
                "name": "شركة اختبار المواعيد",
                "name_en": "Deadline Test Co",
                "jurisdiction_id": cls.jurisdiction.id,
                "company_id": cls.company.id,
            }
        )
        cls.lawsuit = cls.env["legal.lawsuit"].create(
            {
                "title": "دعوى اختبار المواعيد",
                "our_capacity": "plaintiff",
                "entity_id": cls.entity.id,
                "company_id": cls.company.id,
                "lawyer_id": cls.clerk.id,
            }
        )
        cls.hearing_date = fields.Datetime.now() + timedelta(days=7)
        cls.hearing = cls.env["legal.hearing"].create(
            {
                "lawsuit_id": cls.lawsuit.id,
                "date": cls.hearing_date,
            }
        )

        # --- obligation showcase: one period per company, one overdue ------
        cls.body_type = cls.env["legal.gov.body.type"].create(
            {"name": "Test Directorate", "code": "TEST-DDL-DIR"}
        )
        cls.body = cls.env["legal.gov.body"].create(
            {
                "name": "هيئة اختبار المواعيد",
                "code": "TEST-DDL-GCT",
                "body_type_id": cls.body_type.id,
                "jurisdiction_id": cls.jurisdiction.id,
            }
        )
        cls.schedule = cls.env["legal.obligation.schedule"].create(
            {
                "name": "التزام اختبار شهري",
                "code": "TEST-DDL-MONTHLY",
                "body_id": cls.body.id,
                "frequency": "monthly",
                "due_day": 10,
                "company_id": cls.company.id,
            }
        )
        cls.instance = cls.env["legal.obligation.instance"].create(
            {
                "schedule_id": cls.schedule.id,
                "period_key": "TEST-DDL-OVERDUE",
                "due_on": fields.Date.today() - timedelta(days=10),
                "company_id": cls.company.id,
            }
        )
        cls.schedule_b = cls.env["legal.obligation.schedule"].create(
            {
                "name": "التزام شركة أخرى",
                "code": "TEST-DDL-OTHERCO",
                "body_id": cls.body.id,
                "frequency": "monthly",
                "due_day": 10,
                "company_id": cls.company_b.id,
            }
        )
        cls.instance_b = cls.env["legal.obligation.instance"].create(
            {
                "schedule_id": cls.schedule_b.id,
                "period_key": "TEST-DDL-FENCED",
                "due_on": fields.Date.today() + timedelta(days=5),
                "company_id": cls.company_b.id,
            }
        )
        cls.env.flush_all()

    def _row(self, record):
        return self.env["legal.deadline"].search(
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
            ]
        )

    # ------------------------------------------------------------------
    # (a) The view materialises at all
    # ------------------------------------------------------------------
    def test_view_materialises(self):
        count = self.env["legal.deadline"].search_count([])
        self.assertGreaterEqual(count, 2)

    # ------------------------------------------------------------------
    # (b) Known showcase rows appear with the right kind and state
    # ------------------------------------------------------------------
    def test_hearing_appears_as_a_hearing(self):
        row = self._row(self.hearing)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.kind, "hearing")
        self.assertEqual(row.date_due, self.hearing_date.date())
        self.assertEqual(row.state, "open")
        self.assertEqual(row.user_id, self.clerk)
        self.assertEqual(row.company_id, self.company)

    def test_overdue_obligation_appears_overdue(self):
        row = self._row(self.instance)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.kind, "obligation")
        self.assertEqual(row.date_due, self.instance.due_on)
        self.assertEqual(row.state, "overdue")
        self.assertIn("التزام اختبار شهري", row.name)

    def test_a_discharged_period_leaves_the_board(self):
        self.instance.action_mark_filed()
        self.env.flush_all()
        self.assertFalse(self._row(self.instance))

    # ------------------------------------------------------------------
    # (c) The one verb opens the source record
    # ------------------------------------------------------------------
    def test_open_origin_points_at_the_source(self):
        row = self._row(self.hearing)
        action = row.action_open_origin()
        self.assertEqual(action["res_model"], "legal.hearing")
        self.assertEqual(action["res_id"], self.hearing.id)
        self.assertEqual(action["view_mode"], "form")

    # ------------------------------------------------------------------
    # (d) The auditor reads everything and writes nothing
    # ------------------------------------------------------------------
    def test_auditor_can_read(self):
        rows = self.env["legal.deadline"].with_user(self.auditor).search([])
        self.assertTrue(rows)
        # Reading the projected columns must not raise.
        rows[0].read(["name", "kind", "date_due", "state"])

    def test_auditor_cannot_write(self):
        row = self.env["legal.deadline"].with_user(self.auditor).search([], limit=1)
        self.assertTrue(row)
        with self.assertRaises((AccessError, UserError)):
            row.write({"name": "معدل"})

    def test_clerk_cannot_write_either(self):
        row = self.env["legal.deadline"].with_user(self.clerk).search([], limit=1)
        self.assertTrue(row)
        with self.assertRaises((AccessError, UserError)):
            row.write({"state": "done"})

    # ------------------------------------------------------------------
    # (e) The company fence holds on the projection
    # ------------------------------------------------------------------
    def test_company_scoping(self):
        Deadline = self.env["legal.deadline"].with_user(self.clerk)
        own = Deadline.search(
            [
                ("res_model", "=", "legal.obligation.instance"),
                ("res_id", "=", self.instance.id),
            ]
        )
        self.assertTrue(own, "A clerk must see their own company's deadlines.")
        fenced = Deadline.search(
            [
                ("res_model", "=", "legal.obligation.instance"),
                ("res_id", "=", self.instance_b.id),
            ]
        )
        self.assertFalse(fenced, "Another company's deadline must be invisible.")
