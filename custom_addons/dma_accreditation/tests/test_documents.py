# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""Document intelligence: validity, versions, duplicates and the hard gate.

The point of these is that the *review outcome stays authoritative*. A file
being attached has never meant the Certifications Division accepted it, and
after this release swapping the file behind an acceptance no longer keeps the
acceptance either.
"""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationDocuments(DmaAccreditationCommon):

    def _attach(self, line, name="registration.pdf", content=b"%PDF-1.4\nregistration\n"):
        """Attach a file to a checklist line the way the interface does.

        Filed against the line, because that is what makes ``ir.attachment``
        delegate its access to the accreditation file. An attachment with no
        ``res_id`` is readable only by whoever uploaded it, which is exactly
        not what a piece of departmental evidence needs to be.
        """
        attachment = self.env["ir.attachment"].create({
            "name": name,
            "type": "binary",
            "raw": content,
            "mimetype": "application/pdf",
            "res_model": line._name,
            "res_id": line.id,
        })
        line.write({"attachment_ids": [(4, attachment.id)], "is_provided": True})
        return attachment

    def _replacement(self, line, name, content):
        """A replacement file, uploaded against the line the way the form does."""
        return self.env["ir.attachment"].create({
            "name": name, "type": "binary", "raw": content,
            "mimetype": "application/pdf",
            "res_model": line._name, "res_id": line.id,
        })

    def _reviewable_request(self):
        """A request standing where its prerequisites may legally be verified."""
        return self._drive_to_cert_check(self._new_request())

    def _insurance_line(self, request):
        return request.document_ids.filtered(
            lambda line: line.type_id == self.env.ref(
                "dma_accreditation.document_type_insurance"
            )
        )

    # ------------------------------------------------------------------
    # Validity
    # ------------------------------------------------------------------
    def test_01_validity_states_follow_the_expiry_date(self):
        request = self._new_request()
        line = self._insurance_line(request)
        self.assertTrue(
            line.type_id.has_validity,
            "the insurance policy is seeded as a document that expires",
        )
        self.assertEqual(
            line.validity_state, "no_expiry",
            "with no expiry date recorded there is nothing to judge",
        )

        today = fields.Date.context_today(request)
        warning = line.type_id.expiry_warning_days
        for delta, expected in (
            (warning + 30, "valid"),
            (warning - 1, "expiring"),
            (0, "expiring"),
            (-1, "expired"),
        ):
            with self.subTest(delta=delta):
                line.write({"expiry_date": today + timedelta(days=delta)})
                self.assertEqual(line.validity_state, expected)
                self.assertEqual(line.days_to_expiry, delta)

    def test_02_a_document_type_that_does_not_expire_never_reports_a_validity(self):
        request = self._new_request()
        line = request.document_ids.filtered(
            lambda doc: doc.type_id == self.env.ref(
                "dma_accreditation.document_type_org_structure"
            )
        )
        self.assertFalse(line.type_id.has_validity)
        line.write({"expiry_date": fields.Date.context_today(request) - timedelta(days=5)})
        self.assertEqual(
            line.validity_state, "no_expiry",
            "an expiry date on a document that does not expire means nothing",
        )
        self.assertFalse(line._is_expired())

    def test_03_expiry_only_blocks_where_the_directorate_said_it_should(self):
        """The default is informational; blocking is a decision, and it is configurable."""
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        self._accept_all_documents(request)

        line = self._insurance_line(request)
        line.write({"expiry_date": fields.Date.context_today(request) - timedelta(days=1)})
        self.assertEqual(line.validity_state, "expired")
        self.assertFalse(line.type_id.blocks_on_expiry, "off by default")
        self.assertTrue(
            request.checklist_complete,
            "an expired document is reported, not blocking, until configured",
        )

        line.type_id.sudo().write({"blocks_on_expiry": True})
        request.invalidate_recordset()
        line.invalidate_recordset()
        self.assertFalse(request.checklist_complete)
        self.assertTrue(line.is_blocking)
        self.assertIn("Expired", line.blocking_reason)
        with self.assertRaises(ValidationError):
            self._as(request, self.user_cert).action_grant_office_accreditation()

        # Replacing it with a current policy opens the gate again.
        line.write({"expiry_date": fields.Date.context_today(request) + timedelta(days=365)})
        self.assertTrue(request.checklist_complete)
        self._as(request, self.user_cert).action_grant_office_accreditation()
        self.assertEqual(request.state, "office_granted")

    # ------------------------------------------------------------------
    # Versions and replacement
    # ------------------------------------------------------------------
    def test_04_replacing_the_evidence_of_an_accepted_line_supersedes_the_acceptance(self):
        """The defect this release fixes.

        Reception has write access to the checklist because it assembles the
        file. Before this, that let an accepted line have its evidence swapped
        for something nobody had looked at, and the hard gate still opened on
        it.
        """
        request = self._reviewable_request()
        line = self._insurance_line(request)
        first = self._attach(line, "insurance-2025.pdf", b"%PDF-1.4\nold policy\n")
        line.with_user(self.user_cert).action_accept()
        self.assertEqual(line.review_result, "accepted")
        self.assertEqual(line.reviewed_by, self.user_cert)
        self.assertEqual(line.version, 1)

        second = self._replacement(
            line, "insurance-2026.pdf", b"%PDF-1.4\nnew policy\n",
        )
        line.with_user(self.user_reception).write({
            "attachment_ids": [(6, 0, second.ids)],
        })

        self.assertEqual(
            line.review_result, "pending",
            "the sign-off was about the file that has just gone",
        )
        self.assertFalse(line.reviewed_by, "and it is nobody's sign-off now")
        self.assertFalse(line.reviewed_on)
        self.assertEqual(line.version, 2)
        self.assertEqual(line.superseded_count, 1)

        history = line.submission_ids
        self.assertEqual(len(history), 1)
        self.assertEqual(history.version, 1)
        self.assertEqual(
            history.review_result, "accepted",
            "the superseded version remembers the verdict it was given",
        )
        self.assertEqual(history.reviewed_by, self.user_cert)
        self.assertEqual(
            history.attachment_ids, first,
            "and the file it was given on, which is still on record",
        )
        self.assertTrue(first.exists(), "previous evidence is never destroyed")

    def test_05_the_first_upload_is_not_a_replacement(self):
        request = self._new_request()
        line = self._insurance_line(request)
        self._attach(line)
        self.assertEqual(line.version, 1)
        self.assertFalse(line.submission_ids, "nothing was superseded")
        self.assertEqual(line.review_result, "pending")

    def test_06_replacing_a_line_nobody_had_reviewed_still_records_the_version(self):
        request = self._new_request()
        line = self._insurance_line(request)
        self._attach(line, "draft.pdf", b"%PDF-1.4\ndraft\n")
        replacement = self._replacement(line, "final.pdf", b"%PDF-1.4\nfinal\n")
        line.write({"attachment_ids": [(6, 0, replacement.ids)]})
        self.assertEqual(line.superseded_count, 1)
        self.assertEqual(
            line.submission_ids.review_result, "pending",
            "it was never reviewed, and the history says so",
        )
        self.assertEqual(line.review_result, "pending")

    def test_07_the_version_history_is_immutable(self):
        request = self._new_request()
        line = self._insurance_line(request)
        self._attach(line)
        line.write({"attachment_ids": [(5, 0, 0)]})
        history = line.submission_ids
        self.assertTrue(history)
        with self.assertRaises(UserError):
            history.write({"review_result": "accepted"})
        with self.assertRaises(UserError):
            history.unlink()
        with self.assertRaises(UserError):
            history.sudo().unlink()

    def test_08_the_replacement_wizard_records_the_reason_and_the_metadata(self):
        request = self._reviewable_request()
        line = self._insurance_line(request)
        self._attach(line, "insurance-2025.pdf", b"%PDF-1.4\nold\n")
        line.with_user(self.user_cert).action_accept()

        replacement = self._replacement(line, "insurance-2026.pdf", b"%PDF-1.4\nnew\n")
        expiry = fields.Date.context_today(request) + timedelta(days=300)
        wizard = self.env["dma.document.replacement"].with_user(self.user_cert).create({
            "document_id": line.id,
            "attachment_ids": [(6, 0, replacement.ids)],
            "reference": "2026/INS/4471",
            "issuer": "Iraqi Insurance Company",
            "expiry_date": expiry,
            "reason": "The 2025 policy lapsed on 31 December.",
        })
        wizard.action_replace()

        self.assertEqual(line.attachment_ids, replacement)
        self.assertEqual(line.reference, "2026/INS/4471")
        self.assertEqual(line.issuer, "Iraqi Insurance Company")
        self.assertEqual(line.expiry_date, expiry)
        self.assertEqual(line.review_result, "pending")
        self.assertEqual(
            line.submission_ids.replacement_reason,
            "The 2025 policy lapsed on 31 December.",
            "the reason lands on the version it explains",
        )
        self.assertEqual(
            replacement.res_model, line._name,
            "the new file is filed against the checklist line, so its access "
            "follows the accreditation and not the vacuumed wizard",
        )

    def test_09_the_wizard_refuses_an_empty_replacement_and_a_backwards_expiry(self):
        request = self._new_request()
        line = self._insurance_line(request)
        with self.assertRaises(ValidationError):
            self.env["dma.document.replacement"].with_user(self.user_cert).create({
                "document_id": line.id,
                "attachment_ids": [(6, 0, [])],
                "issue_date": fields.Date.context_today(request),
                "expiry_date": fields.Date.context_today(request) - timedelta(days=1),
                "reason": "backwards",
            })

    # ------------------------------------------------------------------
    # Duplicates
    # ------------------------------------------------------------------
    def test_10_the_same_file_on_two_requirements_is_flagged_not_refused(self):
        request = self._reviewable_request()
        registration = request.document_ids.filtered(
            lambda line: line.type_id == self.env.ref(
                "dma_accreditation.document_type_registration"
            )
        )
        attorney = request.document_ids.filtered(
            lambda line: line.type_id == self.env.ref(
                "dma_accreditation.document_type_power_of_attorney"
            )
        )
        content = b"%PDF-1.4\none document, two purposes\n"
        self._attach(registration, "company.pdf", content)
        self.assertFalse(registration.duplicate_warning, "nothing to compare it with yet")

        self._attach(attorney, "company-copy.pdf", content)
        request.invalidate_recordset()
        self.assertEqual(
            attorney.duplicate_of_id, registration,
            "matched on the checksum, not on the name the applicant chose",
        )
        self.assertIn(registration.type_id.name, attorney.duplicate_warning)
        # A warning, never a refusal: one PDF can legitimately be both.
        attorney.with_user(self.user_cert).action_accept()
        self.assertEqual(attorney.review_result, "accepted")

    def test_11_different_bytes_are_not_a_duplicate(self):
        request = self._new_request()
        lines = request.document_ids[:2]
        self._attach(lines[0], "a.pdf", b"%PDF-1.4\nfirst\n")
        self._attach(lines[1], "b.pdf", b"%PDF-1.4\nsecond\n")
        request.invalidate_recordset()
        self.assertFalse(lines[0].duplicate_of_id)
        self.assertFalse(lines[1].duplicate_of_id)

    # ------------------------------------------------------------------
    # The gate, and who may open it
    # ------------------------------------------------------------------
    def test_12_blocking_reason_names_the_actual_problem(self):
        request = self._reviewable_request()
        line = self._insurance_line(request)
        self.assertEqual(line.blocking_reason, "Not provided")

        self._attach(line)
        self.assertEqual(line.blocking_reason, "Provided but not reviewed yet")

        # A rejection carries its reason: it is printed to the applicant.
        line.with_user(self.user_cert).write({"notes": "The policy expired in 2025."})
        line.with_user(self.user_cert).action_mark_invalid()
        self.assertEqual(line.blocking_reason, "Rejected as invalid")

        line.with_user(self.user_cert).action_mark_missing()
        self.assertEqual(
            line.blocking_reason, "Recorded as missing",
            "an explicit verdict is more useful than the generic absence",
        )

        line.with_user(self.user_cert).action_accept()
        self.assertFalse(line.is_blocking)
        self.assertFalse(line.blocking_reason)

    def test_13_only_the_certifications_division_may_reject_evidence(self):
        request = self._reviewable_request()
        line = self._insurance_line(request)
        self._attach(line)
        line.with_user(self.user_cert).write({"notes": "Not the current policy."})
        with self.assertRaises(AccessError):
            line.with_user(self.user_reception).action_mark_invalid()
        line.with_user(self.user_cert).action_mark_invalid()
        self.assertEqual(line.review_result, "invalid")

    def test_14_the_request_counts_what_is_blocking_expiring_and_replaced(self):
        request = self._reviewable_request()
        line = self._insurance_line(request)
        self.assertEqual(
            request.blocking_document_count, request.required_document_count,
        )
        self._accept_all_documents(request)
        self.assertEqual(request.blocking_document_count, 0)

        today = fields.Date.context_today(request)
        line.write({"expiry_date": today + timedelta(days=5)})
        self.assertEqual(request.expiring_document_count, 1)
        self.assertEqual(request.expired_document_count, 0)

        line.write({"expiry_date": today - timedelta(days=5)})
        self.assertEqual(request.expiring_document_count, 0)
        self.assertEqual(request.expired_document_count, 1)

        self._attach(line, "one.pdf", b"%PDF-1.4\none\n")
        replacement = self._replacement(line, "two.pdf", b"%PDF-1.4\ntwo\n")
        line.write({"attachment_ids": [(6, 0, replacement.ids)]})
        self.assertEqual(request.document_replacement_count, 1)

    def test_15_the_progress_blockers_say_why_each_document_is_a_problem(self):
        request = self._new_request()
        self._as(request, self.user_reception).action_submit()
        self._as(request, self.user_reception).action_send_to_general_director()
        self._as(request, self.user_gd).action_gd_accept()
        self._as(request, self.user_legal).action_legal_approve()
        self._accept_all_documents(request)
        line = self._insurance_line(request)
        line.with_user(self.user_cert).action_mark_missing()

        blockers = request.progress_payload["blockers"]
        self.assertEqual(len(blockers), 1)
        self.assertIn(line.type_id.name, blockers[0])
        self.assertEqual(
            blockers[0], "%s: Recorded as missing" % line.type_id.name,
            "the blocker names the actual problem, not just the document",
        )

    def test_16_the_stored_validity_column_is_refreshed_by_the_scheduled_job(self):
        """It is derived from today's date, so it is a day stale by tomorrow."""
        request = self._new_request()
        line = self._insurance_line(request)
        today = fields.Date.context_today(request)
        line.write({"expiry_date": today + timedelta(days=1)})
        self.assertEqual(line.validity_state, "expiring")

        # Pretend a day passed without anything touching the record: the stored
        # column is stale, the gate is not.
        line.flush_recordset()
        self.env.cr.execute(
            "UPDATE dma_request_document SET expiry_date = %s WHERE id = %s",
            (today - timedelta(days=1), line.id),
        )
        line.invalidate_recordset()
        self.assertEqual(
            line.validity_state, "expiring", "the column has not caught up yet",
        )
        self.assertTrue(
            line._is_expired(),
            "but the gate reads the calendar and is never a day out",
        )

        self.env["dma.request.document"]._cron_refresh_validity()
        line.invalidate_recordset()
        self.assertEqual(line.validity_state, "expired")
