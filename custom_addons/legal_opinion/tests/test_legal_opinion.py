from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestLegalOpinion(TransactionCase):
    """The advisory workflow: gated issue, the freeze, the register number,
    the revision chain, and the auditor who may touch nothing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.clerk = new_test_user(
            cls.env,
            login="opn_clerk",
            groups="base.group_user,legal_core.group_legal_clerk",
            company_id=cls.company.id,
        )
        cls.officer = new_test_user(
            cls.env,
            login="opn_officer",
            groups="base.group_user,legal_core.group_legal_officer",
            company_id=cls.company.id,
        )
        cls.approver = new_test_user(
            cls.env,
            login="opn_approver",
            groups="base.group_user,legal_core.group_legal_approver",
            company_id=cls.company.id,
        )
        cls.manager = new_test_user(
            cls.env,
            login="opn_manager",
            groups="base.group_user,legal_core.group_legal_manager",
            company_id=cls.company.id,
        )
        cls.auditor = new_test_user(
            cls.env,
            login="opn_auditor",
            groups="base.group_user,legal_core.group_legal_auditor",
            company_id=cls.company.id,
        )

    def _new_opinion(self, user=None, **overrides):
        values = {
            "subject": "Enforceability of a penalty clause",
            "requesting_department": "Procurement",
            "legal_officer_id": self.officer.id,
            "analysis": "<p>Reasoning.</p>",
            "conclusion": "<p>The answer.</p>",
        }
        values.update(overrides)
        model = self.env["legal.opinion"]
        if user is not None:
            model = model.with_user(user)
        return model.create(values)

    def _drive_to_approval(self, opinion):
        opinion.action_assign()
        opinion.action_start_drafting()
        opinion.action_submit_review()
        opinion.action_request_approval()
        return opinion

    # ------------------------------------------------------------------
    # Reference allocation
    # ------------------------------------------------------------------
    def test_reference_allocated(self):
        opinion = self._new_opinion()
        self.assertTrue(opinion.name.startswith("OPN/"))
        self.assertNotEqual(opinion.name, "New")

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------
    def test_forward_transitions(self):
        opinion = self._new_opinion()
        self.assertEqual(opinion.state, "received")
        self._drive_to_approval(opinion)
        self.assertEqual(opinion.state, "approval")

    def test_assign_requires_officer(self):
        opinion = self._new_opinion(legal_officer_id=False)
        with self.assertRaises(UserError):
            opinion.action_assign()

    def test_out_of_order_transition_refused(self):
        opinion = self._new_opinion()
        # Cannot request approval straight from received.
        with self.assertRaises(UserError):
            opinion.action_request_approval()

    # ------------------------------------------------------------------
    # The gate: only an approver issues
    # ------------------------------------------------------------------
    def test_clerk_cannot_issue(self):
        opinion = self._new_opinion()
        self._drive_to_approval(opinion)
        with self.assertRaises(UserError):
            opinion.with_user(self.clerk).action_approve_issue()

    def test_officer_cannot_issue(self):
        opinion = self._new_opinion()
        self._drive_to_approval(opinion)
        with self.assertRaises(UserError):
            opinion.with_user(self.officer).action_approve_issue()

    def test_approver_issues_and_freezes(self):
        opinion = self._new_opinion(approver_id=self.approver.id)
        self._drive_to_approval(opinion)
        opinion.with_user(self.approver).action_approve_issue()
        opinion.invalidate_recordset()
        self.assertEqual(opinion.state, "issued")
        self.assertTrue(opinion.issued_date)
        self.assertTrue(opinion.snapshot_html)
        # The snapshot carries both the analysis and the conclusion text.
        self.assertIn("The answer.", opinion.snapshot_html)
        # A register number was booked.
        self.assertTrue(opinion.register_correspondence_id)
        self.assertTrue(opinion.register_number)
        self.assertEqual(opinion.correspondence_count, 1)
        self.assertEqual(
            opinion.register_correspondence_id.opinion_id, opinion
        )

    # ------------------------------------------------------------------
    # The freeze
    # ------------------------------------------------------------------
    def test_frozen_after_issue(self):
        opinion = self._new_opinion(approver_id=self.approver.id)
        self._drive_to_approval(opinion)
        opinion.with_user(self.approver).action_approve_issue()
        with self.assertRaises(UserError):
            opinion.write({"conclusion": "<p>A different answer.</p>"})
        with self.assertRaises(UserError):
            opinion.write({"analysis": "<p>Rewritten.</p>"})

    def test_issued_cannot_be_deleted(self):
        opinion = self._new_opinion(approver_id=self.approver.id)
        self._drive_to_approval(opinion)
        opinion.with_user(self.approver).action_approve_issue()
        with self.assertRaises(UserError):
            opinion.unlink()

    def test_issue_requires_conclusion(self):
        opinion = self._new_opinion(conclusion=False, analysis="<p>Only analysis.</p>")
        self._drive_to_approval(opinion)
        with self.assertRaises(UserError):
            opinion.with_user(self.approver).action_approve_issue()

    # ------------------------------------------------------------------
    # Revision chain
    # ------------------------------------------------------------------
    def test_revision_supersedes(self):
        opinion = self._new_opinion(approver_id=self.approver.id)
        self._drive_to_approval(opinion)
        opinion.with_user(self.approver).action_approve_issue()
        action = opinion.action_revise()
        revision = self.env["legal.opinion"].browse(action["res_id"])
        self.assertEqual(revision.supersedes_id, opinion)
        self.assertEqual(opinion.superseded_by_id, revision)
        self.assertEqual(revision.state, "drafting")
        self.assertFalse(opinion.is_current)
        self.assertTrue(revision.is_current)
        # A second revision of the same (now superseded) opinion is refused.
        with self.assertRaises(UserError):
            opinion.action_revise()

    def test_cannot_revise_a_draft(self):
        opinion = self._new_opinion()
        with self.assertRaises(UserError):
            opinion.action_revise()

    # ------------------------------------------------------------------
    # Overdue logic
    # ------------------------------------------------------------------
    def test_overdue_compute_and_search(self):
        today = date.today()
        overdue = self._new_opinion(
            subject="Overdue one", due_date=today - timedelta(days=3)
        )
        not_due = self._new_opinion(
            subject="Future one", due_date=today + timedelta(days=10)
        )
        self.assertTrue(overdue.is_overdue)
        self.assertFalse(not_due.is_overdue)
        found = self.env["legal.opinion"].search(
            [("is_overdue", "=", True), ("id", "in", (overdue + not_due).ids)]
        )
        self.assertIn(overdue, found)
        self.assertNotIn(not_due, found)

    def test_issued_is_never_overdue(self):
        opinion = self._new_opinion(
            approver_id=self.approver.id, due_date=date.today() - timedelta(days=5)
        )
        self._drive_to_approval(opinion)
        opinion.with_user(self.approver).action_approve_issue()
        self.assertFalse(opinion.is_overdue)

    # ------------------------------------------------------------------
    # The auditor may touch nothing
    # ------------------------------------------------------------------
    def test_auditor_cannot_create(self):
        with self.assertRaises(AccessError):
            self._new_opinion(user=self.auditor)

    def test_auditor_cannot_write(self):
        opinion = self._new_opinion()
        with self.assertRaises(AccessError):
            opinion.with_user(self.auditor).write({"subject": "Tampered"})

    def test_auditor_can_read(self):
        opinion = self._new_opinion()
        # A read must not raise for the auditor.
        subject = opinion.with_user(self.auditor).subject
        self.assertEqual(subject, opinion.subject)
