"""The rendering context of the four printed artifacts.

Every helper the templates call lives here rather than in QWeb expressions,
for the same reason ``legal_dashboard`` keeps its logic in Python: the
templates are renderers, and what they render must be testable.

Three conventions are inherited from the official letter in
``legal_correspondence`` and honoured everywhere below:

* **Numerals follow the company.** ``legal.correspondence._localise_numerals``
  is private to that model and bound to its records, so the translation table
  is replicated here once and driven by the same company setting
  (``legal_numeral_system``) - a department whose outgoing book is in
  Arabic-Indic numerals must not have its cover sheets come out Western.

* **Dates are Baghdad dates.** The database stores UTC; the department stamps
  paper in Asia/Baghdad. Every datetime is converted before it is printed,
  and the Hijri date is appended exactly where the letter appends it - only
  when the company asked (``legal_show_hijri``), via the letter's own
  arithmetic-calendar helper.

* **Selection labels are printed in Arabic from closed maps.** The printed
  artifact is Arabic-only whatever the session language, so the labels do not
  ride the translation machinery - they are spelled out here, once, against
  the closed selection vocabularies the suite promises never to extend
  silently (see ``legal_procedure/models/legal_constants.py``).
"""

from datetime import date, datetime

import pytz

from odoo import fields, models
from odoo.tools.misc import formatLang

BAGHDAD = pytz.timezone("Asia/Baghdad")

#: Arabic-Indic digits, mirroring legal.correspondence._ARABIC_INDIC.
ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# ----------------------------------------------------------------------
# The closed vocabularies, in the Arabic the printed page uses.
# Keys are the stored selection values of the models named; they are the
# suite's frozen alphabets, verified against the model source at the time
# of writing and asserted by this module's tests.
# ----------------------------------------------------------------------

REGISTER_DIRECTION_AR = {
    "out": "الصادر",
    "in": "الوارد",
    "internal": "الداخلي",
}

SECRECY_AR = {
    "ordinary": "اعتيادي",
    "secret": "سري",
}

ENTRY_STATE_AR = {
    "draft": "مسودة",
    "registered": "مقيد",
    "void": "ملغى",
}

CASE_KIND_AR = {
    "internal": "على مكتبنا",
    "at_body": "لدى الجهة",
    "terminal": "منجزة",
}

CASE_OUTCOME_AR = {
    "none": "غير محسومة",
    "granted": "منحت الموافقة",
    "granted_conditional": "موافقة مشروطة",
    "returned_for_correction": "أعيدت للتصحيح",
    "rejected": "مرفوضة",
    "withdrawn": "مسحوبة",
    "expired": "انقضت المدة",
}

FEE_STATE_AR = {
    "due": "مستحق",
    "paid": "مدفوع",
    "waived": "معفى",
}

DOC_STATUS_AR = {
    "not_required": "غير مطلوبة",
    "missing": "غير مقدمة",
    "provided": "مقدمة",
    "under_review": "قيد التدقيق",
    "accepted": "مقبولة",
    "rejected": "مرفوضة",
    "expired": "منتهية الصلاحية",
}

LOG_ACTION_AR = {
    "open": "فتح الإضبارة",
    "advance": "تقدم",
    "transition": "انتقال",
    "return": "إعادة للتصحيح",
    "check": "تأشير كشف",
    "document": "مستند",
    "fee": "رسم",
    "letter": "كتاب",
    "contact": "تدوين اتصال",
    "escalate": "تصعيد",
    "close": "غلق",
    "reopen": "إعادة فتح",
}

LAWSUIT_STATE_AR = {
    "assessment": "قيد التقييم",
    "preparation": "قيد الإعداد",
    "filed": "مقيدة",
    "in_progress": "قيد النظر",
    "judgment": "صدور الحكم",
    "appeal": "في مرحلة الطعن",
    "enforcement": "قيد التنفيذ",
    "closed": "مغلقة",
}

CAPACITY_AR = {
    "plaintiff": "مدعي",
    "defendant": "مدعى عليه",
    "third_party": "شخص ثالث",
    "appellant": "طاعن / مستأنِف",
    "appellee": "مطعون ضده / مستأنَف عليه",
}

PARTY_ROLE_AR = {
    "opponent": "خصم",
    "co_party": "طرف معنا",
    "third_party": "شخص ثالث",
    "guarantor": "كفيل / ضامن",
    "other": "أخرى",
}

HEARING_PURPOSE_AR = {
    "pleading": "مرافعة",
    "witnesses": "استماع شهود",
    "expert": "خبرة",
    "verdict": "النطق بالحكم",
    "postponed": "تأجيل",
}

