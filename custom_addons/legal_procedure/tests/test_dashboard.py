# Part of Legal Department. See LICENSE file for full copyright and licensing details.
"""The payload composer, tested as the roles that read it.

``legal.dashboard`` composes every figure the OWL screens draw, as the calling
user, through the ordinary ORM. These tests are the other half of the HOOT
suite's contract: the JS tests hand the components hand-written payloads, so
THIS file is the only place where the real payload shape, the full-domain tile
arithmetic, the role bands and the read-only auditor promise are enforced.

Every count asserted against the payload is recomputed with a direct
``search_count`` as the same user, because the whole point of the tile rework
is that a tile and the list behind it are one number computed over one domain.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from .common import LegalProcedureCommon


@tagged("post_install", "-at_install")
class TestLegalDashboard(LegalProcedureCommon):
    """One class, five readers, three public methods."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"].with_context(no_reset_password=True)

        def _user(login, groups):
            return Users.create({
                "name": login,
                "login": login,
                "email": f"{login}@example.com",
                "group_ids": [(6, 0, [cls.env.ref(group).id for group in groups])],
            })

        cls.user_clerk = _user("dash_clerk", ["legal_core.group_legal_clerk"])
        cls.user_officer = _user("dash_officer", ["legal_core.group_legal_officer"])
        cls.user_approver = _user("dash_approver", ["legal_core.group_legal_approver"])
        cls.user_manager = _user("dash_manager", ["legal_core.group_legal_manager"])
        cls.user_auditor = _user("dash_auditor", ["legal_core.group_legal_auditor"])

        # A closing move, so the approver's signature queue has a real
        # definition to compute from: submit -> done is terminal and ungated,
        # which per the engine's own authority rule is an approver's act.
        cls.transition_close = cls.env["legal.procedure.transition"].create({
            "name": "الموافقة والإغلاق",
            "procedure_type_id": cls.procedure.id,
            "from_step_id": cls.step_submit.id,
            "to_step_id": cls.step_done.id,
        })

    def _dash(self, user):
        return self.env["legal.dashboard"].with_user(user)

    @property
    def _all_users(self):
        return (self.user_clerk, self.user_officer, self.user_approver,
                self.user_manager, self.user_auditor)

    # ==================================================================
    # Smoke: every public method, every role, the promised shape
    # ==================================================================
    def test_mail_room_payload_shape_per_role(self):
        for user in self._all_users:
            data = self._dash(user).get_mail_room_data()
            self.assertLessEqual(
                {"rtl", "numerals", "title", "subtitle", "role", "hero",
                 "tiles", "columns", "degraded"},
                set(data),
                f"mail room payload misses keys for {user.login}",
            )
            self.assertEqual(
                [column["key"] for column in data["columns"]],
                ["incoming", "awaiting", "issue"],
            )
            self.assertEqual(
                {tile["key"] for tile in data["tiles"]},
                {"overdue", "at_body", "to_issue"},
            )
            for column in data["columns"]:
                self.assertLessEqual(
                    {"key", "title", "hint", "empty", "empty_hint", "count",
                     "rows", "action"},
                    set(column),
                )
            for key in ("is_manager", "is_approver", "is_officer",
                        "is_auditor", "can_write", "landing_band", "label"):
                self.assertIn(key, data["role"])

    def test_desk_payload_shape_per_role(self):
        for user in self._all_users:
            data = self._dash(user).get_desk_data()
            self.assertLessEqual(
                {"rtl", "numerals", "title", "role", "hero", "tiles",
                 "worklist", "bodies", "degraded", "attention"},
                set(data),
                f"desk payload misses keys for {user.login}",
            )
            self.assertIsInstance(data["attention"]["items"], list)
            for item in data["attention"]["items"]:
                self.assertLessEqual(
                    {"key", "label", "count", "count_label", "icon", "tone",
                     "action"},
                    set(item),
                )

    def test_body_desk_payload_shape(self):
        data = self._dash(self.user_officer).get_body_desk_data()
        self.assertIn("bodies", data)
        for body in data["bodies"]:
            self.assertLessEqual(
                {"id", "key", "label", "sections", "outstanding"}, set(body),
            )

    # ==================================================================
    # The role bands
    # ==================================================================
    def test_band_presence_follows_the_role(self):
        clerk = self._dash(self.user_clerk).get_desk_data()
        self.assertNotIn("manager", clerk)
        self.assertNotIn("approvals", clerk)
        self.assertNotIn("audit", clerk)

        approver = self._dash(self.user_approver).get_desk_data()
        self.assertIn("approvals", approver)
        self.assertNotIn("manager", approver)

        manager = self._dash(self.user_manager).get_desk_data()
        self.assertIn("manager", manager)
        # The manager holds every role at once, which is the reason My Desk
        # is one screen and not five.
        self.assertIn("approvals", manager)
        self.assertNotIn("audit", manager)

        auditor = self._dash(self.user_auditor).get_desk_data()
        self.assertIn("audit", auditor)
        self.assertNotIn("manager", auditor)
        self.assertNotIn("approvals", auditor)

    def test_manager_band_numbers_match_direct_counts(self):
        self._make_case(user_id=self.user_officer.id)
        self._make_case(user_id=self.user_officer.id)
        self._make_case(user_id=False)

        Case = self.env["legal.case"].with_user(self.user_manager)
        band = self._dash(self.user_manager).get_desk_data()["manager"]
        tiles = {tile["key"]: tile for tile in band["tiles"]}

        self.assertEqual(
            tiles["unassigned"]["value"],
            Case.search_count([("is_closed", "=", False), ("user_id", "=", False)]),
        )
        self.assertEqual(
            tiles["sla_breach"]["value"],
            Case.search_count([
                ("is_closed", "=", False),
                ("sla_state", "in", ["overdue", "escalated"]),
            ]),
        )
        self.assertIn("expiring", tiles)

        by_officer = {row["id"]: row["count"] for row in band["officers"]["rows"]}
        self.assertEqual(
            by_officer.get(self.user_officer.id, 0),
            Case.search_count([
                ("is_closed", "=", False),
                ("user_id", "=", self.user_officer.id),
            ]),
        )
        # Loads are read top down, so the heaviest desk comes first.
        counts = [row["count"] for row in band["officers"]["rows"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_approver_queue_counts_by_domain_not_by_page(self):
        case = self._make_case()
        case.action_advance()  # prepare -> submit, where the closing move sits
        self.assertEqual(case.step_id, self.step_submit)

        queue = self._dash(self.user_approver).get_desk_data()["approvals"]["queue"]
        self.assertTrue(queue, "the approver got no signature queue")
        self.assertGreaterEqual(queue["total"], 1)

        # The action's domain IS the definition of the queue: recount it as
        # the same user and the total must be the same number.
        Case = self.env["legal.case"].with_user(self.user_approver)
        self.assertEqual(queue["total"], Case.search_count(queue["action"]["domain"]))
        # And it is a domain over steps, never a list of the visible ids.
        leaf_fields = [
            leaf[0] for leaf in queue["action"]["domain"]
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3
        ]
        self.assertNotIn("id", leaf_fields)
        # Our closable file is inside that domain.
        self.assertIn(
            case.id,
            Case.search(queue["action"]["domain"]).ids,
        )

    # ==================================================================
    # Honest tiles: the whole queue, never the visible page
    # ==================================================================
    def test_desk_tiles_count_past_the_visible_page(self):
        from odoo.addons.legal_procedure.models.legal_dashboard import COLUMN_LIMIT
        for _index in range(COLUMN_LIMIT + 2):
            case = self._make_case(user_id=self.user_clerk.id)
            case.action_advance()  # -> submit, whose kind is at_body

        data = self._dash(self.user_clerk).get_desk_data()
        # The page is capped...
        self.assertEqual(len(data["worklist"]["files"]), COLUMN_LIMIT)

        # ...but the tile counts the whole queue, and its number is exactly
        # the count of the domain its drill-through opens.
        with_body = next(t for t in data["tiles"] if t["key"] == "with_body")
        Case = self.env["legal.case"].with_user(self.user_clerk)
        expected = Case.search_count([
            "|",
            ("user_id", "=", self.user_clerk.id),
            ("pending_group_id", "in", self.user_clerk.all_group_ids.ids),
            ("is_closed", "=", False),
            ("kind", "=", "at_body"),
        ])
        self.assertGreater(expected, COLUMN_LIMIT)
        self.assertEqual(with_body["value"], expected)
        self.assertEqual(
            with_body["value"],
            Case.search_count(with_body["action"]["domain"]),
        )
        # Drill-throughs are domains, never id-lists.
        leaf_fields = [
            leaf[0] for leaf in with_body["action"]["domain"]
            if isinstance(leaf, (list, tuple)) and len(leaf) == 3
        ]
        self.assertNotIn("id", leaf_fields)

    # ==================================================================
    # The read-only auditor
    # ==================================================================
    def test_auditor_payload_is_read_only(self):
        data = self._dash(self.user_auditor).get_desk_data()
        role = data["role"]
        self.assertTrue(role["is_auditor"])
        self.assertFalse(role["can_write"])
        self.assertEqual(role["landing_band"], "audit")

        mail = self._dash(self.user_auditor).get_mail_room_data()
        self.assertFalse(mail["role"]["can_write"])
        # Not one mutation affordance in any row of any column.
        for row in mail["columns"][0]["rows"]:
            self.assertFalse(row["link"], "auditor was offered attach-to-file")
            self.assertFalse(row["new_case"], "auditor was offered open-a-file")
        for row in mail["columns"][1]["rows"]:
            self.assertFalse(row["remind"], "auditor was offered the reminder")
            self.assertFalse(row["call"], "auditor was offered the call note")

        band = data["audit"]
        self.assertLessEqual({"title", "tiles", "log"}, set(band))
        for tile in band["tiles"]:
            if tile["action"]:
                # Reading is the auditor's job: a plain window action over a
                # domain, no context, so nothing seeds a quick-create.
                self.assertEqual(tile["action"]["type"], "ir.actions.act_window")
                self.assertNotIn("context", tile["action"])
        for row in band["log"]["rows"]:
            self.assertLessEqual({"id", "when", "description"}, set(row))

    def test_clerk_payload_offers_the_mutations(self):
        role = self._dash(self.user_clerk).get_desk_data()["role"]
        self.assertTrue(role["can_write"])
        self.assertFalse(role["is_auditor"])

    def test_auditor_role_label(self):
        role = self._dash(self.user_auditor)._role_brief()
        self.assertEqual(role["label"], "Auditor")

    # ==================================================================
    # The widget payloads on legal.case - the layer the HOOT mocks promise
    # ==================================================================
    def test_case_payload_fields_exist(self):
        """The HOOT suite declares these on a MOCK model; this is the only
        assertion that the real model carries them too."""
        Case = self.env["legal.case"]
        for name in ("progress_payload", "checklist_payload", "walk_payload"):
            self.assertIn(name, Case._fields, f"{name} missing on legal.case")

    def test_case_form_mounts_the_widget_layer(self):
        arch = self.env.ref("legal_procedure.view_legal_case_form").arch
        for widget in ("legal_phase_rail", "legal_checklist", "legal_counter_walk"):
            self.assertIn(
                f'widget="{widget}"', arch,
                f"the case form does not mount {widget}",
            )

    def test_progress_payload_walks_with_the_file(self):
        Phase = self.env["legal.procedure.phase"]
        prepare_phase = Phase.create({
            "name": "التحضير", "code": "T-PREP", "sequence": 1,
            "procedure_type_id": self.procedure.id,
        })
        body_phase = Phase.create({
            "name": "لدى الجهة", "code": "T-BODY", "sequence": 2,
            "procedure_type_id": self.procedure.id,
        })
        self.step_prepare.phase_id = prepare_phase
        self.step_submit.phase_id = body_phase
        self.step_done.phase_id = body_phase

        case = self._make_case(user_id=self.user_clerk.id)
        payload = case.with_user(self.user_clerk).progress_payload
        self.assertEqual(len(payload["phases"]), 2)
        self.assertEqual(payload["phases"][0]["status"], "current")
        self.assertEqual(payload["phases"][1]["status"], "todo")
        self.assertEqual(payload["counter_label"], "1 / 3")
        self.assertTrue(payload["mine"])
        self.assertFalse(payload["closed"])

        case.action_advance()
        payload = case.with_user(self.user_clerk).progress_payload
        self.assertEqual(payload["phases"][0]["status"], "done")
        self.assertEqual(payload["phases"][1]["status"], "current")
        self.assertEqual(payload["counter_label"], "2 / 3")
        self.assertGreater(payload["percent"], 0)

    def test_checklist_payload_counts_match_the_lines(self):
        self.env["legal.doc.requirement"].create({
            "document_type_id": self.document_type.id,
            "procedure_type_id": self.procedure.id,
            "is_required": True,
        })
        case = self._make_case()
        payload = case.checklist_payload
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["done"], 0)
        self.assertEqual(payload["meter_label"], "0 / 1")
        rows = [row for section in payload["sections"] for row in section["rows"]]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "not_submitted")
        self.assertTrue(rows[0]["required"])

        document = self._register_document(
            expiry=fields.Date.context_today(case) + relativedelta(years=1),
        )
        case.document_ids.write({
            "company_document_id": document.id, "accepted": True,
        })
        payload = case.checklist_payload
        self.assertEqual(payload["done"], 1)
        self.assertEqual(payload["percent"], 100)
        rows = [row for section in payload["sections"] for row in section["rows"]]
        self.assertTrue(rows[0]["from_entity_register"])

    def test_walk_payload_round_trip(self):
        self.env["legal.procedure.step.check"].create({
            "name": "ختم الشعبة",
            "step_id": self.step_prepare.id,
            "counter": "شباك ٣",
        })
        case = self._make_case()
        payload = case.walk_payload
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["done"], 0)
        self.assertFalse(payload["counters"][0]["stamp_obtained"])
        check = case.check_ids
        self.assertEqual(len(check), 1)

        # The widget's save: the payload it was given, plus the ticks. The
        # inverse must land them on the check line as the writing user.
        case.with_user(self.user_clerk).write({
            "walk_payload": {
                **payload,
                "ticks": [{"id": check.id, "stamp_obtained": True}],
            },
        })
        self.assertTrue(check.done)
        self.assertEqual(check.done_by_id, self.user_clerk)

        payload = case.walk_payload
        self.assertEqual(payload["done"], 1)
        self.assertTrue(payload["counters"][0]["stamp_obtained"])

    def test_auditor_cannot_tick_the_walk(self):
        """The widget decides nothing: the ACL on the lines refuses the
        auditor's tick exactly as it would refuse it from the list view."""
        self.env["legal.procedure.step.check"].create({
            "name": "ختم",
            "step_id": self.step_prepare.id,
        })
        case = self._make_case()
        payload = case.walk_payload
        check = case.check_ids
        with self.assertRaises(AccessError):
            case.with_user(self.user_auditor).write({
                "walk_payload": {
                    **payload,
                    "ticks": [{"id": check.id, "stamp_obtained": True}],
                },
            })
