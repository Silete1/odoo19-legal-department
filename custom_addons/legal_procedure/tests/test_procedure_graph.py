from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import tagged

from .common import LegalProcedureCommon


@tagged("post_install", "-at_install")
class TestProcedureGraph(LegalProcedureCommon):
    """The configuration layer: what it accepts and, more importantly, what it refuses."""

    def test_linear_procedure_needs_no_transitions(self):
        """The claim the whole design rests on, asserted rather than assumed."""
        linear = self.env["legal.procedure.type"].create(
            {
                "name": "إجراء خطي",
                "code": "TEST-LINEAR",
                "body_id": self.body.id,
            }
        )
        Step = self.env["legal.procedure.step"]
        first = Step.create(
            {
                "name": "أولاً",
                "sequence": 10,
                "procedure_type_id": linear.id,
                "gov_body_id": self.body.id,
            }
        )
        second = Step.create(
            {
                "name": "ثانياً",
                "sequence": 20,
                "procedure_type_id": linear.id,
                "gov_body_id": self.body.id,
                "kind": "terminal",
                "outcome": "granted",
                "auto_next": False,
            }
        )
        self.assertFalse(linear.transition_ids)
        self.assertEqual(linear._next_step_after(first), second)
        linear.action_validate()

    def test_unreachable_step_is_reported(self):
        orphan = self.env["legal.procedure.step"].create(
            {
                "name": "خطوة يتيمة",
                "sequence": 40,
                "procedure_type_id": self.procedure.id,
                "gov_body_id": self.body.id,
                "auto_next": False,
            }
        )
        # Nothing advances into it and nothing leads out of it, so validation
        # should complain twice - once for each fault.
        problems = self.procedure._graph_problems()
        self.assertTrue(
            any(orphan.name in problem and "never be reached" in problem for problem in problems),
            problems,
        )
        with self.assertRaises(UserError):
            self.procedure.action_validate()

    def test_transition_into_another_procedure_is_refused(self):
        other = self.env["legal.procedure.type"].create(
            {"name": "إجراء آخر", "code": "TEST-OTHER", "body_id": self.body.id}
        )
        foreign_step = self.env["legal.procedure.step"].create(
            {
                "name": "خطوة غريبة",
                "procedure_type_id": other.id,
                "gov_body_id": self.body.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["legal.procedure.transition"].create(
                {
                    "name": "تحويل خاطئ",
                    "procedure_type_id": self.procedure.id,
                    "from_step_id": self.step_prepare.id,
                    "to_step_id": foreign_step.id,
                }
            )

    def test_always_false_condition_is_refused(self):
        """The fault with no symptom: a button that simply never appears."""
        with self.assertRaises(ValidationError):
            self.env["legal.procedure.transition"].create(
                {
                    "name": "زر لا يظهر أبداً",
                    "procedure_type_id": self.procedure.id,
                    "from_step_id": self.step_prepare.id,
                    "to_step_id": self.step_submit.id,
                    "condition_domain": "[(1, '=', 0)]",
                }
            )

    def test_nonsense_condition_is_refused(self):
        with self.assertRaises(ValidationError):
            self.env["legal.procedure.transition"].create(
                {
                    "name": "شرط غير صالح",
                    "procedure_type_id": self.procedure.id,
                    "from_step_id": self.step_prepare.id,
                    "to_step_id": self.step_submit.id,
                    "condition_domain": "[('no_such_field', '=', 1)]",
                }
            )

    def test_reserved_capture_field_codes_are_refused(self):
        """A department-wide fact may not be buried inside one step."""
        for code in ("fee", "amount", "receipt", "our_number", "reference"):
            with self.assertRaises(ValidationError, msg=code):
                self.env["legal.procedure.field"].create(
                    {
                        "label": "Something",
                        "code": code,
                        "step_id": self.step_prepare.id,
                    }
                )

    def test_ordinary_capture_field_code_is_accepted(self):
        capture = self.env["legal.procedure.field"].create(
            {
                "label": "رقم القطعة",
                "code": "plot_number",
                "step_id": self.step_prepare.id,
            }
        )
        self.assertEqual(capture.procedure_type_id, self.procedure)

    def test_outcome_only_on_a_terminal_step(self):
        with self.assertRaises(ValidationError):
            self.step_prepare.outcome = "granted"

    def test_step_without_a_body_is_refused(self):
        with self.assertRaises(Exception):
            self.env["legal.procedure.step"].create(
                {"name": "بلا جهة", "procedure_type_id": self.procedure.id}
            )

    def test_new_version_supersedes_rather_than_edits(self):
        original_version = self.procedure.version
        self.procedure.action_new_version()
        self.assertTrue(self.procedure.superseded_by_id)
        self.assertFalse(self.procedure.is_current)
        successor = self.procedure.superseded_by_id
        self.assertEqual(successor.supersedes_id, self.procedure)
        self.assertNotEqual(successor.version, original_version)
        # The copy carries the graph, so the new version is runnable on day one.
        self.assertEqual(len(successor.step_ids), len(self.procedure.step_ids))

    def test_a_requirement_condition_that_can_never_be_true_is_refused(self):
        with self.assertRaises(ValidationError):
            self.env["legal.doc.requirement"].create(
                {
                    "document_type_id": self.document_type.id,
                    "procedure_type_id": self.procedure.id,
                    "applicability_domain": "[(0, '=', 1)]",
                }
            )
