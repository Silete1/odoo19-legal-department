from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import LegalProcedureCommon


@tagged("post_install", "-at_install")
class TestCaseEngine(LegalProcedureCommon):
    """The transactional layer: the walk, the gate, the round and the trail."""

    def test_a_new_file_lands_on_the_first_step(self):
        case = self._make_case()
        self.assertEqual(case.step_id, self.step_prepare)
        self.assertEqual(case.kind, "internal")
        self.assertEqual(case.body_id, self.body)
        self.assertEqual(case.procedure_version, self.procedure.version)
        self.assertEqual(case.round, 1)
        self.assertFalse(case.is_closed)

    def test_opening_a_file_writes_exactly_one_trail_entry(self):
        case = self._make_case()
        self.assertEqual(len(case.log_ids), 1)
        self.assertEqual(case.log_ids.action, "open")
        self.assertEqual(case.log_ids.to_step_id, self.step_prepare)

    def test_stage_entered_on_is_read_off_the_trail(self):
        case = self._make_case()
        self.assertEqual(case.stage_entered_on, case.log_ids.logged_on)
        case.action_advance()
        closures = case.log_ids.filtered("closes_step").sorted("logged_on")
        self.assertEqual(case.stage_entered_on, closures[-1].logged_on)

    def test_an_entry_that_does_not_move_the_file_leaves_the_clock_alone(self):
        """A fee paid or a note taken is not a step closing."""
        case = self._make_case()
        entered = case.stage_entered_on
        case._log("fee", "Paid something", closes_step=False)
        case.invalidate_recordset()
        self.assertEqual(case.stage_entered_on, entered)

    def test_the_advance_is_synthesised_from_the_ordering(self):
        case = self._make_case()
        case.action_advance()
        self.assertEqual(case.step_id, self.step_submit)
        self.assertEqual(case.kind, "at_body")
        case.action_advance()
        self.assertEqual(case.step_id, self.step_done)
        self.assertTrue(case.is_closed)
        self.assertEqual(case.outcome, "granted")

    def test_a_terminal_step_files_the_document_it_produced(self):
        case = self._make_case()
        case.action_advance()
        case.action_advance()
        self.assertTrue(case.result_document_id)
        self.assertEqual(case.result_document_id.document_type_id, self.result_type)
        # In the permanent register, not on the file: an expiring registration
        # must raise one alert rather than one per case that references it.
        self.assertEqual(case.result_document_id.entity_id, self.entity)

    def test_step_id_cannot_be_written_over_rpc(self):
        """readonly is a client hint; this is the rule."""
        case = self._make_case()
        with self.assertRaises(UserError):
            case.write({"step_id": self.step_done.id})
        # Even as a superuser, because the usual escape hatch is the hole an
        # auditor looks for.
        with self.assertRaises(UserError):
            case.sudo().write({"step_id": self.step_done.id})
        self.assertEqual(case.step_id, self.step_prepare)

    def test_the_engine_itself_may_move_the_file(self):
        case = self._make_case()
        case._engine().write({"step_id": self.step_submit.id})
        self.assertEqual(case.step_id, self.step_submit)

    def test_a_blocking_document_stops_the_advance(self):
        self.env["legal.doc.requirement"].create(
            {
                "document_type_id": self.document_type.id,
                "procedure_type_id": self.procedure.id,
                "is_required": True,
            }
        )
        case = self._make_case()
        self.assertTrue(case.document_ids)
        line = case.document_ids
        self.assertEqual(line.line_status, "missing")
        self.assertTrue(line.is_blocking)
        self.assertFalse(case.ready_to_advance)
        self.assertIn(self.document_type.display_name, case.blocker_summary)
        with self.assertRaises(UserError):
            case.action_advance()

    def test_a_register_entry_satisfies_the_line(self):
        self.env["legal.doc.requirement"].create(
            {
                "document_type_id": self.document_type.id,
                "procedure_type_id": self.procedure.id,
            }
        )
        case = self._make_case()
        document = self._register_document(
            expiry=fields.Date.context_today(case) + relativedelta(years=1)
        )
        case.document_ids.write({"company_document_id": document.id, "accepted": True})
        self.assertEqual(case.document_ids.line_status, "accepted")
        self.assertFalse(case.document_ids.is_blocking)
        self.assertTrue(case.ready_to_advance)
        case.action_advance()
        self.assertEqual(case.step_id, self.step_submit)

    def test_an_expired_register_entry_does_not_satisfy_the_line(self):
        self.env["legal.doc.requirement"].create(
            {
                "document_type_id": self.document_type.id,
                "procedure_type_id": self.procedure.id,
            }
        )
        case = self._make_case()
        document = self._register_document(
            expiry=fields.Date.context_today(case) - relativedelta(days=1)
        )
        case.document_ids.write({"company_document_id": document.id, "accepted": True})
        self.assertEqual(case.document_ids.line_status, "expired")
        self.assertTrue(case.document_ids.is_blocking)

    def test_a_conditional_requirement_only_appears_when_it_applies(self):
        """The tier.definition idiom: configuration, never a Python if-branch."""
        iraq = self.env.ref("base.iq", raise_if_not_found=False)
        foreign = self.env.ref("base.gb", raise_if_not_found=False)
        if not (iraq and foreign):
            self.skipTest("Country data unavailable")
        self.env["legal.doc.requirement"].create(
            {
                "document_type_id": self.document_type.id,
                "procedure_type_id": self.procedure.id,
                "applicability_domain": "[('subject_ids.nationality_id', '!=', %s)]" % iraq.id,
            }
        )
        local_case = self._make_case()
        local_case.write(
            {
                "subject_ids": [
                    (0, 0, {"name_ar": "أحمد", "nationality_id": iraq.id}),
                ]
            }
        )
        local_case._sync_document_lines()
        self.assertFalse(local_case.document_ids)

        foreign_case = self._make_case()
        foreign_case.write(
            {
                "subject_ids": [
                    (0, 0, {"name_ar": "جون", "nationality_id": foreign.id}),
                ]
            }
        )
        foreign_case._sync_document_lines()
        self.assertTrue(foreign_case.document_ids)

    def test_a_person_whose_passport_expires_too_soon_blocks_the_file(self):
        case = self._make_case()
        case.write(
            {
                "subject_ids": [
                    (
                        0,
                        0,
                        {
                            "name_ar": "خبير أجنبي",
                            "document_number": "X1234567",
                            "document_expiry": fields.Date.context_today(case)
                            + relativedelta(months=2),
                            "minimum_validity_months": 6,
                        },
                    )
                ]
            }
        )
        self.assertFalse(case.ready_to_advance)
        self.assertIn("expires", case.blocker_summary)

    def test_a_return_opens_a_round_and_keeps_everything(self):
        self.env["legal.doc.requirement"].create(
            {
                "document_type_id": self.document_type.id,
                "procedure_type_id": self.procedure.id,
            }
        )
        case = self._make_case()
        document = self._register_document(
            expiry=fields.Date.context_today(case) + relativedelta(years=1)
        )
        case.document_ids.write({"company_document_id": document.id, "accepted": True})
        case.action_advance()
        self.assertEqual(case.step_id, self.step_submit)

        lines_before = len(case.document_ids)
        case._return_for_correction(self.step_prepare, "نقص في المستمسكات")

        self.assertEqual(case.round, 2)
        self.assertEqual(case.step_id, self.step_prepare)
        self.assertTrue(case.sla_paused)
        # Superseded, never deleted: what they objected to is the only thing the
        # correction can be measured against.
        self.assertTrue(any(line.superseded for line in case.document_ids))
        self.assertGreater(len(case.document_ids), lines_before)
        self.assertTrue(case.log_ids.filtered(lambda entry: entry.action == "return"))

    def test_a_return_without_a_reason_is_refused(self):
        case = self._make_case()
        case.action_advance()
        with self.assertRaises(UserError):
            case._return_for_correction(self.step_prepare, "   ")

    def test_the_trail_cannot_be_edited_or_deleted(self):
        case = self._make_case()
        entry = case.log_ids[0]
        with self.assertRaises(UserError):
            entry.write({"description": "something else"})
        with self.assertRaises(UserError):
            entry.sudo().write({"description": "something else"})
        with self.assertRaises(UserError):
            entry.sudo().unlink()

    def test_the_trail_snapshots_the_configuration_of_the_day(self):
        case = self._make_case()
        entry = case.log_ids[0]
        self.assertEqual(entry.step_code, self.step_prepare.code)
        self.assertEqual(entry.step_name, self.step_prepare.name)
        # Renaming the step afterwards must not rewrite what happened.
        self.step_prepare.name = "اسم جديد"
        self.assertEqual(entry.step_name, "تحضير الملف")

    def test_a_transition_is_only_offered_where_it_applies(self):
        case = self._make_case()
        self.assertFalse(case.available_transition_ids)
        case.action_advance()
        self.assertIn(self.transition_return, case.available_transition_ids)

    def test_a_valid_power_of_attorney_is_required_when_the_move_says_so(self):
        move = self.env["legal.procedure.transition"].create(
            {
                "name": "التقديم بالوكالة",
                "procedure_type_id": self.procedure.id,
                "from_step_id": self.step_prepare.id,
                "to_step_id": self.step_submit.id,
                "require_valid_poa": True,
            }
        )
        case = self._make_case()
        with self.assertRaises(UserError):
            case._fire(move)

        agent = self.env["res.partner"].create({"name": "الوكيل"})
        poa = self.env["legal.poa"].create(
            {
                "name": "وكالة عامة",
                "number": "TEST-POA-1",
                "entity_id": self.entity.id,
                "agent_partner_id": agent.id,
                "issue_date": fields.Date.context_today(case),
                "expiry_date": fields.Date.context_today(case) + relativedelta(years=1),
                "company_id": self.company.id,
            }
        )
        poa.action_activate()
        case.poa_id = poa
        case._fire(move)
        self.assertEqual(case.step_id, self.step_submit)

    def test_a_revoked_power_of_attorney_blocks_the_move(self):
        move = self.env["legal.procedure.transition"].create(
            {
                "name": "التقديم بالوكالة",
                "procedure_type_id": self.procedure.id,
                "from_step_id": self.step_prepare.id,
                "to_step_id": self.step_submit.id,
                "require_valid_poa": True,
            }
        )
        agent = self.env["res.partner"].create({"name": "وكيل معزول"})
        case = self._make_case()
        poa = self.env["legal.poa"].create(
            {
                "name": "وكالة ملغاة",
                "entity_id": self.entity.id,
                "agent_partner_id": agent.id,
                "issue_date": fields.Date.context_today(case),
                "company_id": self.company.id,
            }
        )
        poa.action_activate()
        poa.write(
            {
                "state": "revoked",
                "revocation_reason": "انتهاء الخدمة",
                "revoked_on": fields.Date.context_today(case),
            }
        )
        case.poa_id = poa
        with self.assertRaises(UserError):
            case._fire(move)

    def test_a_power_of_attorney_cannot_be_deleted(self):
        agent = self.env["res.partner"].create({"name": "وكيل"})
        poa = self.env["legal.poa"].create(
            {
                "name": "وكالة",
                "entity_id": self.entity.id,
                "agent_partner_id": agent.id,
                "company_id": self.company.id,
            }
        )
        with self.assertRaises(UserError):
            poa.unlink()

    def test_fees_are_raised_and_block_where_configured(self):
        self.env["legal.fee.rule"].create(
            {
                "name": "رسم التسجيل",
                "procedure_type_id": self.procedure.id,
                "step_id": self.step_prepare.id,
                "amount": 25000.0,
            }
        )
        case = self._make_case()
        self.assertEqual(len(case.fee_ids), 1)
        self.assertEqual(case.fee_total, 25000.0)
        self.assertEqual(case.fee_unpaid, 25000.0)
        self.assertFalse(case.ready_to_advance)
        case.fee_ids.action_mark_paid()
        self.assertEqual(case.fee_ids.state, "paid")
        self.assertEqual(case.fee_unpaid, 0.0)
        self.assertTrue(case.ready_to_advance)

    def test_the_counter_walk_is_instantiated_and_blocks(self):
        self.env["legal.procedure.step.check"].create(
            {
                "name": "ختم الحجوزات الضريبية",
                "step_id": self.step_prepare.id,
                "counter": "شباك 7",
                "produces_stamp": "ختم الحجوزات الضريبية",
            }
        )
        case = self._make_case()
        self.assertEqual(len(case.check_ids), 1)
        walk = case.check_ids
        self.assertEqual(walk.counter, "شباك 7")
        self.assertFalse(case.ready_to_advance)
        walk.action_mark_done()
        self.assertTrue(walk.done)
        self.assertTrue(case.ready_to_advance)

    def test_a_required_capture_field_blocks_until_it_is_answered(self):
        self.env["legal.procedure.field"].create(
            {
                "label": "رقم القطعة",
                "code": "plot_number",
                "step_id": self.step_prepare.id,
                "required": True,
            }
        )
        case = self._make_case()
        self.assertFalse(case.ready_to_advance)
        case.capture_values = {"plot_number": "12/34"}
        self.assertTrue(case.ready_to_advance)

    def test_the_reference_index_finds_the_file_by_any_number(self):
        case = self._make_case()
        case.write(
            {
                "subject_ids": [
                    (0, 0, {"name_ar": "خبير", "document_number": "A9988776"})
                ]
            }
        )
        self.assertIn("A9988776", case.reference_index)
        found = self.env["legal.case"].name_search("A9988776")
        self.assertIn(case.id, [record[0] for record in found])

    def test_the_service_level_deadline_is_stored_and_the_verdict_is_live(self):
        self.env["legal.sla.rule"].create(
            {
                "procedure_type_id": self.procedure.id,
                "step_id": self.step_prepare.id,
                "target_days": 2,
                "warning_days": 1,
                "escalation_days": 1,
            }
        )
        case = self._make_case()
        self.assertTrue(case.sla_due_on)
        self.assertIn(case.sla_state, ("on_track", "warning"))
        # A stored deadline can be sorted and searched on; the verdict cannot be
        # stored because it changes at midnight with nobody writing to the row.
        self.assertIn(
            case, self.env["legal.case"].search([("sla_due_on", "!=", False)])
        )

    def test_the_deadline_scan_raises_one_escalation_and_no_more(self):
        self.env["legal.sla.rule"].create(
            {
                "procedure_type_id": self.procedure.id,
                "step_id": self.step_prepare.id,
                "target_days": 1,
                "escalation_days": 0,
            }
        )
        case = self._make_case()
        case._engine().write(
            {"sla_due_on": fields.Datetime.now() - relativedelta(days=3)}
        )
        raised = case._raise_due_escalations()
        self.assertTrue(raised)
        first = len(case.escalation_ids)
        # Idempotent by the unique index, not by a flag anybody has to remember.
        case._raise_due_escalations()
        self.assertEqual(len(case.escalation_ids), first)

    def test_escalations_close_when_the_file_moves_on(self):
        self.env["legal.sla.rule"].create(
            {
                "procedure_type_id": self.procedure.id,
                "step_id": self.step_prepare.id,
                "target_days": 1,
            }
        )
        case = self._make_case()
        case._engine().write(
            {"sla_due_on": fields.Datetime.now() - relativedelta(days=3)}
        )
        case._raise_due_escalations()
        self.assertTrue(case.escalation_ids.filtered("is_open"))
        case.action_advance()
        self.env["legal.case"]._cron_deadline_scan()
        self.assertFalse(case.escalation_ids.filtered("is_open"))

    def test_our_days_and_their_days_split_the_delay(self):
        case = self._make_case()
        case.action_advance()
        self.assertGreaterEqual(case.our_days, 0.0)
        self.assertGreaterEqual(case.their_days, 0.0)

    def test_a_file_cannot_carry_people_a_procedure_does_not_have(self):
        company_only = self.env["legal.procedure.type"].create(
            {
                "name": "إجراء عن الشركة",
                "code": "TEST-COMPANY-ONLY",
                "body_id": self.body.id,
                "subject_cardinality": "none",
            }
        )
        self.env["legal.procedure.step"].create(
            {
                "name": "خطوة",
                "procedure_type_id": company_only.id,
                "gov_body_id": self.body.id,
            }
        )
        case = self._make_case(procedure_type_id=company_only.id)
        with self.assertRaises(Exception):
            case.write({"subject_ids": [(0, 0, {"name_ar": "أحد"})]})

    def test_a_closed_file_can_be_re_opened_and_it_shows(self):
        case = self._make_case()
        case.action_advance()
        case.action_advance()
        self.assertTrue(case.is_closed)
        case.action_reopen()
        self.assertFalse(case.is_closed)
        self.assertEqual(case.round, 2)
        self.assertTrue(case.log_ids.filtered(lambda entry: entry.action == "reopen"))

    def test_every_service_level_filter_is_a_runnable_search(self):
        """The search method is what a board's filters run on, so every branch
        of it is executed here - a domain that raises only when somebody clicks
        it is a domain nobody has tested."""
        self._make_case()
        Case = self.env["legal.case"]
        for state in (
            "not_applicable",
            "on_track",
            "warning",
            "overdue",
            "escalated",
            "paused",
        ):
            Case.search([("sla_state", "=", state)])
            Case.search([("sla_state", "!=", state)])
        Case.search([("sla_state", "in", ["overdue", "escalated"])])

    def test_the_kanban_draws_every_step_including_the_empty_ones(self):
        """group_expand: the column a clerk is looking for is precisely the one
        with nothing in it yet."""
        self._make_case()
        result = self.env["legal.case"].with_context(
            default_procedure_type_id=self.procedure.id,
            read_group_expand=True,
        ).web_read_group(
            [("procedure_type_id", "=", self.procedure.id)],
            groupby=["step_id"],
            aggregates=["__count"],
        )
        drawn = {
            group["step_id"][0] for group in result["groups"] if group["step_id"]
        }
        self.assertEqual(drawn, set(self.procedure.step_ids.ids))

    def test_a_move_can_be_fired_from_the_embedded_list(self):
        """The button inside the file's own x2many, wired through the field context."""
        case = self._make_case()
        case.action_advance()
        transition = case.available_transition_ids[0]
        # Without the case in context the move refuses rather than guessing.
        with self.assertRaises(UserError):
            transition.action_fire_on_case()
        result = transition.with_context(
            legal_case_id=case.id
        ).action_fire_on_case()
        # This transition demands a reason, so the engine hands back the dialog
        # rather than moving the file behind the clerk's back.
        self.assertEqual(result["res_model"], "legal.case.return")
