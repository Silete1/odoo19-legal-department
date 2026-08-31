from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import LegalLitigationCommon


@tagged("post_install", "-at_install")
class TestLitigation(LegalLitigationCommon):
    """The lifecycle, the filing gate, the appeal window and the duties."""

    # ------------------------------------------------------------------
    # (a) The auditor is read-only through every path
    # ------------------------------------------------------------------
    def test_auditor_cannot_create_a_lawsuit(self):
        with self.assertRaises(AccessError):
            self.env["legal.lawsuit"].with_user(self.auditor).create(
                {
                    "title": "محاولة إنشاء",
                    "entity_id": self.entity.id,
                    "company_id": self.company.id,
                }
            )

    def test_auditor_cannot_write_a_lawsuit(self):
        lawsuit = self._make_lawsuit()
        with self.assertRaises(AccessError):
            lawsuit.with_user(self.auditor).write({"title": "معدّل"})

    def test_auditor_cannot_write_a_judgment(self):
        lawsuit = self._make_lawsuit()
        judgment = self.env["legal.judgment"].create(
            {"lawsuit_id": lawsuit.id, "court_id": self.court.id}
        )
        with self.assertRaises(AccessError):
            judgment.with_user(self.auditor).write({"summary": "x"})

    # ------------------------------------------------------------------
    # (b) A clerk cannot perform the approver-gated close
    # ------------------------------------------------------------------
    def test_clerk_cannot_close_a_case(self):
        # A case in a post-filing state carries its court and number - the
        # filed-has-court constraint insists on it.
        lawsuit = self._make_lawsuit(
            court_id=self.court.id, court_case_number="55/2026"
        )
        lawsuit.state = "in_progress"
        with self.assertRaises(UserError):
            lawsuit.with_user(self.clerk).action_close()

    def test_approver_may_close_a_case(self):
        lawsuit = self._make_lawsuit(
            court_id=self.court.id, court_case_number="56/2026"
        )
        lawsuit.state = "judgment"
        # The wizard is what an approver confirms; it carries the reason.
        wizard = (
            self.env["legal.lawsuit.reason"]
            .with_user(self.approver)
            .create(
                {
                    "lawsuit_id": lawsuit.id,
                    "action_kind": "close",
                    "reason": "تسوية ودية",
                }
            )
        )
        wizard.action_confirm()
        self.assertEqual(lawsuit.state, "closed")
        self.assertTrue(lawsuit.is_closed)
        self.assertEqual(lawsuit.close_reason, "تسوية ودية")

    def test_clerk_cannot_close_through_the_wizard_either(self):
        """The gate is server-side, so the wizard path is closed to a clerk too."""
        lawsuit = self._make_lawsuit(
            court_id=self.court.id, court_case_number="57/2026"
        )
        lawsuit.state = "in_progress"
        wizard = (
            self.env["legal.lawsuit.reason"]
            .with_user(self.clerk)
            .create(
                {
                    "lawsuit_id": lawsuit.id,
                    "action_kind": "close",
                    "reason": "محاولة",
                }
            )
        )
        with self.assertRaises(UserError):
            wizard.action_confirm()

    # ------------------------------------------------------------------
    # (c) The lifecycle and the filing gate
    # ------------------------------------------------------------------
    def test_a_new_case_is_numbered_and_starts_at_assessment(self):
        lawsuit = self._make_lawsuit()
        self.assertNotEqual(lawsuit.reference, "New")
        self.assertTrue(lawsuit.reference.startswith("LAW/"))
        self.assertEqual(lawsuit.state, "assessment")

    def test_filing_is_blocked_without_a_court_and_number(self):
        lawsuit = self._make_lawsuit()
        lawsuit.action_prepare()
        with self.assertRaises(UserError):
            lawsuit.action_file()
        self.assertEqual(lawsuit.state, "preparation")

    def test_filing_is_blocked_without_a_valid_litigation_poa(self):
        lawsuit = self._make_lawsuit(
            court_id=self.court.id, court_case_number="100/2026"
        )
        # An advocate with no litigation deed at all.
        stranger = self._make_user("lit_stranger", "legal_core.group_legal_clerk")
        lawsuit.lawyer_id = stranger
        lawsuit.action_prepare()
        with self.assertRaises(UserError):
            lawsuit.action_file()

    def test_filing_succeeds_with_court_number_and_a_valid_poa(self):
        lawsuit = self._make_lawsuit(
            court_id=self.court.id,
            court_case_number="145/2026",
            poa_id=self.poa.id,
        )
        lawsuit.action_prepare()
        lawsuit.action_file()
        self.assertEqual(lawsuit.state, "filed")
        self.assertTrue(lawsuit.date_filed)
        lawsuit.action_start()
        self.assertEqual(lawsuit.state, "in_progress")
        lawsuit.action_to_judgment()
        self.assertEqual(lawsuit.state, "judgment")

    def test_the_poa_is_auto_found_when_not_named(self):
        """A valid litigation deed for the advocate is found even if not chosen."""
        lawsuit = self._make_lawsuit(
            court_id=self.court.id, court_case_number="200/2026"
        )
        lawsuit.action_prepare()
        lawsuit.action_file()
        self.assertEqual(lawsuit.poa_id, self.poa)

    # ------------------------------------------------------------------
    # (c) The appeal-window engine
    # ------------------------------------------------------------------
    def test_appeal_deadline_is_notification_plus_the_rule(self):
        lawsuit = self._make_lawsuit(court_id=self.court.id)
        tabligh = fields.Date.context_today(lawsuit)
        judgment = self.env["legal.judgment"].create(
            {
                "lawsuit_id": lawsuit.id,
                "court_id": self.court.id,
                "judgment_date": tabligh,
                "ruling_type": "judgment",
                "remedy": "appeal",
                "tabligh_date": tabligh,
            }
        )
        self.assertEqual(judgment.appeal_rule_id, self.appeal_rule)
        self.assertEqual(
            judgment.appeal_deadline, tabligh + timedelta(days=15)
        )
        self.assertEqual(judgment.appeal_state, "open")
        self.assertFalse(judgment.is_overdue)

    def test_a_lapsed_window_is_overdue(self):
        lawsuit = self._make_lawsuit(court_id=self.court.id)
        long_ago = fields.Date.context_today(lawsuit) - timedelta(days=40)
        judgment = self.env["legal.judgment"].create(
            {
                "lawsuit_id": lawsuit.id,
                "court_id": self.court.id,
                "remedy": "appeal",
                "ruling_type": "judgment",
                "tabligh_date": long_ago,
            }
        )
        self.assertTrue(judgment.appeal_deadline < fields.Date.context_today(lawsuit))
        self.assertEqual(judgment.appeal_state, "closed")
        self.assertTrue(judgment.is_overdue)

    def test_lodging_a_challenge_stops_the_clock(self):
        lawsuit = self._make_lawsuit(court_id=self.court.id)
        tabligh = fields.Date.context_today(lawsuit)
        judgment = self.env["legal.judgment"].create(
            {
                "lawsuit_id": lawsuit.id,
                "court_id": self.court.id,
                "remedy": "appeal",
                "ruling_type": "judgment",
                "tabligh_date": tabligh,
            }
        )
        judgment.action_mark_appealed()
        self.assertTrue(judgment.appeal_filed)
        self.assertEqual(judgment.appeal_state, "filed")
        self.assertFalse(judgment.is_overdue)

    def test_next_deadline_reflects_an_open_window(self):
        lawsuit = self._make_lawsuit(court_id=self.court.id)
        tabligh = fields.Date.context_today(lawsuit)
        self.env["legal.judgment"].create(
            {
                "lawsuit_id": lawsuit.id,
                "court_id": self.court.id,
                "remedy": "appeal",
                "ruling_type": "judgment",
                "tabligh_date": tabligh,
            }
        )
        self.assertTrue(lawsuit.appeal_window_open)
        self.assertEqual(lawsuit.next_deadline, tabligh + timedelta(days=15))

    # ------------------------------------------------------------------
    # (c) Hearings breed the next one, once
    # ------------------------------------------------------------------
    def test_next_hearing_date_is_the_earliest_pending_sitting(self):
        lawsuit = self._make_lawsuit(court_id=self.court.id)
        now = fields.Datetime.now()
        self.env["legal.hearing"].create(
            {
                "lawsuit_id": lawsuit.id,
                "date": now - timedelta(days=5),
                "result": "أُجّلت",
            }
        )
        upcoming = self.env["legal.hearing"].create(
            {"lawsuit_id": lawsuit.id, "date": now + timedelta(days=7)}
        )
        self.assertEqual(lawsuit.next_hearing_date, upcoming.date)

    def test_setting_the_next_date_rolls_one_sitting_forward_only_once(self):
        lawsuit = self._make_lawsuit(court_id=self.court.id)
        now = fields.Datetime.now()
        hearing = self.env["legal.hearing"].create(
            {
                "lawsuit_id": lawsuit.id,
                "date": now,
                "next_hearing_date": now + timedelta(days=14),
            }
        )
        self.assertTrue(hearing.next_hearing_id)
        child = hearing.next_hearing_id
        # Re-running the roll-forward makes no second child.
        hearing._roll_forward()
        self.assertEqual(hearing.next_hearing_id, child)
        self.assertEqual(
            self.env["legal.hearing"].search_count(
                [("lawsuit_id", "=", lawsuit.id)]
            ),
            2,
        )

    # ------------------------------------------------------------------
    # (d) Constraints
    # ------------------------------------------------------------------
    def test_a_filed_case_must_have_a_court(self):
        lawsuit = self._make_lawsuit()
        with self.assertRaises(ValidationError):
            lawsuit.write({"state": "filed"})

    def test_a_claim_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self._make_lawsuit(claim_amount=-1)

    def test_a_court_cannot_be_its_own_appeal_court(self):
        with self.assertRaises(ValidationError):
            self.court.parent_court_id = self.court
