from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestLegalRequest(TransactionCase):
    """The intake lifecycle, its gates and its clock.

    The suite is deliberately built around the separation of duties, because that
    is the whole point of an intake desk: a clerk who could approve their own
    answer, or an auditor who could edit the record they are meant to check,
    would make the register worthless.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.category = cls.env["legal.request.category"].create(
            {"name": "Legal Consultation", "code": "TEST-CONSULT"}
        )

        cls.clerk = new_test_user(
            cls.env, "req_clerk", groups="legal_core.group_legal_clerk"
        )
        cls.officer = new_test_user(
            cls.env, "req_officer", groups="legal_core.group_legal_officer"
        )
        cls.approver = new_test_user(
            cls.env, "req_approver", groups="legal_core.group_legal_approver"
        )
        cls.manager = new_test_user(
            cls.env, "req_manager", groups="legal_core.group_legal_manager"
        )
        cls.auditor = new_test_user(
            cls.env, "req_auditor", groups="legal_core.group_legal_auditor"
        )

    def _make_request(self, user=None, **values):
        base = {
            "subject": "Review of a supply contract",
            "category_id": self.category.id,
            "requesting_department": "Finance",
            "company_id": self.company.id,
        }
        base.update(values)
        model = self.env["legal.request"]
        if user is not None:
            model = model.with_user(user)
        return model.create(base)

    # ------------------------------------------------------------------
    # (a) The auditor is read-only through every path
    # ------------------------------------------------------------------
    def test_auditor_cannot_create(self):
        with self.assertRaises(AccessError):
            self._make_request(user=self.auditor)

    def test_auditor_cannot_write(self):
        request = self._make_request(user=self.clerk)
        with self.assertRaises(AccessError):
            request.with_user(self.auditor).write({"subject": "tampered"})

    def test_auditor_cannot_unlink(self):
        request = self._make_request(user=self.clerk)
        with self.assertRaises(AccessError):
            request.with_user(self.auditor).unlink()

    def test_auditor_may_read(self):
        request = self._make_request(user=self.clerk)
        # No raise: the auditor sees everything and mutates nothing.
        self.assertEqual(request.with_user(self.auditor).subject, request.subject)

    # ------------------------------------------------------------------
    # (b) A clerk cannot perform a gated action
    # ------------------------------------------------------------------
    def test_clerk_cannot_triage(self):
        request = self._make_request(user=self.clerk, state="received")
        with self.assertRaises(UserError):
            request.with_user(self.clerk).action_triage()

    def test_clerk_cannot_approve(self):
        request = self._make_request(
            user=self.clerk,
            state="ready_for_approval",
            response="<p>The clause is sound.</p>",
        )
        with self.assertRaises(UserError):
            request.with_user(self.clerk).action_approve()

    def test_officer_cannot_approve(self):
        """Approval is an approver's job, and an officer is below that rung."""
        request = self._make_request(
            user=self.clerk,
            state="ready_for_approval",
            response="<p>The clause is sound.</p>",
        )
        with self.assertRaises(UserError):
            request.with_user(self.officer).action_approve()

    def test_approver_may_approve(self):
        request = self._make_request(
            user=self.clerk,
            state="ready_for_approval",
            response="<p>The clause is sound.</p>",
        )
        request.with_user(self.approver)._apply_approval("approved", "Cleared.")
        self.assertEqual(request.state, "approved")
        self.assertEqual(request.approved_by_id, self.approver)
        self.assertTrue(request.approved_on)

    # ------------------------------------------------------------------
    # (c) Core transitions and the reference allocation
    # ------------------------------------------------------------------
    def test_submit_allocates_a_reference(self):
        request = self._make_request(user=self.clerk)
        self.assertEqual(request.state, "draft")
        self.assertEqual(request.reference, "New")
        request.with_user(self.clerk).action_submit()
        self.assertEqual(request.state, "received")
        self.assertTrue(request.reference.startswith("REQ/"))

    def test_a_request_created_into_the_queue_takes_a_number_at_once(self):
        request = self._make_request(user=self.clerk, state="received")
        self.assertTrue(request.reference.startswith("REQ/"))

    def test_assign_requires_an_officer(self):
        request = self._make_request(user=self.clerk, state="triage")
        with self.assertRaises(UserError):
            request.with_user(self.officer).action_assign()
        request.assigned_officer_id = self.officer
        request.with_user(self.officer).action_assign()
        self.assertEqual(request.state, "assigned")

    def test_cannot_submit_for_approval_with_no_response(self):
        request = self._make_request(user=self.clerk, state="in_progress")
        with self.assertRaises(UserError):
            request.with_user(self.officer).action_submit_for_approval()
        request.response = "<p>Here is the answer.</p>"
        request.with_user(self.officer).action_submit_for_approval()
        self.assertEqual(request.state, "ready_for_approval")

    def test_full_walk_to_closed(self):
        request = self._make_request(user=self.clerk, assigned_officer_id=self.officer.id)
        request.with_user(self.clerk).action_submit()
        request.with_user(self.officer).action_triage()
        request.with_user(self.officer).action_assign()
        request.with_user(self.officer).action_start()
        request.response = "<p>The answer.</p>"
        request.with_user(self.officer).action_submit_for_approval()
        request.with_user(self.approver)._apply_approval("approved", "Cleared.")
        request.with_user(self.officer).action_close()
        self.assertEqual(request.state, "closed")

    # ------------------------------------------------------------------
    # The overdue / age clock
    # ------------------------------------------------------------------
    def test_overdue_is_true_only_while_open_and_past_target(self):
        today = fields.Date.context_today(self.env["legal.request"])
        request = self._make_request(
            user=self.clerk,
            state="in_progress",
            request_date=today - timedelta(days=10),
            target_response_date=today - timedelta(days=3),
        )
        self.assertTrue(request.is_overdue)
        # Closing it stops the clock, even though the date is still in the past.
        request.state = "closed"
        request.invalidate_recordset(["is_overdue"])
        self.assertFalse(request.is_overdue)

    def test_overdue_search_matches_the_compute(self):
        today = fields.Date.context_today(self.env["legal.request"])
        late = self._make_request(
            user=self.clerk,
            state="in_progress",
            request_date=today - timedelta(days=10),
            target_response_date=today - timedelta(days=1),
        )
        on_time = self._make_request(
            user=self.clerk,
            state="in_progress",
            target_response_date=today + timedelta(days=5),
        )
        found = self.env["legal.request"].search([("is_overdue", "=", True)])
        self.assertIn(late, found)
        self.assertNotIn(on_time, found)

    def test_age_counts_days_since_the_request_date(self):
        today = fields.Date.context_today(self.env["legal.request"])
        request = self._make_request(
            user=self.clerk, state="received", request_date=today - timedelta(days=4)
        )
        self.assertEqual(request.age, 4)

    # ------------------------------------------------------------------
    # (d) A constraint
    # ------------------------------------------------------------------
    def test_target_cannot_precede_the_request_date(self):
        today = fields.Date.context_today(self.env["legal.request"])
        with self.assertRaises(ValidationError):
            self._make_request(
                user=self.clerk,
                request_date=today,
                target_response_date=today - timedelta(days=2),
            )

    # ------------------------------------------------------------------
    # Cancellation needs a reason; a numbered request is not deletable
    # ------------------------------------------------------------------
    def test_cancel_requires_a_reason(self):
        request = self._make_request(user=self.clerk, state="received")
        wizard = (
            self.env["legal.request.cancel"]
            .with_user(self.officer)
            .create({"request_id": request.id, "reason": "  "})
        )
        with self.assertRaises(UserError):
            wizard.action_confirm()
        wizard.reason = "Duplicate of REQ/2026/0004."
        wizard.action_confirm()
        self.assertEqual(request.state, "cancelled")
        self.assertEqual(request.cancel_reason, "Duplicate of REQ/2026/0004.")

    def test_a_numbered_request_cannot_be_deleted(self):
        request = self._make_request(user=self.clerk, state="received")
        with self.assertRaises(UserError):
            request.with_user(self.manager).unlink()

    # ------------------------------------------------------------------
    # The correspondence edge
    # ------------------------------------------------------------------
    def test_convert_is_gated_to_officer(self):
        request = self._make_request(user=self.clerk, state="received")
        with self.assertRaises(UserError):
            request.with_user(self.clerk).action_convert()
        action = request.with_user(self.officer).action_convert()
        self.assertEqual(action["res_model"], "legal.correspondence")
        self.assertEqual(action["context"]["default_request_id"], request.id)