ATTENDANCE_AR = {
    "we_attended": "حضرنا",
    "opponent_absent": "غياب الخصم",
    "we_absent": "تغيبنا",
    "both_absent": "غياب الطرفين",
}

RULING_TYPE_AR = {
    "judgment": "حكم",
    "decision": "قرار",
}

FAVOUR_AR = {
    "favour": "لصالحنا",
    "partial": "جزئياً",
    "against": "ضدنا",
    "na": "غير محدد",
}

APPEAL_STATE_AR = {
    "na": "لا مدة طعن",
    "open": "المدة مفتوحة",
    "closing_soon": "توشك على الانتهاء",
    "closed": "انقضت المدة",
    "filed": "مطعون فيه",
}

REMEDY_AR = {
    "objection": "اعتراض على الحكم الغيابي",
    "appeal": "استئناف",
    "cassation": "تمييز",
    "labor": "طعن أمام محاكم العمل",
}

RISK_AR = {
    "low": "منخفضة",
    "medium": "متوسطة",
    "high": "عالية",
}

CONTRACT_STATE_AR = {
    "received": "مستلم",
    "legal_review": "قيد التدقيق القانوني",
    "negotiation": "قيد التفاوض",
    "internal_approval": "قيد الموافقة الداخلية",
    "counterparty_review": "لدى الطرف الآخر",
    "to_sign": "جاهز للتوقيع",
    "signed": "موقع",
    "active": "نافذ",
    "expired": "منتهي",
    "terminated": "مفسوخ",
    "closed": "مغلق",
}

SIGNATURE_STATUS_AR = {
    "unsigned": "غير موقع",
    "ours_signed": "موقع من طرفنا",
    "fully_signed": "موقع من الطرفين",
}

CONTRACT_ROLE_AR = {
    "counterparty": "الطرف الآخر",
    "guarantor": "ضامن",
    "beneficiary": "مستفيد",
    "witness": "شاهد",
}

OBLIGATION_STATUS_AR = {
    "pending": "قائم",
    "done": "منجز",
    "waived": "معفى",
}

OWED_BY_AR = {
    "ours": "علينا",
    "theirs": "على الطرف الآخر",
}

FREQUENCY_AR = {
    "one_off": "لمرة واحدة",
    "monthly": "شهري",
    "quarterly": "فصلي",
    "semiannual": "نصف سنوي",
    "annual": "سنوي",
}

MODIFICATION_STATE_AR = {
    "draft": "مسودة",
    "applied": "نافذ",
}


