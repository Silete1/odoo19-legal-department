from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests.common import tagged

from .common import LegalProcedureCommon


@tagged("post_install", "-at_install")
class TestObligations(LegalProcedureCommon):
    """Recurring deadlines: a row with a state, never a computed absence."""

    def test_a_fixed_annual_date_generates_one_row_per_year(self):
        schedule = self.env["legal.obligation.schedule"].create(
            {
                "name": "الإقرار الضريبي السنوي",
                "code": "TEST-GCT-ANNUAL",
                "body_id": self.other_body.id,
                "entity_id": self.entity.id,
                "frequency": "fixed_annual_date",
                "due_month": 5,
                "due_day": 31,
                "lead_days": 30,
                "penalty_note": "10% of the tax capped at IQD 500,000",
            }
        )
        created = schedule._generate()
        self.assertTrue(created)
        self.assertTrue(schedule.instance_ids)
        for instance in schedule.instance_ids:
            self.assertEqual(instance.due_on.month, 5)
            self.assertEqual(instance.due_on.day, 31)
            self.assertEqual(instance.state, "not_started")
            self.assertLess(instance.start_by_date, instance.due_on)
            self.assertEqual(instance.penalty_note, schedule.penalty_note)

    def test_generation_is_idempotent(self):
        """The whole point of the unique index: a second pass writes nothing."""
        schedule = self.env["legal.obligation.schedule"].create(
            {
                "name": "اشتراك الضمان الاجتماعي",
                "code": "TEST-PSSO-MONTHLY",
                "body_id": self.other_body.id,
                "entity_id": self.entity.id,
                "frequency": "monthly",
                "due_day": 10,
            }
        )
        schedule._generate()
        first = len(schedule.instance_ids)
        self.assertTrue(first)
        self.assertEqual(schedule._generate(), 0)
        schedule.invalidate_recordset()
        self.assertEqual(len(schedule.instance_ids), first)

    def test_a_day_beyond_the_month_is_clamped(self):
        schedule = self.env["legal.obligation.schedule"].create(
            {
                "name": "شيء يستحق آخر الشهر",
                "code": "TEST-EOM",
                "body_id": self.other_body.id,
                "entity_id": self.entity.id,
                "frequency": "monthly",
                "due_day": 31,
            }
        )
        schedule._generate()
        februaries = schedule.instance_ids.filtered(lambda row: row.due_on.month == 2)
        for instance in februaries:
            self.assertIn(instance.due_on.day, (28, 29))

    def test_a_period_opens_the_file_that_discharges_it(self):
        schedule = self.env["legal.obligation.schedule"].create(
            {
                "name": "إقرار سنوي",
                "code": "TEST-ANNUAL-CASE",
                "body_id": self.body.id,
                "entity_id": self.entity.id,
                "procedure_type_id": self.procedure.id,
                "frequency": "fixed_annual_date",
                "due_month": 5,
                "due_day": 31,
            }
        )
        schedule._generate()
        instance = schedule.instance_ids[0]
        instance.action_open_case()
        self.assertTrue(instance.case_id)
        self.assertEqual(instance.state, "in_progress")
        # The period key travels with the file rather than being matched up later
        # by date arithmetic across a year end and a Hijri holiday.
        self.assertEqual(instance.case_id.period_key, instance.period_key)
        self.assertEqual(instance.case_id.date_deadline, instance.due_on)

    def test_a_past_due_period_is_marked_late_rather_than_left_looking_clean(self):
        schedule = self.env["legal.obligation.schedule"].create(
            {
                "name": "شيء فات موعده",
                "code": "TEST-LATE",
                "body_id": self.other_body.id,
                "entity_id": self.entity.id,
                "frequency": "fixed_annual_date",
                "due_month": 1,
                "due_day": 1,
            }
        )
        instance = self.env["legal.obligation.instance"].create(
            {
                "schedule_id": schedule.id,
                "period_key": "TEST-OVERDUE",
                "due_on": fields.Date.context_today(schedule) - relativedelta(days=10),
                "entity_id": self.entity.id,
                "company_id": self.company.id,
            }
        )
        self.env["legal.obligation.instance"]._cron_mark_late()
        self.assertEqual(instance.state, "late")

    def test_the_same_period_cannot_be_recorded_twice(self):
        schedule = self.env["legal.obligation.schedule"].create(
            {
                "name": "فريد",
                "code": "TEST-UNIQUE",
                "body_id": self.other_body.id,
                "entity_id": self.entity.id,
                "frequency": "fixed_annual_date",
            }
        )
        values = {
            "schedule_id": schedule.id,
            "period_key": "2026",
            "due_on": fields.Date.context_today(schedule),
            "company_id": self.company.id,
        }
        self.env["legal.obligation.instance"].create(values)
        self.env["legal.obligation.instance"].flush_model()
        with self.assertRaises(Exception):
            self.env["legal.obligation.instance"].create(values)
            self.env["legal.obligation.instance"].flush_model()
