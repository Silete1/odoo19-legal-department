# Part of the DMA Accreditation module. See LICENSE file for full copyright and licensing details.
"""The accreditation dossier: what is in it, and what must never be.

The security tests here are the point of the file. A dossier is the complete
evidence file of a private company, so the two things that must be true are
that it contains everything belonging to *this* accreditation and nothing
belonging to another one.
"""
import io
import zipfile

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import DmaAccreditationCommon


@tagged("post_install", "-at_install", "dma_accreditation")
class TestAccreditationDossier(DmaAccreditationCommon):

    def _attach_to_line(self, line, name, content=b"%PDF-1.4\nevidence\n"):
        attachment = self.env["ir.attachment"].create({
            "name": name, "type": "binary", "raw": content,
            "mimetype": "application/pdf",
            "res_model": line._name, "res_id": line.id,
        })
        line.write({"attachment_ids": [(4, attachment.id)], "is_provided": True})
        return attachment

    def _sections(self, request):
        return {section["key"]: section for section in request._dossier_index()}

    def _all_entries(self, request):
        return [
            entry for section in request._dossier_index()
            for entry in section.get("entries", [])
        ]

    # ------------------------------------------------------------------
    # What the index contains
    # ------------------------------------------------------------------
    def test_01_the_index_has_a_heading_for_every_part_of_the_paper_file(self):
        request = self._new_request()
        sections = self._sections(request)
        self.assertEqual(
            list(sections),
            ["application", "prerequisites", "sop", "fees", "committee",
             "issued", "correspondence", "history"],
            "the dossier reads in the order an auditor reads a paper file",
        )
        prerequisites = sections["prerequisites"]
        self.assertEqual(
            len(prerequisites["documents"]), len(request.document_ids),
            "one block per requirement, whether or not anything is filed under it",
        )
        for block in prerequisites["documents"]:
            self.assertTrue(block["label"])
            self.assertIn("review_label", block)
            self.assertIn("validity_label", block)

    def test_02_the_index_collects_evidence_from_every_corner_of_the_file(self):
        request = self._drive_to_dual_confirm(self._new_request())
        line = request.document_ids[0]
        checklist_file = self._attach_to_line(line, "registration.pdf")
        fee = request.fee_ids[0]
        receipt = self.env["ir.attachment"].create({
            "name": "receipt.pdf", "type": "binary", "raw": b"%PDF-1.4\nreceipt\n",
            # Filed against the fee, the way the form's upload widget files it.
            # An attachment with no res_id belongs to whoever uploaded it and
            # nobody else, which is not what a departmental receipt is.
            "res_model": fee._name, "res_id": fee.id,
        })
        fee.sudo().write({"attachment_ids": [(6, 0, receipt.ids)]})
        minutes = self.env["ir.attachment"].create({
            "name": "minutes.pdf", "type": "binary", "raw": b"%PDF-1.4\nminutes\n",
            "res_model": request._name, "res_id": request.id,
        })
        request.sudo().write({"committee_minutes_ids": [(6, 0, minutes.ids)]})

        sections = self._sections(request)
        self.assertIn(
            checklist_file.id,
            [entry["attachment_id"] for entry in sections["prerequisites"]["entries"]],
        )
        self.assertIn(
            receipt.id, [entry["attachment_id"] for entry in sections["fees"]["entries"]],
        )
        self.assertIn(
            minutes.id,
            [entry["attachment_id"] for entry in sections["committee"]["entries"]],
        )
        # The SOP was attached by the shared test helper.
        self.assertTrue(sections["sop"]["entries"])

    def test_03_superseded_versions_are_in_the_dossier_and_marked_as_such(self):
        request = self._new_request()
        line = request.document_ids[0]
        first = self._attach_to_line(line, "v1.pdf", b"%PDF-1.4\nfirst\n")
        second = self.env["ir.attachment"].create({
            "name": "v2.pdf", "type": "binary", "raw": b"%PDF-1.4\nsecond\n",
            "res_model": line._name, "res_id": line.id,
        })
        line.write({"attachment_ids": [(6, 0, second.ids)]})

        block = next(
            entry for entry in self._sections(request)["prerequisites"]["documents"]
            if entry["document_id"] == line.id
        )
        by_id = {entry["attachment_id"]: entry for entry in block["entries"]}
        self.assertIn(first.id, by_id, "the evidence trail keeps what came before")
        self.assertTrue(by_id[first.id]["superseded"])
        self.assertFalse(by_id[second.id]["superseded"])

    def test_04_the_generated_letter_is_recognised_without_matching_its_name(self):
        request = self._drive_to_office_granted(self._new_request())
        # Rendering needs no PDF engine in a test, so the attachment may be
        # absent; when it is there it must be filed under "issued".
        if request.office_letter_attachment_id:
            issued = self._sections(request)["issued"]["entries"]
            self.assertIn(
                request.office_letter_attachment_id.id,
                [entry["attachment_id"] for entry in issued],
            )
            self.assertEqual(
                request.office_letter_attachment_id.description, "dma_office_letter",
                "marked in a way that survives a change of interface language",
            )

    def test_05_the_index_says_what_is_missing(self):
        request = self._drive_to_cert_check(self._new_request())
        payload = request.dossier_payload
        self.assertEqual(
            len(payload["missing"]), request.required_document_count,
            "nothing has been accepted yet, so everything required is missing",
        )
        self._accept_all_documents(request)
        request.invalidate_recordset()
        self.assertFalse(request.dossier_payload["missing"])
        self.assertEqual(request.dossier_missing_count, 0)

    def test_06_the_decision_trail_is_in_the_dossier(self):
        request = self._drive_to_office_granted(self._new_request())
        history = self._sections(request)["history"]["history"]
        self.assertTrue(history)
        self.assertTrue(history[-1]["open"], "the step the file is on now")
        steps = [visit["step"] for visit in history]
        self.assertEqual(len(set(steps)), len(steps), "one entry per visit, in order")
        for visit in history[:-1]:
            self.assertTrue(visit["entered_on"])
            self.assertTrue(visit["left_on"])
            self.assertTrue(visit["duration"])

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------
    def test_07_a_dossier_never_contains_another_accreditation_s_evidence(self):
        mine = self._new_request()
        theirs = self._new_request()
        self._attach_to_line(mine.document_ids[0], "mine.pdf", b"%PDF-1.4\nmine\n")
        stranger = self._attach_to_line(
            theirs.document_ids[0], "theirs.pdf", b"%PDF-1.4\ntheirs\n",
        )
        # ... including an attachment filed straight against the other request.
        foreign = self.env["ir.attachment"].create({
            "name": "foreign.pdf", "type": "binary", "raw": b"%PDF-1.4\nforeign\n",
            "res_model": theirs._name, "res_id": theirs.id,
        })

        ids = [entry["attachment_id"] for entry in self._all_entries(mine)]
        self.assertNotIn(stranger.id, ids)
        self.assertNotIn(foreign.id, ids)

        archive = zipfile.ZipFile(io.BytesIO(mine._dossier_zip_bytes()))
        names = archive.namelist()
        self.assertFalse(
            [name for name in names if "theirs" in name or "foreign" in name],
            "and nothing of theirs reaches the archive either",
        )

    def test_08_the_archive_is_built_from_the_record_not_from_a_list_of_ids(self):
        """There is no way to ask for an attachment; you ask for a file."""
        request = self._new_request()
        self.assertFalse(
            [name for name in dir(request) if name == "action_download_attachments"],
            "the only entry point takes a request",
        )
        action = request.action_download_dossier()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(
            action["url"], "/dma/accreditation/dossier/%s" % request.id,
        )

    def test_09_archive_entry_names_are_sanitised(self):
        """Odoo's own ZIP builders write the file name in verbatim. This one does not."""
        request = self._new_request()
        line = request.document_ids[0]
        self._attach_to_line(line, "../../evil.exe", b"%PDF-1.4\nnasty\n")
        self._attach_to_line(line, "CON.pdf", b"%PDF-1.4\nreserved\n")

        archive = zipfile.ZipFile(io.BytesIO(request._dossier_zip_bytes()))
        for name in archive.namelist():
            self.assertNotIn("..", name, "no traversal out of the extraction folder")
            self.assertFalse(name.startswith("/"))
            self.assertFalse(name.startswith("\\"))
        self.assertTrue(
            [name for name in archive.namelist() if name.endswith("evil.exe")],
            "the file is still there, under a name that cannot escape",
        )

    def test_10_two_documents_of_the_same_name_do_not_shadow_one_another(self):
        request = self._new_request()
        for line in request.document_ids[:2]:
            self._attach_to_line(
                line, "scan.pdf", b"%PDF-1.4\n" + str(line.id).encode() + b"\n",
            )
        archive = zipfile.ZipFile(io.BytesIO(request._dossier_zip_bytes()))
        names = archive.namelist()
        self.assertEqual(len(names), len(set(names)), "every entry has its own name")
        self.assertEqual(
            len([name for name in names if "scan" in name]), 2,
            "and both documents survived",
        )

    def test_11_the_archive_refuses_to_be_a_memory_bomb(self):
        request = self._new_request()
        self._attach_to_line(request.document_ids[0], "big.pdf", b"%PDF-1.4\n" + b"x" * 5000)
        self.env["ir.config_parameter"].sudo().set_param(
            "dma_accreditation.dossier_max_bytes", "100",
        )
        with self.assertRaises(UserError):
            request._dossier_zip_bytes()
        self.env["ir.config_parameter"].sudo().set_param(
            "dma_accreditation.dossier_max_bytes", "209715200",
        )
        self.assertTrue(request._dossier_zip_bytes())

    def test_12_the_download_route_refuses_a_reader_who_may_not_read_the_file(self):
        """The controller's gate is the record's own access check."""
        request = self._new_request()
        outsider = self.env["res.users"].create({
            "name": "Outsider", "login": "dma_outsider",
            "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
        })
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            request.with_user(outsider).check_access("read")
        with self.assertRaises(AccessError):
            request.with_user(outsider)._dossier_zip_bytes()

    def test_12b_a_reader_who_may_not_see_one_file_gets_a_dossier_without_it(self):
        """A partial right produces a partial dossier, never an error.

        ``ir.attachment`` delegates its access to the record an attachment is
        filed against, and an attachment filed against nothing at all belongs
        to whoever uploaded it. The dossier honours that rather than working
        around it.
        """
        request = self._new_request()
        line = request.document_ids[0]
        shared = self._attach_to_line(line, "shared.pdf", b"%PDF-1.4\nshared\n")
        # Uploaded by the Certifications Division and filed against nothing.
        private = self.env["ir.attachment"].with_user(self.user_cert).create({
            "name": "private-note.pdf", "type": "binary",
            "raw": b"%PDF-1.4\nprivate\n",
        })
        # Only the uploader can even link it: the ORM checks read access on
        # the far side of a many2many before writing it.
        line.with_user(self.user_cert).write({"attachment_ids": [(4, private.id)]})

        for_cert = request.with_user(self.user_cert)._dossier_readable_attachments()
        for_finance = request.with_user(self.user_finance)._dossier_readable_attachments()
        self.assertIn(shared, for_cert)
        self.assertIn(shared, for_finance)
        self.assertIn(private, for_cert, "the uploader can still see their own file")
        self.assertNotIn(private, for_finance)

        archive = zipfile.ZipFile(
            io.BytesIO(request.with_user(self.user_finance)._dossier_zip_bytes())
        )
        self.assertFalse(
            [name for name in archive.namelist() if "private-note" in name],
            "and it is simply absent from their archive",
        )
        self.assertTrue([name for name in archive.namelist() if "shared" in name])

    def test_13_the_archive_carries_a_folder_per_heading(self):
        request = self._new_request()
        self._attach_to_line(request.document_ids[0], "registration.pdf")
        archive = zipfile.ZipFile(io.BytesIO(request._dossier_zip_bytes()))
        root = request._dossier_filename()
        self.assertEqual(root, "DMA_ACC_%s" % request.name.split("/", 2)[-1].replace("/", "_"))
        for name in archive.namelist():
            self.assertTrue(
                name.startswith(root + "/"),
                "everything sits under one folder named after the file",
            )
        self.assertTrue(
            [name for name in archive.namelist() if "02_prerequisites" in name],
            "and the headings are numbered the way the printed index numbers them",
        )

    # ------------------------------------------------------------------
    # The printed index
    # ------------------------------------------------------------------
    def test_14_the_printed_index_renders_and_names_what_is_missing(self):
        # Left standing at the Certifications step: that is where a document is
        # recorded as missing, and where the printed index earns its keep.
        request = self._drive_to_cert_check(self._new_request())
        line = request.document_ids[0]
        line.with_user(self.user_cert).action_mark_missing()
        report = self.env.ref("dma_accreditation.action_report_dossier_index")
        html, content_type = report._render_qweb_html(
            "dma_accreditation.action_report_dossier_index", request.ids,
        )
        html = html.decode() if isinstance(html, bytes) else html
        self.assertEqual(content_type, "html")
        self.assertIn(request.name, html)
        self.assertIn(request.partner_id.name, html)
        self.assertIn("فهرس ملف التفويض", html, "Arabic first, like every DMA document")
        self.assertIn(line.type_id.name, html)
        self.assertIn(
            request.verification_token, html,
            "and it carries the verification QR of the file",
        )

    def test_15_the_index_the_screen_the_report_and_the_archive_agree(self):
        request = self._drive_to_office_granted(self._new_request())
        self._attach_to_line(request.document_ids[0], "registration.pdf")

        from_screen = request.dossier_payload
        from_report = self.env[
            "report.dma_accreditation.report_dossier_index"
        ]._get_report_values(request.ids)["dossier_data"][request.id]

        self.assertEqual(from_screen["file_count"], from_report["file_count"])
        self.assertEqual(from_screen["missing"], from_report["missing"])
        self.assertEqual(
            [section["key"] for section in from_screen["sections"]],
            [section["key"] for section in from_report["sections"]],
            "three renderings of one reading of the file",
        )

    def test_15b_the_archive_carries_its_own_cover_sheet(self):
        """And it is HTML, so building an archive never waits on a PDF engine."""
        request = self._drive_to_office_granted(self._new_request())
        archive = zipfile.ZipFile(io.BytesIO(request._dossier_zip_bytes()))
        index = [name for name in archive.namelist() if name.endswith("_index.html")]
        self.assertEqual(len(index), 1, "one cover sheet, at the top of the archive")
        self.assertTrue(
            index[0].split("/")[-1].startswith("00_"),
            "numbered so it sorts above the evidence",
        )
        body = archive.read(index[0]).decode()
        self.assertIn(request.name, body)
        self.assertIn(request.partner_id.name, body)
        self.assertIn("فهرس ملف التفويض", body)

    def test_16_an_empty_file_still_produces_a_dossier(self):
        request = self._new_request()
        payload = request.dossier_payload
        self.assertEqual(payload["file_count"], 0)
        self.assertTrue(payload["missing"], "an empty dossier says what is missing")
        archive = zipfile.ZipFile(io.BytesIO(request._dossier_zip_bytes()))
        self.assertIsNone(
            archive.testzip(), "and it is still a valid archive",
        )

    def test_17_dossier_counts_are_available_to_the_form(self):
        request = self._new_request()
        self._attach_to_line(request.document_ids[0], "one.pdf")
        request.invalidate_recordset()
        self.assertEqual(request.dossier_document_count, 1)
        self.assertEqual(
            request.dossier_missing_count, request.required_document_count,
        )
