"""What the office payload must guarantee, whoever is reading it.

The screen has no business logic of its own - it renders what the server
composes - so these tests are the whole of its contract. Three properties
matter and each is tested as the user, never as the superuser:

* the payload is **complete** for every seat, so no template branch can meet
  an undefined;
* the queue is **differentiated** by role rather than filtered by number, which
  is the entire redesign in one assertion;
* the read-only seat is **read-only in the payload**, not merely in the markup.
"""

import re

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLegalOffice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.roles = {}
        groups = {
            "clerk": "legal_core.group_legal_clerk",
            "officer": "legal_core.group_legal_officer",
            "approver": "legal_core.group_legal_approver",
            "manager": "legal_core.group_legal_manager",
            "auditor": "legal_core.group_legal_auditor",
        }
        company = cls.env.company
        for key, xmlid in groups.items():
            # `group_ids`, not `groups_id`: Odoo 19 renamed the field, and the
            # rest of the suite's tests already use the new name.
            cls.roles[key] = cls.env["res.users"].create({
                "name": f"Office {key}",
                "login": f"office.{key}.test",
                "email": f"office.{key}@test.local",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id,
                                      cls.env.ref(xmlid).id])],
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
            })

    def _payload(self, key):
        return (self.env["legal.office"]
                .with_user(self.roles[key])
                .get_office_data())

    # ------------------------------------------------------------------
    def test_payload_is_complete_for_every_role(self):
        """Every seat gets every region, so no template branch meets undefined."""
        for key in self.roles:
            with self.subTest(role=key):
                data = self._payload(key)
                for section in ("rtl", "numerals", "role", "header", "signals",
                                "queue", "agenda", "secondary", "create", "degraded"):
                    self.assertIn(section, data, f"{section} missing for {key}")
                self.assertEqual(data["role"]["key"], key)
                self.assertTrue(data["header"]["title"])
                self.assertTrue(data["queue"]["title"])
                self.assertIn("title", data["queue"]["empty"])
                self.assertIn("hint", data["queue"]["empty"])
                self.assertIsInstance(data["signals"]["items"], list)
                self.assertLessEqual(len(data["signals"]["items"]), 5,
                                     "the attention strip must stay a strip")

    def test_the_screen_is_never_degraded_on_a_healthy_database(self):
        """A degraded note in normal operation means a collector is broken."""
        for key in self.roles:
            with self.subTest(role=key):
                self.assertEqual(self._payload(key)["degraded"], [])

    def test_queue_composition_differs_by_role(self):
        """The redesign, in one assertion.

        The five seats must not be the same list with different numbers on it.
        A clerk's queue is fed by the intake registers, an approver's by the
        decision states, and neither plan may be a copy of the other.
        """
        office = self.env["legal.office"]
        plans = {key: [spec["key"] for spec in office._queue_plan(key)]
                 for key in self.roles}
        self.assertNotEqual(plans["clerk"], plans["approver"])
        self.assertNotEqual(plans["officer"], plans["manager"])
        self.assertIn("correspondence", plans["clerk"])
        self.assertNotIn("correspondence", plans["approver"])
        self.assertIn("obligation", plans["manager"])

    def test_auditor_payload_carries_no_create_affordance(self):
        """Read-only is withheld by the server, not hidden by the template."""
        data = self._payload("auditor")
        self.assertTrue(data["role"]["read_only"])
        self.assertEqual(data["create"], [],
                         "an auditor payload that contains a create action has one")

    def test_writers_are_offered_something_to_create(self):
        data = self._payload("officer")
        self.assertFalse(data["role"]["read_only"])
        self.assertTrue(data["create"], "a writer with no create control cannot start work")
        for entry in data["create"]:
            self.assertTrue(entry["action"]["res_model"].startswith("legal."))

    def test_every_queue_row_carries_its_reason_and_a_way_in(self):
        """A row without a reason is a row the reader has to open to triage."""
        for key in self.roles:
            with self.subTest(role=key):
                for row in self._payload(key)["queue"]["rows"]:
                    self.assertTrue(row["open"], "a queue row must open its record")
                    self.assertEqual(row["open"]["res_model"], row["model"])
                    self.assertIn(row["bucket"], (0, 1, 2, 3, 4))
                    self.assertIsInstance(row["reference"], str)
                    self.assertTrue(row["subject"], "a row with no subject is unreadable")

    def test_queue_is_ordered_by_when_it_hurts(self):
        """Overdue outranks priority, and priority outranks the date."""
        rows = self._payload("manager")["queue"]["rows"]
        buckets = [row["bucket"] for row in rows]
        self.assertEqual(buckets, sorted(buckets),
                         "an overdue row must never sort below a future one")

    def test_signals_open_the_records_they_counted(self):
        """A count that leads somewhere else is a count nobody trusts."""
        for key in self.roles:
            with self.subTest(role=key):
                for item in self._payload(key)["signals"]["items"]:
                    if item["count"]:
                        self.assertTrue(item["action"])
                        self.assertEqual(item["action"]["type"], "ir.actions.act_window")
                    else:
                        self.assertFalse(item["action"],
                                         "an empty signal must not be clickable")

    def test_agenda_rows_project_real_records(self):
        data = self._payload("manager")
        for group in data["agenda"]["groups"]:
            self.assertTrue(group["rows"])
            for row in group["rows"]:
                self.assertTrue(row["kind_label"])
                if row["open"]:
                    self.assertEqual(row["open"]["type"], "ir.actions.act_window")

    def test_analytics_panels_all_state_a_question_and_drill_through(self):
        """No panel is decoration: each carries its question and its records."""
        data = (self.env["legal.analytics"]
                .with_user(self.roles["manager"])
                .get_analytics_data(6))
        self.assertEqual(data["degraded"], [])
        self.assertTrue(data["sections"])
        for section in data["sections"]:
            for panel in section["panels"]:
                with self.subTest(panel=panel["key"]):
                    self.assertTrue(panel["question"].endswith("?")
                                    or "؟" in panel["question"],
                                    "a panel must state a question")
                    self.assertTrue(panel["series"])
                    # Two series is the cap: the third status step is below
                    # 3:1 on a white surface and a stack would have put it there.
                    self.assertLessEqual(len(panel["series"]), 2)
                    for series in panel["series"]:
                        self.assertEqual(len(series["data"]), len(panel["labels"]))
                    if len(panel["series"]) > 1:
                        self.assertTrue(panel["legend"],
                                        "two series without a legend is colour-alone")

    def test_every_role_gets_a_secondary_panel(self):
        for key in self.roles:
            with self.subTest(role=key):
                self.assertTrue(self._payload(key)["secondary"]["tabs"],
                                f"{key} has no secondary panel at all")

    def test_department_wide_secondary_tabs_are_not_silently_empty(self):
        """A silently empty tab is how a broken query hides.

        ``_safe_read_group`` degrades to an empty list and only logs, so a
        group-by on a field that cannot be grouped - ``sla_state`` is computed
        on read, with a ``search`` method and no column - produces a tab that
        merely looks like a quiet week.

        Asserted only for the seats whose tabs are department-scoped. An
        officer's tabs are all *mine*-scoped, and a freshly created test user
        legitimately owns nothing, so an empty tab there is the truth rather
        than a defect - which is exactly the distinction this test has to make
        to be worth having.
        """
        for key in ("clerk", "manager", "auditor"):
            with self.subTest(role=key):
                tabs = self._payload(key)["secondary"]["tabs"]
                self.assertTrue(
                    any(tab["rows"] for tab in tabs),
                    f"every department-wide tab for {key} came back empty",
                )

    def test_every_sla_state_referenced_is_a_real_selection_value(self):
        """A domain naming a value the selection does not have matches nothing.

        It raises nothing either, which is what makes it worth a test: the
        manager's queue spent a draft filtering on "breached"/"late" and
        therefore never surfaced a single service-level breach.
        """
        import inspect

        from odoo.addons.legal_office.models import legal_office, legal_analytics

        valid = set(dict(
            self.env["legal.case"]._fields["sla_state"]
            ._description_selection(self.env)
        ))
        for module in (legal_office, legal_analytics):
            source = inspect.getsource(module)
            for match in re.finditer(r'"sla_state",\s*"in",\s*\(([^)]*)\)', source):
                for raw in match.group(1).split(","):
                    value = raw.strip().strip("\"'")
                    if value:
                        self.assertIn(value, valid,
                                      f"{value!r} is not an sla_state value")
