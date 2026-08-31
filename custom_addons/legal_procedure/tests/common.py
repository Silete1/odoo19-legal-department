from odoo import fields
from odoo.tests.common import TransactionCase


class LegalProcedureCommon(TransactionCase):
    """A small but honest procedure to test against.

    Deliberately a *linear* one with a single return transition, because that is
    the shape almost every real Iraqi procedure has: a straight walk that is
    occasionally sent back. If the engine is right about that shape it is right
    about most of the product.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.jurisdiction = cls.env["legal.jurisdiction"].create(
            {"name": "Federal Iraq", "code": "TEST-IQ-FED"}
        )
        cls.body_type = cls.env["legal.gov.body.type"].create(
            {"name": "Directorate", "code": "TEST-DIR"}
        )
        cls.body = cls.env["legal.gov.body"].create(
            {
                "name": "دائرة تسجيل الشركات",
                "code": "TEST-MOT-REG",
                "body_type_id": cls.body_type.id,
                "jurisdiction_id": cls.jurisdiction.id,
            }
        )
        cls.other_body = cls.env["legal.gov.body"].create(
            {
                "name": "الهيئة العامة للضرائب",
                "code": "TEST-GCT",
                "body_type_id": cls.body_type.id,
                "jurisdiction_id": cls.jurisdiction.id,
            }
        )
        cls.entity = cls.env["legal.entity"].create(
            {
                "name": "شركة الاختبار المحدودة",
                "name_en": "Test Company Ltd",
                "jurisdiction_id": cls.jurisdiction.id,
                "company_id": cls.company.id,
            }
        )
        cls.document_kind = cls.env["legal.document.kind"].create(
            {"name": "Clearances", "code": "TEST-CLEAR"}
        )
        cls.document_type = cls.env["legal.document.type"].create(
            {
                "name": "براءة ذمة",
                "code": "TEST-CLEARANCE",
                "kind_id": cls.document_kind.id,
                "issuing_body_id": cls.other_body.id,
                "validity_model": "expiry",
                "validity_value": 1,
                "validity_uom": "year",
            }
        )
        cls.result_type = cls.env["legal.document.type"].create(
            {
                "name": "إجازة تأسيس",
                "code": "TEST-INCORP-CERT",
                "kind_id": cls.document_kind.id,
                "issuing_body_id": cls.body.id,
                "validity_model": "none",
            }
        )

        cls.procedure = cls.env["legal.procedure.type"].create(
            {
                "name": "تأسيس شركة محدودة",
                "code": "TEST-INCORP",
                "body_id": cls.body.id,
                "jurisdiction_id": cls.jurisdiction.id,
                "version": "1.0",
                "result_document_type_id": cls.result_type.id,
                "has_result_document": "required",
                "subject_cardinality": "many",
                "has_subjects": "optional",
            }
        )
        Step = cls.env["legal.procedure.step"]
        cls.step_prepare = Step.create(
            {
                "name": "تحضير الملف",
                "code": "PREP",
                "sequence": 10,
                "procedure_type_id": cls.procedure.id,
                "gov_body_id": cls.body.id,
                "kind": "internal",
                "target_days": 2,
            }
        )
        cls.step_submit = Step.create(
            {
                "name": "التقديم إلى الشعبة",
                "code": "SUBMIT",
                "sequence": 20,
                "procedure_type_id": cls.procedure.id,
                "gov_body_id": cls.body.id,
                "kind": "at_body",
                "target_days": 5,
            }
        )
        cls.step_done = Step.create(
            {
                "name": "الإنجاز",
                "code": "DONE",
                "sequence": 30,
                "procedure_type_id": cls.procedure.id,
                "gov_body_id": cls.body.id,
                "kind": "terminal",
                "outcome": "granted",
                "auto_next": False,
            }
        )
        cls.transition_return = cls.env["legal.procedure.transition"].create(
            {
                "name": "إعادة للتصحيح",
                "procedure_type_id": cls.procedure.id,
                "from_step_id": cls.step_submit.id,
                "to_step_id": cls.step_prepare.id,
                "is_return": True,
                "require_reason": True,
            }
        )

    @classmethod
    def _make_case(cls, **values):
        base = {
            "procedure_type_id": cls.procedure.id,
            "entity_id": cls.entity.id,
            "company_id": cls.company.id,
            "subject": "طلب تأسيس",
        }
        base.update(values)
        return cls.env["legal.case"].create(base)

    @classmethod
    def _register_document(cls, document_type=None, expiry=None):
        return cls.env["legal.document"].create(
            {
                "name": "Register entry",
                "document_type_id": (document_type or cls.document_type).id,
                "entity_id": cls.entity.id,
                "company_id": cls.company.id,
                "issue_date": fields.Date.context_today(cls.env["legal.document"]),
                "expiry_date": expiry,
            }
        )