class LegalReportsRenderMixin:
    """The formatting helpers every print's rendering context carries.

    A plain Python mixin, not a registry model: the four report models below
    inherit it alongside ``models.AbstractModel``, and the helpers close over
    the company whose paper is being printed.
    """

    def _report_company(self, docs):
        companies = docs.mapped("company_id") if docs else self.env["res.company"]
        return companies[0] if len(companies) == 1 else self.env.company

    def _localise(self, company, text):
        if text is None or text is False:
            text = ""
        text = str(text)
        if company.legal_numeral_system == "arabic":
            return text.translate(ARABIC_INDIC)
        return text

    def _to_baghdad_date(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            return pytz.utc.localize(value).astimezone(BAGHDAD).date()
        return value

    def _fmt_date(self, company, value):
        """A Baghdad date the way the letter writes it, Hijri beside it only
        where the company asked."""
        day = self._to_baghdad_date(value)
        if not day:
            return ""
        text = day.strftime("%d/%m/%Y")
        if company.legal_show_hijri:
            text = "%s (%s هـ)" % (
                text,
                self.env["legal.correspondence"]._to_hijri(day),
            )
        return self._localise(company, text)

    def _fmt_datetime(self, company, value):
        if not value:
            return ""
        if isinstance(value, datetime):
            local = pytz.utc.localize(value).astimezone(BAGHDAD)
            return self._localise(company, local.strftime("%d/%m/%Y %H:%M"))
        return self._fmt_date(company, value)

    def _fmt_amount(self, company, amount, currency=None):
        """The figure with its currency, IQD by the currency's own rules."""
        currency = currency or company.currency_id
        return self._localise(
            company, formatLang(self.env, amount or 0.0, currency_obj=currency)
        )

    def _base_values(self, docids, doc_model, docs):
        company = self._report_company(docs)
        return {
            "doc_ids": docids,
            "doc_model": doc_model,
            "docs": docs,
            "company": company,
            "fmt": lambda text: self._localise(company, text),
            "fmt_date": lambda value: self._fmt_date(company, value),
            "fmt_datetime": lambda value: self._fmt_datetime(company, value),
            "fmt_amount": lambda amount, currency=None: self._fmt_amount(
                company, amount, currency
            ),
            "printed_on": self._fmt_date(company, datetime.now(BAGHDAD).date()),
        }


class ReportRegisterBook(LegalReportsRenderMixin, models.AbstractModel):
    _name = "report.legal_reports.report_register_book"
    _description = "Register Book Print"

    def _get_report_values(self, docids, data=None):
        registers = self.env["legal.register"].browse(docids)
        data = data or {}
        year = int(data.get("year") or datetime.now(BAGHDAD).year)
        # active_test off: the book never loses a row, so an archived entry
        # still prints on the page its number occupies.
        Entry = self.env["legal.correspondence"].with_context(active_test=False)
        entries, stats = {}, {}
        for register in registers:
            lines = Entry.search(
                [
                    ("register_id", "=", register.id),
                    ("state", "in", ("registered", "void")),
                    ("is_contact_note", "=", False),
                    ("our_date", ">=", date(year, 1, 1)),
                    ("our_date", "<=", date(year, 12, 31)),
                ],
                order="our_date asc, sequence_number asc, id asc",
            )
            entries[register.id] = lines
            stats[register.id] = {
                "total": len(lines),
                "void": len(lines.filtered(lambda entry: entry.state == "void")),
            }
        values = self._base_values(docids, "legal.register", registers)
        values.update(
            year=year,
            entries=entries,
            stats=stats,
            direction_labels=REGISTER_DIRECTION_AR,
            secrecy_labels=SECRECY_AR,
            entry_state_labels=ENTRY_STATE_AR,
        )
        return values


class ReportCaseCover(LegalReportsRenderMixin, models.AbstractModel):
    _name = "report.legal_reports.report_case_cover"
    _description = "Case File Cover Sheet Print"

    def _get_report_values(self, docids, data=None):
        cases = self.env["legal.case"].browse(docids)
        values = self._base_values(docids, "legal.case", cases)
        values.update(
            kind_labels=CASE_KIND_AR,
            outcome_labels=CASE_OUTCOME_AR,
            fee_state_labels=FEE_STATE_AR,
            doc_status_labels=DOC_STATUS_AR,
            log_action_labels=LOG_ACTION_AR,
        )
        return values


class ReportLawsuitStatus(LegalReportsRenderMixin, models.AbstractModel):
    _name = "report.legal_reports.report_lawsuit_status"
    _description = "Lawsuit Status Report Print"

    def _get_report_values(self, docids, data=None):
        lawsuits = self.env["legal.lawsuit"].browse(docids)
        values = self._base_values(docids, "legal.lawsuit", lawsuits)
        values.update(
            state_labels=LAWSUIT_STATE_AR,
            capacity_labels=CAPACITY_AR,
            role_labels=PARTY_ROLE_AR,
            purpose_labels=HEARING_PURPOSE_AR,
            attendance_labels=ATTENDANCE_AR,
            ruling_labels=RULING_TYPE_AR,
            favour_labels=FAVOUR_AR,
            appeal_labels=APPEAL_STATE_AR,
            remedy_labels=REMEDY_AR,
            risk_labels=RISK_AR,
        )
        return values


class ReportContractSummary(LegalReportsRenderMixin, models.AbstractModel):
    _name = "report.legal_reports.report_contract_summary"
    _description = "Contract Summary Print"

    def _get_report_values(self, docids, data=None):
        contracts = self.env["legal.contract"].browse(docids)
        # The value trail: original + the applied amendments = current. Summed
        # here rather than in QWeb so the arithmetic is one testable line.
        amendment_delta = {
            contract.id: sum(
                contract.modification_ids.filtered(
                    lambda modification: modification.state == "applied"
                ).mapped("value_change")
            )
            for contract in contracts
        }
        values = self._base_values(docids, "legal.contract", contracts)
        values.update(
            amendment_delta=amendment_delta,
            state_labels=CONTRACT_STATE_AR,
            signature_labels=SIGNATURE_STATUS_AR,
            role_labels=CONTRACT_ROLE_AR,
            status_labels=OBLIGATION_STATUS_AR,
            owed_labels=OWED_BY_AR,
            freq_labels=FREQUENCY_AR,
            mod_state_labels=MODIFICATION_STATE_AR,
            risk_labels=RISK_AR,
        )
        return values
