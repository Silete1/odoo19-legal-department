# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Process performance, asserted against a caseload with a known history.

Every figure is checked against a number worked out by hand from the fixture,
not merely against "the method returned something". Time is frozen so a
duration is a duration and not a function of when the suite happens to run.
"""
from odoo import fields
from odoo.tests.common import freeze_time, tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationAnalytics(DmaAccreditationCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Performance figures are about a caseload, so the caseload has to be
        # exactly the fixture. A database installed with demo data already
        # carries files of its own, and "the median wait is 48 hours" is only
        # checkable when nothing else is in the sample.
        cls.env["dma.accreditation.request"].sudo().search([]).write({"active": False})

    def _at(self, moment):
        return freeze_time(moment)

    def _file(self, submitted_on, gd_on):
        """A file submitted on one day and accepted by the GD on another."""
        with self._at(submitted_on):
            request = self._new_request()
            self._as(request, self.user_reception).action_submit()
            self._as(request, self.user_reception).action_send_to_general_director()
        with self._at(gd_on):
            self._as(request, self.user_gd).action_gd_accept()
        return request

    # ==================================================================
    # The event log
    # ==================================================================
    def test_01_the_log_carries_the_duration_of_the_step_it_closed(self):
        request = self._file("2026-03-02 08:00:00", "2026-03-05 08:00:00")
        line = request.approval_line_ids.filtered(lambda l: l.step == "gd_review")
        self.assertTrue(line.is_transition, "this entry moved the file on")
        self.assertEqual(
            fields.Datetime.to_string(line.entered_on), "2026-03-02 08:00:00",
        )
        self.assertAlmostEqual(
            line.duration_hours, 72.0, places=2,
            msg="three days with the General Director, to the hour",
        )

    def test_02_only_the_entry_that_closed_a_step_counts_as_a_transition(self):
        with self._at("2026-03-02 08:00:00"):
            request = self._drive_to_dual_confirm(self._new_request())
        with self._at("2026-03-03 08:00:00"):
            self._as(request, self.user_finance).action_finance_confirm()
        with self._at("2026-03-04 08:00:00"):
            self._as(request, self.user_operations).action_operations_confirm()
        with self._at("2026-03-06 08:00:00"):
            self._as(request, self.user_finance).action_dual_confirm_done()

        entries = request.approval_line_ids.filtered(lambda l: l.step == "dual_confirm")
        self.assertEqual(len(entries), 3, "two signatures and the move on")
        closing = entries.filtered("is_transition")
        self.assertEqual(len(closing), 1, "only one of them closed the step")
        self.assertAlmostEqual(
            closing.duration_hours, 96.0, places=2,
            msg="and it carries the whole four days, not a third of them",
        )

    def test_03_the_percentile_aggregate_reaches_postgresql(self):
        for gd_day, in ((3,), (5,), (9,)):
            self._file("2026-03-02 08:00:00", "2026-03-%02d 08:00:00" % (2 + gd_day))
        rows = self.env["dma.approval.line"]._read_group(
            domain=[
                ("step", "=", "gd_review"), ("is_transition", "=", True),
                # The window keeps any pre-existing file out of the sample.
                ("date", ">=", "2026-03-01 00:00:00"),
                ("date", "<", "2026-04-01 00:00:00"),
            ],
            groupby=[],
            aggregates=["__count", "duration_hours:p50", "duration_hours:p90"],
        )
        count, median, p90 = rows[0]
        self.assertEqual(count, 3)
        self.assertAlmostEqual(
            median, 120.0, places=1, msg="the middle of 72 / 120 / 216 hours",
        )
        self.assertAlmostEqual(p90, 196.8, places=1)

    # ==================================================================
    # Stage performance
    # ==================================================================
    def test_04_stage_durations_are_measured_per_visit(self):
        self._file("2026-03-02 08:00:00", "2026-03-05 08:00:00")   # 72 h
        self._file("2026-03-02 08:00:00", "2026-03-03 08:00:00")   # 24 h
        with self._at("2026-03-20 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-20",
            )
        stage = next(item for item in data["stages"] if item["key"] == "gd_review")
        self.assertEqual(stage["count"], 2)
        self.assertAlmostEqual(stage["median_hours"], 48.0, places=1)
        self.assertTrue(stage["thin"], "two files is not a performance figure")
        self.assertEqual(stage["label"], "General Director Initial Acceptance")
        self.assertEqual(stage["role"], "General Director")

    def test_05_the_live_backlog_and_the_overdue_count_come_off_the_clock(self):
        with self._at("2026-03-02 08:00:00"):
            late = self._new_request()
            self._as(late, self.user_reception).action_submit()
            self._as(late, self.user_reception).action_send_to_general_director()
        with self._at("2026-03-20 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-20",
            )
            stage = next(item for item in data["stages"] if item["key"] == "gd_review")
            self.assertEqual(stage["waiting"], 1)
            self.assertEqual(stage["overdue"], 1)
            self.assertEqual(stage["escalated"], 1)
            self.assertEqual(stage["overdue_rate"], 100)
        self.assertIn(late, self.env["dma.accreditation.request"].browse(late.id))

    def test_06_the_bottleneck_ranking_answers_three_separate_questions(self):
        self._file("2026-03-02 08:00:00", "2026-03-12 08:00:00")   # slow GD
        with self._at("2026-03-02 08:00:00"):
            waiting = self._new_request()
            self._as(waiting, self.user_reception).action_submit()
        with self._at("2026-03-20 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-20",
            )
        self.assertEqual(
            data["bottlenecks"]["slowest"][0]["key"], "gd_review",
            "ten days is the longest median wait in the fixture",
        )
        self.assertTrue(data["bottlenecks"]["busiest"], "something is waiting")
        self.assertIn(waiting.state, [
            stage["key"] for stage in data["bottlenecks"]["busiest"]
        ])
        # Each ranking is its own ordering, never one blended score.
        for key in ("slowest", "latest", "busiest"):
            self.assertLessEqual(len(data["bottlenecks"][key]), 5)

    # ==================================================================
    # Throughput and cycle time
    # ==================================================================
    def test_07_throughput_counts_decisions_in_the_month_they_were_taken(self):
        with self._at("2026-02-10 08:00:00"):
            february = self._new_request()
            self._as(february, self.user_reception).action_submit()
        with self._at("2026-03-10 08:00:00"):
            march = self._drive_to_office_granted(self._new_request())
        with self._at("2026-03-31 12:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-02-01", date_to="2026-03-31",
            )
        months = data["throughput"]["months"]
        self.assertEqual(months, ["2026-02", "2026-03"])
        submitted = dict(zip(months, data["throughput"]["series"]["submitted"]))
        self.assertEqual(submitted["2026-02"], 1)
        self.assertEqual(submitted["2026-03"], 1)
        granted = dict(zip(months, data["throughput"]["series"]["office_granted"]))
        self.assertEqual(granted["2026-02"], 0)
        self.assertEqual(granted["2026-03"], 1)
        self.assertEqual(march.state, "office_granted")
        self.assertEqual(february.state, "submitted")

    def test_08_cycle_time_is_measured_between_the_decisions_themselves(self):
        with self._at("2026-03-02 08:00:00"):
            request = self._new_request()
            self._as(request, self.user_reception).action_submit()
            self._as(request, self.user_reception).action_send_to_general_director()
            self._as(request, self.user_gd).action_gd_accept()
            self._as(request, self.user_legal).action_legal_approve()
            self._accept_all_documents(request)
        with self._at("2026-03-12 08:00:00"):
            self._as(request, self.user_cert).action_grant_office_accreditation()
        with self._at("2026-03-31 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-31",
            )
        office = data["cycle_time"]["office"]
        self.assertEqual(office["count"], 1)
        self.assertAlmostEqual(
            office["median"], 240.0, places=1, msg="ten days from submission to grant",
        )
        self.assertEqual(office["label"], "10.0 d")
        self.assertTrue(office["thin"], "one file is not a cycle time")
        self.assertEqual(
            data["cycle_time"]["overall"]["count"], 0,
            "the file never reached the operational accreditation",
        )

    def test_09_a_file_still_in_flight_never_drags_a_cycle_time_down(self):
        with self._at("2026-03-02 08:00:00"):
            self._drive_to_office_granted(self._new_request())
            open_file = self._new_request()
            self._as(open_file, self.user_reception).action_submit()
        with self._at("2026-03-31 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-31",
            )
        self.assertEqual(
            data["cycle_time"]["office"]["count"], 1,
            "only the file that actually reached the milestone counts",
        )

    # ==================================================================
    # Rework
    # ==================================================================
    def test_10_returns_are_counted_by_the_step_they_came_back_from(self):
        with self._at("2026-03-02 08:00:00"):
            request = self._new_request()
            self._as(request, self.user_reception).action_submit()
            self._as(request, self.user_reception).action_send_to_general_director()
            self._as(request, self.user_gd).action_return_to_applicant("Incomplete.")
            self._as(request, self.user_reception).action_resume_from_return()
            self._as(request, self.user_reception).action_send_to_general_director()
            self._as(request, self.user_gd).action_return_to_applicant("Still incomplete.")
        with self._at("2026-03-31 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-31",
            )
        rework = data["rework"]
        self.assertEqual(rework["total"], 2)
        self.assertEqual(rework["by_step"][0]["key"], "gd_review")
        self.assertEqual(rework["by_step"][0]["count"], 2)
        self.assertEqual(len(rework["repeat_offenders"]), 1)
        self.assertEqual(rework["repeat_offenders"][0]["id"], request.id)
        self.assertEqual(rework["repeat_offenders"][0]["count"], 2)

    # ==================================================================
    # Workload
    # ==================================================================
    def test_11_workload_shows_what_each_department_holds_and_how_late_it_is(self):
        with self._at("2026-03-02 08:00:00"):
            late = self._new_request()
            self._as(late, self.user_reception).action_submit()
            self._as(late, self.user_reception).action_send_to_general_director()
            self._file("2026-03-02 08:00:00", "2026-03-04 08:00:00")
        with self._at("2026-03-20 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-20",
            )
        gd = next(row for row in data["workload"] if row["key"] == "general_director")
        self.assertEqual(gd["holding"], 1, "one file is with the General Director")
        self.assertEqual(gd["overdue"], 1)
        self.assertEqual(gd["completed"], 1, "and one was dealt with in the period")
        self.assertAlmostEqual(gd["median_hours"], 48.0, places=1)
        self.assertEqual(
            data["workload"][0]["key"], "general_director",
            "whoever is late is at the top of the list",
        )

    def test_12_the_dual_confirmation_puts_a_file_on_two_desks_at_once(self):
        with self._at("2026-03-02 08:00:00"):
            self._drive_to_dual_confirm(self._new_request())
        with self._at("2026-03-03 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-20",
            )
        by_role = {row["key"]: row for row in data["workload"]}
        self.assertEqual(by_role["finance"]["holding"], 1)
        self.assertEqual(
            by_role["operations"]["holding"], 1,
            "the parallel step is not assigned to one department",
        )

    # ==================================================================
    # Live SLA and document health
    # ==================================================================
    def test_13_the_sla_payload_reports_the_live_picture(self):
        with self._at("2026-03-02 08:00:00"):
            late = self._new_request()
            self._as(late, self.user_reception).action_submit()
            self._as(late, self.user_reception).action_send_to_general_director()
        with self._at("2026-03-09 08:00:00"):
            # Filed today, so it has every one of its two days left.
            fresh = self._new_request()
            self._as(fresh, self.user_reception).action_submit()
            self.env["dma.accreditation.request"]._cron_sla_review()
            data = self.env["dma.accreditation.request"].get_sla_dashboard_data()
        counts = {item["key"]: item["count"] for item in data["counts"]}
        self.assertEqual(counts.get("escalated"), 1)
        self.assertEqual(data["worst"][0]["id"], late.id)
        self.assertEqual(data["worst"][0]["sla_state"], "escalated")
        self.assertTrue(data["worst"][0]["overdue_label"])
        self.assertTrue(data["escalations"], "the open escalations are listed")
        self.assertEqual(data["escalations"][0]["request_id"], late.id)
        self.assertLessEqual(data["on_time_percent"], 100)
        self.assertEqual(fresh.state, "submitted")

    def test_14_document_health_never_counts_an_attachment_as_evidence(self):
        request = self._new_request()
        line = request.document_ids[0]
        attachment = self.env["ir.attachment"].create({
            "name": "scan.pdf", "type": "binary", "raw": b"%PDF-1.4\nscan\n",
            "res_model": line._name, "res_id": line.id,
        })
        line.write({"attachment_ids": [(4, attachment.id)], "is_provided": True})

        data = self.env["dma.accreditation.request"].get_document_health_data()
        self.assertGreaterEqual(data["totals"]["pending_review"], 1)
        self.assertTrue(
            any(item["id"] == request.id for item in data["blocked_requests"]),
            "a file with an unreviewed attachment is still blocked by it",
        )

        line.with_user(self.user_cert).action_mark_invalid()
        data = self.env["dma.accreditation.request"].get_document_health_data()
        self.assertGreaterEqual(data["totals"]["invalid"], 1)
        self.assertTrue(data["worst_documents"])

    def test_15_a_small_sample_is_reported_as_a_small_sample(self):
        self._file("2026-03-02 08:00:00", "2026-03-05 08:00:00")
        with self._at("2026-03-20 08:00:00"):
            data = self.env["dma.accreditation.request"].get_process_performance_data(
                date_from="2026-03-01", date_to="2026-03-20",
            )
        stage = next(item for item in data["stages"] if item["key"] == "gd_review")
        self.assertEqual(stage["count"], 1)
        self.assertTrue(stage["thin"])
        self.assertEqual(data["min_sample"], 5)

    def test_16_the_distribution_helper_matches_postgresql(self):
        """The Python and SQL paths must never disagree on the same numbers."""
        Request = self.env["dma.accreditation.request"]
        for values, median, p90 in (
            ([1.0], 1.0, 1.0),
            ([1.0, 3.0], 2.0, 2.8),
            ([1.0, 2.0, 3.0], 2.0, 2.8),
            ([10.0, 20.0, 30.0, 40.0], 25.0, 37.0),
        ):
            with self.subTest(values=values):
                stats = Request._distribution(values)
                self.assertEqual(stats["count"], len(values))
                self.assertAlmostEqual(stats["median"], median, places=6)
                self.assertAlmostEqual(stats["p90"], p90, places=6)
        empty = Request._distribution([])
        self.assertEqual(empty["count"], 0)
        self.assertTrue(empty["thin"])

    def test_17_the_analytics_are_read_in_the_reader_s_timezone(self):
        self.env.user.tz = "Asia/Baghdad"
        with self._at("2026-03-31 22:30:00"):
            # 22:30 UTC on 31 March is 01:30 on 1 April in Baghdad, so the
            # bucket a naive reading would land in is the wrong month.
            request = self._new_request()
            self._as(request, self.user_reception).action_submit()
            analytics = self.env["dma.accreditation.request"]._analytics_env()
            self.assertEqual(analytics.env.context.get("tz"), "Asia/Baghdad")

    def test_18_the_analytics_refuse_a_reader_who_may_not_read_the_caseload(self):
        from odoo.exceptions import AccessError
        outsider = self.env["res.users"].create({
            "name": "Outsider", "login": "dma_analytics_outsider",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        Request = self.env["dma.accreditation.request"].with_user(outsider)
        for method in (
            "get_process_performance_data",
            "get_sla_dashboard_data",
            "get_document_health_data",
        ):
            with self.subTest(method=method), self.assertRaises(AccessError):
                getattr(Request, method)()
