from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalContract(TransactionCase):
    """The contract lifecycle: the walk, the gates, the obligations and the trail."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.jurisdiction = cls.env["legal.jurisdiction"].create(
            {"name": "Federal Iraq", "code": "TEST-CON-IQ"}
        )
        cls.entity = cls.env["legal.entity"].create(
            {
                "name": "شركة العقود المحدودة",
                "name_en": "Contracts Test Co",
                "jurisdiction_id": cls.jurisdiction.id,
                "company_id": cls.company.id,
            }
        )
        cls.contract_type = cls.env["legal.contract.type"].create(
            {"name": "Service Agreement", "code": "TEST-SERVICE"}
        )
        cls.counterparty = cls.env["res.partner"].create(
            {"name": "شركة الطرف الثاني", "is_company": True}
        )

        cls.clerk = cls._make_user("con_clerk", "legal_core.group_legal_clerk")
        cls.approver = cls._make_user("con_approver", "legal_core.group_legal_approver")
        cls.manager = cls._make_user("con_manager", "legal_core.group_legal_manager")
        cls.auditor = cls._make_user("con_auditor", "legal_core.group_legal_auditor")

    @classmethod
    def _make_user(cls, login, group_xmlid):
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "group_ids": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(group_xmlid).id,
                        ],
                    )
                ],
            }
        )

    @classmethod
    def _make_contract(cls, **values):
        base = {
            "title": "Test contract",
            "type_id": cls.contract_type.id,
            "entity_id": cls.entity.id,
            "company_id": cls.company.id,
            "party_ids": [
                (0, 0, {"partner_id": cls.counterparty.id, "role": "counterparty"})
            ],
        }
        base.update(values)
        return cls.env["legal.contract"].create(base)

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    def test_a_new_contract_takes_a_reference(self):
        contract = self._make_contract()
        self.assertTrue(contract.name.startswith("CON/"))
        self.assertEqual(contract.state, "received")
        self.assertEqual(contract.counterparty_id, self.counterparty)
        self.assertFalse(contract.is_closed)

    # ------------------------------------------------------------------
    # (a) The auditor is read-only through every path
    # ------------------------------------------------------------------
    def test_the_auditor_can_read_but_never_write(self):
        contract = self._make_contract()
        # Reading is allowed.
        contract.with_user(self.auditor).read(["title", "state"])
        # Writing, creating and unlinking are refused.
        with self.assertRaises(AccessError):
            contract.with_user(self.auditor).write({"title": "changed"})
        with self.assertRaises(AccessError):
            self.env["legal.contract"].with_user(self.auditor).create(
                {"title": "x", "type_id": self.contract_type.id}
            )
        with self.assertRaises(AccessError):
            contract.with_user(self.auditor).unlink()

    # ------------------------------------------------------------------
    # (b) A clerk cannot make the gated moves
    # ------------------------------------------------------------------
    def test_a_clerk_cannot_grant_internal_approval(self):
        contract = self._make_contract(state="internal_approval")
        with self.assertRaises(UserError):
            contract.with_user(self.clerk).action_grant_internal_approval()
        # The approver may.
        contract.with_user(self.approver).action_grant_internal_approval()
        self.assertEqual(contract.state, "counterparty_review")

    def test_only_the_manager_may_terminate(self):
        contract = self._make_contract(state="active")
        with self.assertRaises(UserError):
            contract.with_user(self.clerk).action_terminate()
        with self.assertRaises(UserError):
            contract.with_user(self.approver).action_terminate()
        contract.with_user(self.manager).action_terminate()
        self.assertEqual(contract.state, "terminated")
        self.assertTrue(contract.is_closed)

    # ------------------------------------------------------------------
    # (c) The state transitions
    # ------------------------------------------------------------------
    def test_the_happy_path_walks_to_active(self):
        contract = self._make_contract()
        contract.action_submit_review()
        self.assertEqual(contract.state, "legal_review")
        contract.action_start_negotiation()
        self.assertEqual(contract.state, "negotiation")
        contract.action_request_internal_approval()
        self.assertEqual(contract.state, "internal_approval")
        contract.with_user(self.approver).action_grant_internal_approval()
        self.assertEqual(contract.state, "counterparty_review")
        contract.action_counterparty_returned()
        self.assertEqual(contract.state, "to_sign")
        contract.with_user(self.approver).action_mark_signed()
        self.assertEqual(contract.state, "signed")
        self.assertEqual(contract.signature_status, "ours_signed")
        self.assertTrue(contract.signature_date)
        contract.action_activate()
        self.assertEqual(contract.state, "active")
        self.assertTrue(contract.commencement_date)

    def test_approval_needs_a_counterparty(self):
        contract = self._make_contract(party_ids=[], state="negotiation")
        with self.assertRaises(UserError):
            contract.action_request_internal_approval()

    def test_a_move_from_the_wrong_state_is_refused(self):
        contract = self._make_contract(state="active")
        with self.assertRaises(UserError):
            contract.action_submit_review()

    # ------------------------------------------------------------------
    # (c) Expiry and overdue logic
    # ------------------------------------------------------------------
    def test_a_contract_past_its_term_is_expired_by_the_cron(self):
        contract = self._make_contract(
            state="active",
            effective_date=fields.Date.context_today(self.env["legal.contract"])
            - relativedelta(years=1),
            expiry_date=fields.Date.context_today(self.env["legal.contract"])
            - relativedelta(days=1),
        )
        self.assertEqual(contract.expiry_state, "expired")
        self.env["legal.contract"]._cron_expire()
        self.assertEqual(contract.state, "expired")

    def test_an_expiring_contract_reports_its_validity(self):
        today = fields.Date.context_today(self.env["legal.contract"])
        contract = self._make_contract(
            state="active",
            effective_date=today - relativedelta(months=11),
            expiry_date=today + relativedelta(days=10),
            notice_days=30,
        )
        self.assertEqual(contract.expiry_state, "expiring")
        self.assertLessEqual(contract.days_to_expiry, 10)

    def test_a_one_off_obligation_past_due_is_overdue(self):
        contract = self._make_contract(state="active")
        today = fields.Date.context_today(self.env["legal.contract"])
        obligation = self.env["legal.contract.obligation"].create(
            {
                "contract_id": contract.id,
                "name": "Deliver certificate",
                "frequency": "one_off",
                "due_date": today - relativedelta(days=5),
            }
        )
        self.assertTrue(obligation.is_overdue)
        # And it is findable by the search that the board filter runs.
        found = self.env["legal.contract.obligation"].search(
            [("is_overdue", "=", True), ("id", "=", obligation.id)]
        )
        self.assertEqual(found, obligation)

    # ------------------------------------------------------------------
    # Recurring generation
    # ------------------------------------------------------------------
    def test_recurring_generation_is_idempotent(self):
        contract = self._make_contract(state="active")
        today = fields.Date.context_today(self.env["legal.contract"])
        obligation = self.env["legal.contract.obligation"].create(
            {
                "contract_id": contract.id,
                "name": "Monthly rent",
                "frequency": "monthly",
                "start_date": today - relativedelta(months=1),
                "amount": 5000000.0,
            }
        )
        created = obligation._generate()
        self.assertTrue(created)
        first = len(obligation.instance_ids)
        self.assertEqual(obligation._generate(), 0)
        obligation.invalidate_recordset()
        self.assertEqual(len(obligation.instance_ids), first)

    def test_an_occurrence_cannot_be_recorded_twice(self):
        contract = self._make_contract(state="active")
        obligation = self.env["legal.contract.obligation"].create(
            {"contract_id": contract.id, "name": "x", "frequency": "monthly"}
        )
        values = {
            "obligation_id": obligation.id,
            "period_key": "2026-03-01",
            "due_date": "2026-03-01",
            "company_id": self.company.id,
        }
        self.env["legal.contract.obligation.instance"].create(values)
        self.env["legal.contract.obligation.instance"].flush_model()
        with self.assertRaises(Exception):
            self.env["legal.contract.obligation.instance"].create(values)
            self.env["legal.contract.obligation.instance"].flush_model()

    def test_a_past_due_occurrence_is_marked_late(self):
        contract = self._make_contract(state="active")
        obligation = self.env["legal.contract.obligation"].create(
            {"contract_id": contract.id, "name": "x", "frequency": "monthly"}
        )
        today = fields.Date.context_today(self.env["legal.contract"])
        instance = self.env["legal.contract.obligation.instance"].create(
            {
                "obligation_id": obligation.id,
                "period_key": "OVERDUE",
                "due_date": today - relativedelta(days=3),
                "company_id": self.company.id,
            }
        )
        self.env["legal.contract.obligation.instance"]._cron_mark_late()
        self.assertEqual(instance.state, "late")

    # ------------------------------------------------------------------
    # Amendments never edit the original in place
    # ------------------------------------------------------------------
    def test_an_applied_amendment_moves_the_current_value_only(self):
        contract = self._make_contract(value=100000000.0)
        self.assertEqual(contract.current_value, 100000000.0)
        amendment = self.env["legal.contract.modification"].create(
            {
                "contract_id": contract.id,
                "number": "Addendum 1",
                "description": "Scope increase",
                "value_change": 25000000.0,
            }
        )
        # Draft: the original value is untouched and current value unchanged.
        self.assertEqual(contract.current_value, 100000000.0)
        # A clerk cannot apply it.
        with self.assertRaises(UserError):
            amendment.with_user(self.clerk).action_apply()
        amendment.with_user(self.approver).action_apply()
        self.assertEqual(amendment.state, "applied")
        self.assertEqual(contract.value, 100000000.0)
        self.assertEqual(contract.current_value, 125000000.0)

    def test_an_amendment_can_extend_the_term(self):
        contract = self._make_contract(
            effective_date="2026-01-01", expiry_date="2026-12-31"
        )
        amendment = self.env["legal.contract.modification"].create(
            {
                "contract_id": contract.id,
                "number": "Addendum 1",
                "description": "Extend by a year",
                "new_expiry_date": "2027-12-31",
            }
        )
        amendment.with_user(self.approver).action_apply()
        self.assertEqual(str(contract.expiry_date), "2027-12-31")

    # ------------------------------------------------------------------
    # (d) A constraint
    # ------------------------------------------------------------------
    def test_a_contract_cannot_end_before_it_begins(self):
        with self.assertRaises(ValidationError):
            self._make_contract(
                effective_date="2026-06-01", expiry_date="2026-01-01"
            )

    # ------------------------------------------------------------------
    # Signing files the document into the register
    # ------------------------------------------------------------------
    def test_the_sign_wizard_files_a_register_document(self):
        contract = self._make_contract(state="to_sign")
        wizard = (
            self.env["legal.contract.sign"]
            .with_user(self.approver)
            .create({"contract_id": contract.id})
        )
        wizard.action_confirm()
        self.assertTrue(contract.signed_document_id)
        self.assertEqual(contract.signature_status, "fully_signed")
        self.assertEqual(contract.state, "signed")
        self.assertEqual(
            contract.signed_document_id.document_type_id,
            self.env.ref("legal_contract.doctype_signed_contract"),
        )
        # A clerk cannot file a signed contract.
        other = self._make_contract(state="to_sign")
        wiz2 = (
            self.env["legal.contract.sign"]
            .with_user(self.clerk)
            .create({"contract_id": other.id})
        )
        with self.assertRaises(UserError):
            wiz2.action_confirm()

    # ------------------------------------------------------------------
    # The correspondence edge
    # ------------------------------------------------------------------
    def test_a_letter_can_be_filed_under_a_contract(self):
        contract = self._make_contract(state="active")
        letter = self.env["legal.correspondence"].create(
            {
                "kind_id": self.env.ref("legal_correspondence.kind_in_letter").id,
                "direction": "in",
                "subject": "A letter about the contract",
                "entity_id": self.entity.id,
                "contract_id": contract.id,
            }
        )
        self.assertEqual(contract.correspondence_count, 1)
        self.assertEqual(letter.action_open_contract()["res_id"], contract.id)
