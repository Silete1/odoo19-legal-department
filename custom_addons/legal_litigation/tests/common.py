from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class LegalLitigationCommon(TransactionCase):
    """A court, a valid litigation deed, and one user per rung of the ladder.

    Deliberately builds its own users rather than leaning on the demo pack, so
    the separation-of-duties and read-only assertions hold whether or not
    ``legal_iq_demo`` happens to be installed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.clerk = cls._make_user("lit_clerk", "legal_core.group_legal_clerk")
        cls.approver = cls._make_user("lit_approver", "legal_core.group_legal_approver")
        cls.manager = cls._make_user("lit_manager", "legal_core.group_legal_manager")
        cls.auditor = cls._make_user("lit_auditor", "legal_core.group_legal_auditor")

        cls.jurisdiction = cls.env["legal.jurisdiction"].create(
            {"name": "Test Baghdad", "code": "TEST-LIT-BGD"}
        )
        cls.entity = cls.env["legal.entity"].create(
            {
                "name": "شركة الاختبار للدعاوى",
                "name_en": "Litigation Test Co",
                "jurisdiction_id": cls.jurisdiction.id,
                "company_id": cls.company.id,
            }
        )
        cls.court = cls.env["legal.court"].create(
            {
                "name": "محكمة بداءة الاختبار",
                "code": "TEST-BID",
                "degree": "first_instance",
                "governorate_id": cls.jurisdiction.id,
            }
        )
        cls.appeal_court = cls.env["legal.court"].create(
            {
                "name": "محكمة استئناف الاختبار",
                "code": "TEST-APP",
                "degree": "appeal",
                "governorate_id": cls.jurisdiction.id,
            }
        )
        cls.appeal_rule = cls.env["legal.appeal.rule"].create(
            {
                "name": "Test appeal of a judgment",
                "remedy": "appeal",
                "ruling_type": "judgment",
                "days": 15,
                "non_extendable": True,
                "verification_status": "verified",
            }
        )
        cls.advocate_partner = cls.env["res.partner"].create(
            {"name": "المحامي الاختبار"}
        )
        cls.poa = cls.env["legal.poa"].create(
            {
                "name": "وكالة بالمرافعة للاختبار",
                "entity_id": cls.entity.id,
                "agent_partner_id": cls.advocate_partner.id,
                "agent_user_id": cls.clerk.id,
                "scope": "litigation",
                "state": "active",
                "issue_date": fields.Date.context_today(cls.env["legal.poa"]),
                "company_id": cls.company.id,
            }
        )

    @classmethod
    def _make_user(cls, login, group_xmlid):
        group = cls.env.ref(group_xmlid)
        return cls.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "email": "%s@test.local" % login,
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id, group.id])],
                "company_id": cls.company.id,
                "company_ids": [(6, 0, [cls.company.id])],
            }
        )

    @classmethod
    def _make_lawsuit(cls, **values):
        base = {
            "title": "دعوى اختبار",
            "our_capacity": "plaintiff",
            "entity_id": cls.entity.id,
            "company_id": cls.company.id,
            "lawyer_id": cls.clerk.id,
        }
        base.update(values)
        return cls.env["legal.lawsuit"].create(base)
