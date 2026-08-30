# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The time control layer.

Time is frozen throughout: a test that reads the real clock passes on a Tuesday
and fails on a Sunday, and a service level is entirely about *when*.
"""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import freeze_time, tagged
from odoo.tools import mute_logger

from .common import DmaAccreditationCommon

#: Every test in this file starts here, so a target of "3 days" is a date
#: anybody reading the assertions can work out in their head.
DAY_ONE = "2026-03-02 08:00:00"


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationSla(DmaAccreditationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.rule_gd = cls.env.ref("dma_accreditation.sla_rule_gd_review")
        cls.rule_finance = cls.env.ref("dma_accreditation.sla_rule_dual_confirm_finance")
        cls.rule_operations = cls.env.ref(
            "dma_accreditation.sla_rule_dual_confirm_operations"
        )

    def _at(self, moment):
        return freeze_time(moment)

    def _refresh(self, request):
        """Throw the cached verdict away: the clock has moved."""
        request.invalidate_recordset()
        return request

    def _drive_to_gd_review(self, request):
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        return request

    # ==================================================================
    # Where the clock starts
    # ==================================================================
    def test_01_stage_entry_is_read_off_the_approval_log(self):
        with self._at(DAY_ONE):
            request = self._new_request()
            self.assertEqual(
                request.stage_entered_on, request.create_date,
                "a file that has never moved arrived when it was created",
            )
        with self._at("2026-03-04 10:00:00"):
            self._as(request, self.user_reception).action_submit()
        with self._at("2026-03-05 09:30:00"):
            self._as(request, self.user_reception).action_send_to_general_director()

        self.assertEqual(request.state, "gd_review")
        self.assertEqual(
            fields.Datetime.to_string(request.stage_entered_on),
            "2026-03-05 09:30:00",
            "the file reached the General Director when the previous step closed",
        )

    def test_02_the_dual_confirmation_signatures_do_not_restart_the_clock(self):
        """The one step that writes log entries without the file moving."""
        with self._at(DAY_ONE):
            request = self._drive_to_dual_confirm(self._new_request())
        arrival = request.stage_entered_on

        with self._at("2026-03-04 12:00:00"):
            self._as(request, self.user_finance).action_finance_confirm()
        self._refresh(request)
        self.assertEqual(
            request.stage_entered_on, arrival,
            "Finance signing is a decision taken on the step, not an arrival",
        )
        self.assertEqual(request.state, "dual_confirm")

    def test_03_the_process_history_and_the_stage_clock_tell_the_same_story(self):
        with self._at(DAY_ONE):
            request = self._drive_to_office_granted(self._new_request())
        visits = request._process_visits()
        self.assertTrue(visits[-1]["open"], "the last visit is where the file is")
        self.assertEqual(visits[-1]["step"], request.state)
        self.assertEqual(
            visits[-1]["entered_on"], request.stage_entered_on,
            "one reconstruction of the history, not two",
        )
        # Every completed visit has a duration and closed exactly one step.
        for visit in visits[:-1]:
            self.assertTrue(visit["left_on"])
            self.assertGreaterEqual(visit["hours"], 0.0)
        self.assertEqual(
            [visit["step"] for visit in visits],
            ["draft", "submitted", "gd_review", "legal_review", "cert_check",
             "office_granted"],
            "and it is the path the file actually took",
        )

    def test_04_a_returned_file_that_comes_back_records_two_visits(self):
        with self._at(DAY_ONE):
            request = self._new_request()
            self._as(request, self.user_reception).action_submit()
            self._as(request, self.user_reception).action_send_to_general_director()
        with self._at("2026-03-06 09:00:00"):
            self._as(request, self.user_gd).action_return_to_applicant("Incomplete file.")
        with self._at("2026-03-10 09:00:00"):
            self._as(request, self.user_reception).action_resume_from_return()

        self.assertEqual(request.state, "submitted")
        steps = [visit["step"] for visit in request._process_visits()]
        self.assertEqual(steps.count("submitted"), 2, "it came round a second time")
        self.assertEqual(
            fields.Datetime.to_string(request.stage_entered_on),
            "2026-03-10 09:00:00",
            "and the second visit starts a fresh clock",
        )

    # ==================================================================
    # The verdict
    # ==================================================================
    def test_05_on_track_warning_overdue_and_escalated(self):
        # Initial acceptance: target 3 days, warn 1 day before, escalate 2 after.
        self.assertEqual(self.rule_gd.target_days, 3)
        self.assertEqual(self.rule_gd.warning_days, 1)
        self.assertEqual(self.rule_gd.escalation_days, 2)

        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
            self.assertEqual(request.sla_state, "on_track")
            self.assertEqual(
                fields.Datetime.to_string(request.sla_due_on), "2026-03-05 08:00:00",
            )
            self.assertEqual(request.sla_blocking_role, "general_director")

        for moment, expected in (
            ("2026-03-03 23:00:00", "on_track"),   # more than a day to go
            ("2026-03-04 09:00:00", "warning"),    # inside the warning window
            ("2026-03-05 09:00:00", "overdue"),    # past the target
            ("2026-03-07 09:00:00", "escalated"),  # past target + escalation
        ):
            with self.subTest(moment=moment), self._at(moment):
                self._refresh(request)
                self.assertEqual(request.sla_state, expected)

        with self._at("2026-03-08 08:00:00"):
            self._refresh(request)
            self.assertAlmostEqual(request.sla_overdue_hours, 72.0, places=1)
            self.assertEqual(request.stage_age_display, "6 day(s)")

    def test_06_a_step_with_no_service_level_is_not_applicable(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
            self.rule_gd.with_user(self.user_manager).write({"active": False})
            self._refresh(request)
            self.assertEqual(request.sla_state, "not_applicable")
            self.assertFalse(request.sla_due_on)
            self.assertIn("No service level", request.sla_payload["due_label"])
        self.rule_gd.with_user(self.user_manager).write({"active": True})

    def test_07_a_returned_file_is_paused_and_a_closed_one_stops_counting(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        with self._at("2026-03-03 09:00:00"):
            self._as(request, self.user_gd).action_return_to_applicant("Please complete.")
        with self._at("2026-04-01 09:00:00"):
            self._refresh(request)
            self.assertEqual(
                request.sla_state, "paused",
                "the file is with the applicant; the Directorate is not late",
            )
            self.assertFalse(request.sla_due_on)
            self.assertIn("applicant", request.sla_payload["due_label"])

        # ... and a decided file owes nobody anything, however long ago it closed.
        with self._at(DAY_ONE):
            closed = self._new_request()
            self._as(closed, self.user_reception).action_submit()
            self._as(closed, self.user_reception).action_send_to_general_director()
            self._as(closed, self.user_gd).action_reject("Not eligible.")
        with self._at("2027-01-01 09:00:00"):
            self._refresh(closed)
            self.assertEqual(closed.state, "rejected")
            self.assertEqual(closed.sla_state, "not_applicable")
            self.assertEqual(closed.stage_age_hours, 0.0)

    def test_08_an_archived_file_is_off_the_clock(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        with self._at("2026-04-01 09:00:00"):
            request.with_user(self.user_manager).write({"active": False})
            self._refresh(request)
            self.assertEqual(request.sla_state, "not_applicable")

    # ==================================================================
    # The parallel step
    # ==================================================================
    def test_09_dual_confirmation_is_two_clocks_and_the_file_is_as_late_as_the_later(self):
        with self._at(DAY_ONE):
            request = self._drive_to_dual_confirm(self._new_request())
            self.assertEqual(request.state, "dual_confirm")
            verdict = request._sla_verdict()
            self.assertEqual(
                {party["role"] for party in verdict["parties"]},
                {"finance", "operations"},
                "both departments owe a move at the same time",
            )

        # Finance signs on time; Operations does not.
        with self._at("2026-03-03 08:00:00"):
            self._as(request, self.user_finance).action_finance_confirm()
        with self._at("2026-03-12 08:00:00"):
            self._refresh(request)
            verdict = request._sla_verdict()
            self.assertEqual(verdict["role"], "operations")
            self.assertEqual(request.sla_blocking_role, "operations")
            self.assertEqual(request.sla_state, "escalated")
            self.assertEqual(
                len(verdict["parties"]), 1,
                "Finance has signed and drops off the list of who is answerable",
            )
            # 10 days waiting, of which 1 was Finance's.
            self.assertAlmostEqual(request.finance_pending_hours, 24.0, places=1)
            self.assertAlmostEqual(request.operations_pending_hours, 240.0, places=1)

        with self._at("2026-03-13 08:00:00"):
            self._as(request, self.user_operations).action_operations_confirm()
        self._refresh(request)
        self.assertEqual(
            fields.Datetime.to_string(request.dual_confirm_first_on),
            "2026-03-03 08:00:00",
        )
        self.assertEqual(
            fields.Datetime.to_string(request.dual_confirm_second_on),
            "2026-03-13 08:00:00",
        )
        self.assertAlmostEqual(request.dual_confirm_hours, 264.0, places=1)

        # The timing survives the file moving on to the next step.
        with self._at("2026-03-14 08:00:00"):
            self._as(request, self.user_finance).action_dual_confirm_done()
        self._refresh(request)
        self.assertEqual(request.state, "demo_fee")
        self.assertAlmostEqual(
            request.dual_confirm_hours, 264.0, places=1,
            msg="the parallel timing is a fact about a step that is now behind it",
        )
        self.assertEqual(
            fields.Datetime.to_string(request.dual_confirm_started_on),
            "2026-03-02 08:00:00",
        )

    def test_10_the_badge_names_both_parties_on_the_parallel_step(self):
        with self._at(DAY_ONE):
            request = self._drive_to_dual_confirm(self._new_request())
        with self._at("2026-03-08 08:00:00"):
            self._refresh(request)
            payload = request.sla_payload
            self.assertEqual(len(payload["parties"]), 2)
            self.assertEqual(
                {party["role_key"] for party in payload["parties"]},
                {"finance", "operations"},
            )
            for party in payload["parties"]:
                self.assertTrue(party["state_label"], "colour is never on its own")
                self.assertTrue(party["icon"])

    # ==================================================================
    # Searching
    # ==================================================================
    def test_11_the_service_level_can_be_filtered_on(self):
        with self._at(DAY_ONE):
            late = self._drive_to_gd_review(self._new_request())
            fresh = self._drive_to_gd_review(self._new_request())
        with self._at("2026-03-06 09:00:00"):
            # `late` arrived on day one; `fresh` arrives now.
            fresh._workflow_write({"state": "submitted"})
            self._as(fresh, self.user_reception).action_send_to_general_director()
            self.env.invalidate_all()

            Request = self.env["dma.accreditation.request"]
            overdue = Request.search([("sla_state", "=", "overdue")])
            self.assertIn(late, overdue)
            self.assertNotIn(fresh, overdue)

            on_track = Request.search([("sla_state", "in", ["on_track"])])
            self.assertIn(fresh, on_track)
            self.assertNotIn(late, on_track)

            self.assertNotIn(late, Request.search([("sla_state", "!=", "overdue")]))
            with self.assertRaises(UserError):
                Request.search([("sla_state", "like", "over")])

    # ==================================================================
    # Reminders and escalation
    # ==================================================================
    def _sla_activities(self, request):
        return self.env["mail.activity"].sudo().search([
            ("res_model", "=", request._name),
            ("res_id", "=", request.id),
            ("activity_type_id", "=", self.env.ref(
                "dma_accreditation.mail_activity_type_sla"
            ).id),
        ])

    def test_12_the_cron_reminds_once_and_stays_idempotent(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        Request = self.env["dma.accreditation.request"]

        with self._at("2026-03-05 09:00:00"):        # overdue
            Request._cron_sla_review()
            activities = self._sla_activities(request)
            self.assertTrue(activities, "the responsible department is told")
            self.assertEqual(
                activities.mapped("user_id"),
                request._responsible_users("general_director"),
            )
            first = activities.ids
            summaries = activities.mapped("summary")

            # Run it again, and again: no second copy, nothing rewritten.
            Request._cron_sla_review()
            Request._cron_sla_review()
            again = self._sla_activities(request)
            self.assertEqual(again.ids, first, "no duplicate reminder")
            self.assertEqual(again.mapped("summary"), summaries)

            escalations = self.env["dma.sla.escalation"].search([
                ("request_id", "=", request.id),
            ])
            self.assertEqual(len(escalations), 1, "raised exactly once")
            self.assertEqual(escalations.level, "1")

    def test_13_escalation_reaches_the_manager_and_closes_when_the_file_moves(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        Request = self.env["dma.accreditation.request"]
        Escalation = self.env["dma.sla.escalation"]

        with self._at("2026-03-08 09:00:00"):        # past target + escalation
            Request._cron_sla_review()
            escalations = Escalation.search([("request_id", "=", request.id)])
            self.assertEqual(
                sorted(escalations.mapped("level")), ["1", "2"],
                "the department is warned and the manager is told",
            )
            self._refresh(request)
            self.assertEqual(request.escalation_level, "2")
            self.assertEqual(request.open_escalation_count, 2)
            manager_activity = self._sla_activities(request).filtered(
                lambda activity: activity.user_id in request._responsible_users("manager")
            )
            self.assertTrue(manager_activity, "and it lands on the manager's desk")

            Request._cron_sla_review()
            self.assertEqual(
                len(Escalation.search([("request_id", "=", request.id)])), 2,
                "a second run raises nothing new",
            )

        with self._at("2026-03-09 09:00:00"):
            self._as(request, self.user_gd).action_gd_accept()
            Request._cron_sla_review()
            escalations = Escalation.search([("request_id", "=", request.id)])
            self.assertTrue(
                all(escalation.resolved_on for escalation in escalations),
                "the step was dealt with, so its escalations close",
            )
            self._refresh(request)
            self.assertFalse(request.escalation_level)
            self.assertFalse(
                self._sla_activities(request),
                "and the reminder goes with the step it was about",
            )

    def test_14_a_second_visit_to_a_step_can_be_escalated_again(self):
        """The idempotency key is the visit, not the step."""
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        Request = self.env["dma.accreditation.request"]
        Escalation = self.env["dma.sla.escalation"]

        with self._at("2026-03-06 09:00:00"):
            Request._cron_sla_review()
            self.assertEqual(len(Escalation.search([("request_id", "=", request.id)])), 1)
            self._as(request, self.user_gd).action_return_to_applicant("Incomplete.")
        with self._at("2026-03-07 09:00:00"):
            self._as(request, self.user_reception).action_resume_from_return()
            self._as(request, self.user_reception).action_send_to_general_director()
        with self._at("2026-03-12 09:00:00"):
            Request._cron_sla_review()
            escalations = Escalation.search([("request_id", "=", request.id)])
            self.assertEqual(
                len(escalations.filtered(lambda e: e.level == "1")), 2,
                "the file overran the same step twice, and both are on record",
            )

    def test_15_an_escalation_is_evidence_and_only_acknowledgement_may_touch_it(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        with self._at("2026-03-06 09:00:00"):
            self.env["dma.accreditation.request"]._cron_sla_review()
            escalation = self.env["dma.sla.escalation"].search([
                ("request_id", "=", request.id),
            ])
            with self.assertRaises(UserError):
                escalation.write({"reason": "rewritten"})
            with self.assertRaises(UserError):
                escalation.unlink()
            escalation.with_user(self.user_gd).action_acknowledge()
            self.assertEqual(escalation.acknowledged_by, self.user_gd)
            self.assertTrue(escalation.is_open, "acknowledging is not resolving")

    def test_16_the_cron_walks_the_whole_caseload_not_just_the_head_of_it(self):
        """A "first N per run" cap would never reach the tail of the queue."""
        with self._at(DAY_ONE):
            requests = [self._drive_to_gd_review(self._new_request()) for _ in range(3)]
        ids = [request.id for request in requests]
        Escalation = self.env["dma.sla.escalation"]

        with self._at("2026-03-06 09:00:00"):
            self.env["dma.accreditation.request"]._cron_sla_review()
            self.assertEqual(
                len(Escalation.search([("request_id", "in", ids)])), 3,
                "every overdue file was reached, not only the oldest ones",
            )
            # And a second run over the very same data writes nothing.
            before = Escalation.search([("request_id", "in", ids)]).ids
            self.env["dma.accreditation.request"]._cron_sla_review()
            self.assertEqual(
                Escalation.search([("request_id", "in", ids)]).ids, before,
            )

    # ==================================================================
    # Configuration
    # ==================================================================
    def test_17_only_the_manager_may_change_a_service_level(self):
        with self.assertRaises(AccessError):
            self.rule_gd.with_user(self.user_gd).write({"target_days": 99})
        with self.assertRaises(AccessError):
            self.env["dma.sla.rule"].with_user(self.user_finance).create({
                "state": "committee", "role": "committee", "target_days": 1,
            })
        self.rule_gd.with_user(self.user_manager).write({"target_days": 3})

    def test_18_changing_a_service_level_moves_the_deadlines_with_it(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
            self.assertEqual(
                fields.Datetime.to_string(request.sla_due_on), "2026-03-05 08:00:00",
            )
            self.rule_gd.with_user(self.user_manager).write({"target_days": 10})
            request.invalidate_recordset()
            self.assertEqual(
                fields.Datetime.to_string(request.sla_due_on), "2026-03-12 08:00:00",
                "the stored deadline follows the configuration, not the other way",
            )
            self.assertEqual(request.sla_state, "on_track")
        self.rule_gd.with_user(self.user_manager).write({"target_days": 3})

    def test_19_a_service_level_cannot_warn_before_the_file_arrives(self):
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.rule_gd.with_user(self.user_manager).write({
                "target_days": 1, "warning_days": 5,
            })

    @mute_logger("odoo.sql_db")
    def test_20_a_step_and_department_can_only_carry_one_service_level(self):
        from psycopg2 import IntegrityError
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.env["dma.sla.rule"].with_user(self.user_manager).create({
                "state": "gd_review", "role": "general_director",
                "target_days": 1, "company_id": False,
            })
            self.env.flush_all()

    # ==================================================================
    # Timezone
    # ==================================================================
    def test_21_the_clock_is_kept_in_utc_and_read_in_the_officer_s_timezone(self):
        """A deadline is a moment, not a wall clock reading."""
        self.user_gd.tz = "Asia/Baghdad"
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        with self._at("2026-03-04 09:00:00"):
            baghdad = self._refresh(request).with_user(self.user_gd).with_context(
                tz="Asia/Baghdad"
            )
            utc = self._refresh(request).with_context(tz="UTC")
            self.assertEqual(
                baghdad.sla_state, utc.sla_state,
                "the same file is exactly as late in Baghdad as in UTC",
            )
            self.assertEqual(baghdad.sla_due_on, utc.sla_due_on)

    # ==================================================================
    # Expiring evidence and certificates
    # ==================================================================
    def test_22_the_watch_reminds_about_expiring_evidence_without_repeating_itself(self):
        with self._at(DAY_ONE):
            request = self._new_request()
            line = request.document_ids.filtered(
                lambda doc: doc.type_id == self.env.ref(
                    "dma_accreditation.document_type_insurance"
                )
            )
            line.write({"expiry_date": fields.Date.to_date("2026-03-10")})
            self.assertEqual(line.validity_state, "expiring")

            Request = self.env["dma.accreditation.request"]
            Request._cron_document_watch()
            expiry_type = self.env.ref("dma_accreditation.mail_activity_type_expiry")
            activities = self.env["mail.activity"].sudo().search([
                ("res_model", "=", request._name), ("res_id", "=", request.id),
                ("activity_type_id", "=", expiry_type.id),
            ])
            self.assertTrue(activities)
            first = activities.ids
            Request._cron_document_watch()
            self.assertEqual(
                self.env["mail.activity"].sudo().search([
                    ("res_model", "=", request._name), ("res_id", "=", request.id),
                    ("activity_type_id", "=", expiry_type.id),
                ]).ids, first,
                "a second run the same day writes nothing",
            )

    def test_23_an_expired_accreditation_is_reported_never_revoked(self):
        with self._at(DAY_ONE):
            request = self._drive_to_dual_confirm(self._new_request())
            self._as(request, self.user_finance).action_finance_confirm()
            self._as(request, self.user_operations).action_operations_confirm()
            self._as(request, self.user_finance).action_dual_confirm_done()
            self._add_confirmed_fee(request, "operational_demo", "REC/SLA/DEMO")
            self._as(request, self.user_finance).action_demo_fee_registered()
            request.sudo().write({
                "committee_decision": "approve",
                "committee_date": fields.Date.context_today(request),
                "decision_text": "<p>Approved.</p>",
            })
            self._as(request, self.user_committee).action_committee_decision()
            request.sudo().write({"refined_decision_text": "<p>Refined.</p>"})
            self._as(request, self.user_legal).action_issue_authorization()
            self.assertEqual(request.state, "authorized")
            self.assertEqual(request.accreditation_validity_state, "valid")

        with self._at("2027-06-01 09:00:00"):
            self.env["dma.accreditation.request"]._cron_document_watch()
            self._refresh(request)
            self.assertEqual(request.accreditation_validity_state, "expired")
            self.assertEqual(
                request.state, "authorized",
                "time passing is not a decision: the status is untouched",
            )
            self.assertTrue(
                self.env["mail.activity"].sudo().search([
                    ("res_model", "=", request._name), ("res_id", "=", request.id),
                    ("activity_type_id", "=", self.env.ref(
                        "dma_accreditation.mail_activity_type_expiry"
                    ).id),
                ]),
                "but somebody is told",
            )

    def test_24_the_waiting_time_reads_the_way_an_officer_speaks(self):
        request = self._new_request()
        self.assertEqual(request._format_hours(0.2), "12 min")
        self.assertEqual(request._format_hours(5), "5 hour(s)")
        self.assertEqual(request._format_hours(48), "2 day(s)")
        self.assertEqual(request._format_hours(54), "2 day(s) 6 h")

    def test_25_the_badge_never_leans_on_colour_alone(self):
        with self._at(DAY_ONE):
            request = self._drive_to_gd_review(self._new_request())
        for moment in ("2026-03-02 09:00:00", "2026-03-04 09:00:00",
                       "2026-03-06 09:00:00", "2026-03-09 09:00:00"):
            with self.subTest(moment=moment), self._at(moment):
                payload = self._refresh(request).sla_payload
                self.assertTrue(payload["state_label"], "a written verdict")
                self.assertTrue(payload["icon"], "and an icon")
                self.assertTrue(payload["age"], "and how long it has been waiting")
                self.assertTrue(payload["waiting_on"], "and who is holding it")
