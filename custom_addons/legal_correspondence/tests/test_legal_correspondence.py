from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalCorrespondence(TransactionCase):
    """The four rules that make this a register rather than a table."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.body = cls.env["legal.gov.body"].create(
            {
                "name": "الهيئة العامة للضرائب",
                "code": "TEST-GCT",
                "body_type_id": cls.env.ref("legal_core.body_type_commission").id,
                "jurisdiction_id": cls.env.ref("legal_core.jurisdiction_iq_federal").id,
                "salutation": "السيد رئيس الهيئة المحترم",
                "letterhead_recipient": "الهيئة العامة للضرائب\nقسم الشركات",
            }
        )
        cls.register = cls.env["legal.register"].create(
            {
                "name": "سجل الصادر - اختبار",
                "code": "TEST-OUT",
                "direction": "out",
                "prefix": "ق",
                "company_id": cls.company.id,
            }
        )
        cls.kind_out = cls.env.ref("legal_correspondence.kind_out_letter")
        cls.kind_in = cls.env.ref("legal_correspondence.kind_in_letter")
        cls.kind_ack = cls.env.ref("legal_correspondence.kind_acknowledgement")
        cls.kind_phone = cls.env.ref("legal_correspondence.kind_phone_note")
        cls.entity = cls.env["legal.entity"].create(
            {
                "name": "شركة الاختبار المحدودة",
                "jurisdiction_id": cls.env.ref("legal_core.jurisdiction_iq_federal").id,
            }
        )
        cls.today = date.today()
        cls.year = cls.today.year

    # The reply clock reads the wall clock, so every date below is relative to
    # today. A fixture pinned to a literal year passes for a month and then
    # starts reporting a letter posted this morning as late.
    def _new_entry(self, **overrides):
        values = {
            "register_id": self.register.id,
            "kind_id": self.kind_out.id,
            "direction": "out",
            "gov_body_id": self.body.id,
            "subject": "طلب براءة ذمة",
            "our_date": self.today,
        }
        values.update(overrides)
        return self.env["legal.correspondence"].create(values)

    # ------------------------------------------------------------------
    # Numbering
    # ------------------------------------------------------------------
    def test_numbering_starts_from_the_register_prefix_and_year(self):
        first = self._new_entry()
        first.action_register()
        self.assertEqual(first.our_number, "ق/%d/0001" % self.year)
        self.assertEqual(first.sequence_prefix, "ق/%d/" % self.year)
        self.assertEqual(first.sequence_number, 1)

        second = self._new_entry(subject="تذكير بطلب براءة الذمة")
        second.action_register()
        self.assertEqual(second.our_number, "ق/%d/0002" % self.year)

    def test_numbering_resets_with_the_calendar_year(self):
        """The reset is deduced from the shape of the last number, not configured."""
        self._new_entry().action_register()
        next_year = self._new_entry(our_date=date(self.year + 1, 1, 6))
        next_year.action_register()
        self.assertEqual(next_year.our_number, "ق/%d/0001" % (self.year + 1))

    def test_a_typed_number_continues_the_chain(self):
        """A department migrating in October types its own number and carries on."""
        migrated = self._new_entry(our_number="ق/%d/1247" % self.year)
        migrated.action_register()
        self.assertEqual(migrated.our_number, "ق/%d/1247" % self.year)

        following = self._new_entry(subject="كتاب لاحق")
        following.action_register()
        self.assertEqual(following.our_number, "ق/%d/1248" % self.year)

    def test_a_number_must_agree_with_its_date(self):
        with self.assertRaises(ValidationError):
            self._new_entry(our_number="ق/%d/0148" % (self.year - 1), our_date=self.today)

    # ------------------------------------------------------------------
    # A contact note consumes no number
    # ------------------------------------------------------------------
    def test_contact_note_takes_no_register_number(self):
        letter = self._new_entry(reply_expected=True, reply_days=7)
        letter.action_register()
        note = self.env["legal.contact.note.wizard"].create(
            {
                "correspondence_id": letter.id,
                "kind_id": self.kind_phone.id,
                "gov_body_id": self.body.id,
                "contact_date": self.today,
                "spoke_to": "أبو أحمد - معاون مدير القسم",
                "said": "الإضبارة لدى المستشار القانوني.",
                "promised_on": self.today + timedelta(days=29),
            }
        )
        action = note.action_record()
        recorded = self.env["legal.correspondence"].browse(action["res_id"])
        self.assertEqual(recorded.state, "registered")
        self.assertFalse(recorded.our_number, "a contact note never touched the book")
        self.assertFalse(recorded.register_id)
        self.assertEqual(recorded.spoke_to, "أبو أحمد - معاون مدير القسم")

        # And the promise moves the clock rather than being decoration.
        letter.invalidate_recordset()
        self.assertEqual(letter.reply_due_on, self.today + timedelta(days=29))

    def test_a_contact_note_may_not_be_given_a_number(self):
        with self.assertRaises(ValidationError):
            self.env["legal.correspondence"].create(
                {
                    "kind_id": self.kind_phone.id,
                    "direction": "internal",
                    "gov_body_id": self.body.id,
                    "subject": "اتصال",
                    "our_number": "ق/%d/0900" % self.year,
                    "our_date": self.today,
                }
            )

    # ------------------------------------------------------------------
    # The write lock
    # ------------------------------------------------------------------
    def test_registered_entry_refuses_a_new_number_over_rpc(self):
        entry = self._new_entry()
        entry.action_register()
        for values in (
            {"our_number": "ق/%d/9999" % self.year},
            {"our_date": self.today - timedelta(days=1)},
            {"register_id": self.register.copy({"code": "TEST-OUT-2"}).id},
            {"direction": "in"},
        ):
            with self.assertRaises(UserError):
                entry.write(values)

    def test_restating_an_unchanged_value_is_not_refused(self):
        """A form that reloads and saves sends every field back; that must work."""
        entry = self._new_entry()
        entry.action_register()
        entry.write({"our_number": entry.our_number, "our_date": entry.our_date})
        self.assertEqual(entry.our_number, "ق/%d/0001" % self.year)

    def test_a_draft_may_still_be_corrected(self):
        entry = self._new_entry()
        corrected = self.today - timedelta(days=2)
        entry.write({"our_date": corrected, "direction": "internal"})
        self.assertEqual(entry.our_date, corrected)

    # ------------------------------------------------------------------
    # Void, never delete
    # ------------------------------------------------------------------
    def test_a_registered_entry_cannot_be_deleted(self):
        entry = self._new_entry()
        entry.action_register()
        with self.assertRaises(UserError):
            entry.unlink()

    def test_a_draft_may_be_deleted(self):
        entry = self._new_entry()
        entry.unlink()

    def test_voiding_without_a_reason_is_refused(self):
        entry = self._new_entry()
        entry.action_register()
        with self.assertRaises(ValidationError):
            entry.write({"state": "void"})
            entry.flush_recordset()
        entry.invalidate_recordset()

    def test_voiding_keeps_the_number(self):
        entry = self._new_entry()
        entry.action_register()
        number = entry.our_number

        wizard = self.env["legal.correspondence.void.wizard"].create(
            {"correspondence_id": entry.id, "reason": "كتاب مكرر - صدر بالرقم السابق."}
        )
        wizard.action_void()
        self.assertEqual(entry.state, "void")
        self.assertEqual(entry.our_number, number, "a void keeps its place in the book")

        # And the next letter takes the next number, never the voided one.
        following = self._new_entry(subject="الكتاب البديل")
        following.action_register()
        self.assertEqual(following.our_number, "ق/%d/0002" % self.year)

    # ------------------------------------------------------------------
    # The reply clock
    # ------------------------------------------------------------------
    def test_a_receipt_is_not_an_answer(self):
        letter = self._new_entry(reply_expected=True, reply_days=5)
        letter.action_register()
        self.assertEqual(letter.reply_state, "awaiting")

        receipt = self._new_entry(
            kind_id=self.kind_ack.id,
            direction="in",
            subject="وصل استلام",
            reply_to_id=letter.id,
            our_date=self.today,
        )
        receipt.action_register()
        letter.invalidate_recordset()
        self.assertEqual(
            letter.reply_state,
            "awaiting",
            "a وصل proves receipt and closes nothing",
        )

        answer = self._new_entry(
            kind_id=self.kind_in.id,
            direction="in",
            subject="جواب الهيئة",
            reply_to_id=letter.id,
            our_date=self.today,
        )
        answer.action_register()
        letter.invalidate_recordset()
        self.assertEqual(letter.reply_state, "answered")

    def test_reply_state_is_searchable(self):
        letter = self._new_entry(reply_expected=True, reply_days=5)
        letter.action_register()
        found = self.env["legal.correspondence"].search(
            [("reply_state", "=", "awaiting"), ("id", "=", letter.id)]
        )
        self.assertEqual(found, letter)
        self.assertFalse(
            self.env["legal.correspondence"].search(
                [("reply_state", "=", "answered"), ("id", "=", letter.id)]
            )
        )

    # ------------------------------------------------------------------
    # The key to the drawer
    # ------------------------------------------------------------------
    def test_only_the_registrar_may_allocate_a_number(self):
        registrar_group = self.env.ref("legal_correspondence.group_legal_registrar")
        self.register.write_group_id = registrar_group

        clerk = self.env["res.users"].create(
            {
                "name": "كاتب",
                "login": "legal_clerk_test",
                "group_ids": [(6, 0, [self.env.ref("legal_core.group_legal_clerk").id])],
            }
        )
        entry = self._new_entry()
        with self.assertRaises(UserError):
            entry.with_user(clerk).action_register()

        clerk.write({"group_ids": [(4, registrar_group.id)]})
        entry.with_user(clerk).action_register()
        self.assertEqual(entry.state, "registered")

    # ------------------------------------------------------------------
    # The artefact the ministry actually receives
    # ------------------------------------------------------------------
    def test_the_official_letter_renders(self):
        """Both letterhead variants must compile and carry the register number.

        A QWeb error surfaces at the moment somebody presses Print, in front of
        a clerk holding an envelope, so it is worth catching here instead.
        """
        signatory = self.env["legal.signatory"].create(
            {
                "name": "علي حسن",
                "title": "المدير المفوض",
                "entity_id": self.entity.id,
            }
        )
        template = self.env["legal.letter.template"].create(
            {
                "name": "طلب براءة ذمة",
                "code": "TEST-CLEARANCE",
                "body_id": self.body.id,
                "subject_template": "طلب براءة ذمة عن {today}",
                "body_template": "<p>نرجو تزويدنا ببراءة ذمة باسم {entity}.</p>",
                "signatory_id": signatory.id,
                "show_subject_table": True,
                "cc_list": "القسم القانوني\nالأرشيف",
            }
        )
        entry = self._new_entry(
            letter_template_id=template.id,
            signatory_id=signatory.id,
            line_ids=[(0, 0, {"name": "أحمد صالح", "reference": "A1234567"})],
        )
        entry.action_register()
        self.assertTrue(entry.snapshot_html, "the filed copy is frozen at issue")

        report = self.env["ir.actions.report"]
        for report_ref in (
            "legal_correspondence.report_official_letter",
            "legal_correspondence.report_official_letter_drawn",
        ):
            html = report._render_qweb_html(report_ref, entry.ids)[0].decode()
            self.assertIn(entry.our_number, html)
            self.assertIn("م /", html)
            self.assertIn("نسخة منه إلى", html)
            self.assertIn("صفحة", html)

    def test_arabic_indic_numerals_are_a_company_setting(self):
        entry = self._new_entry()
        entry.action_register()
        self.assertEqual(entry._localise_numerals("1247"), "1247")
        self.company.legal_numeral_system = "arabic"
        self.assertEqual(entry._localise_numerals("1247"), "١٢٤٧")
        self.company.legal_numeral_system = "western"

    def test_hijri_conversion_matches_the_known_dates(self):
        """Off by default, but wrong dates on a letter are not acceptable."""
        self.assertEqual(
            self.env["legal.correspondence"]._to_hijri(date(2024, 4, 10)),
            "01/10/1445",
        )
        self.assertEqual(
            self.env["legal.correspondence"]._to_hijri(date(2025, 3, 1)),
            "01/09/1446",
        )
