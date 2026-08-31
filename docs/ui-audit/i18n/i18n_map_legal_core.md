# i18n seed map - legal_core

Each row: the exact new English msgid, the Arabic wording that was stripped from the
source (cleaned; for strings that were English sentences with embedded Arabic terms,
the Arabic column carries the stripped term(s) as terminology seed). Files are
relative to `custom_addons/legal_core/`. Multi-line msgids show `\n` for the newline.

| English msgid | Arabic seed | File |
|---|---|---|
| The Chamber's class or the Ministry of Planning's grade. A tender may demand a specific class, not merely a valid card. | الصنف (غرفة التجارة) / الدرجة (وزارة التخطيط) | models/legal_document.py |
| Certified Copy | مصدقة | models/legal_document_type.py |
| A photocopy stamped as a true copy by the issuing body or a consulate. | طبق الأصل | models/legal_document_type.py |
| Notarised | الكاتب العدل | models/legal_document_type.py |
| Consular Legalisation | التصديقات | models/legal_document_type.py |
| Iraq has no apostille. A foreign document must be certified by the issuing country's foreign ministry, then by the Iraqi mission there, then by the Legalisation Department at the Iraqi Ministry of Foreign Affairs (Law 52 of 1970). | دائرة التصديقات (وزارة الخارجية العراقية) | models/legal_document_type.py |
| A simple company must have its formation contract notarised at the Notary Public. | الشركة البسيطة يصدق عقد تأسيسها لدى الكاتب العدل | models/legal_entity.py |
| The registered activity as recorded with the Registrar. | النشاط المسجل | models/legal_entity.py |
| The section inside the body that holds this file, e.g. the Companies Section or the Large Taxpayers Section. Clerks are routed by section, not by body. | قسم الشركات، قسم كبار مكلفي الدخل | models/legal_entity.py |
| The date the artefact ceases to be in force. Empty means it does not expire. | نافذة | models/legal_expiry_mixin.py |
| Section head, deputy, enquiries clerk. | مدير القسم، معاون، موظف الاستعلامات | models/legal_gov_body.py |
| What a clerk actually calls it: the Taxes, the Residency, the Chamber. | الضرائب، الإقامة، الغرفة | models/legal_gov_body.py |
| Printed verbatim as the addressee block, for example:\nMinistry of Oil / Studies, Planning and Follow-up Directorate / Entry Visas Section | الجهة الموجه إليها — مثال: وزارة النفط / دائرة الدراسات والتخطيط والمتابعة / قسم سمات الدخول | models/legal_gov_body.py |
| For example: 08:30 - 14:15, closed Friday and Saturday | 08:30 - 14:15، عطلة الجمعة والسبت | models/legal_gov_body.py |
| Managing Director, Director General, Deputy Director General - printed under the signature. | المدير المفوض، المدير العام، معاون المدير العام | models/legal_signatory.py |
| Official Seal | الختم | models/legal_signatory.py |
| The minutes of meeting or Registrar ratification that appointed them. | محضر | models/legal_signatory.py |
| The department, e.g. the Legal Department. | القسم القانوني | models/res_company.py |
| Adds the Hijri date beside the Gregorian one on letters. The research found no rule requiring dual dating on Iraqi correspondence - the Registrar's own bulletin and the Iraqi Official Gazette use Gregorian alone - so this is off by default. | الوقائع العراقية | models/res_company.py |
| Reads everything and changes nothing. For the internal auditor, the Federal Board of Supreme Audit, or an external reviewer. | ديوان الرقابة المالية | security/legal_core_security.xml |
| Legal Department - Core | الدائرة القانونية - الأساس | __manifest__.py |
| Chamber of Commerce Identity Card | هوية غرفة التجارة | views/legal_document_type_views.xml |
| A document that goes stale rather than expiring: a paid electricity bill, a bank confirmation letter, a supporting letter. Council of Ministers directive 16180 of 2024 made the latest paid electricity and water bills mandatory attachments at the Registrar, and the Ministry of Planning refuses any supporting letter issued more than a year before the application. | تأييد (كتاب تأييد مصرفي) | views/legal_document_type_views.xml |
| A tender does not merely demand a valid Chamber identity; it demands a Chamber of Commerce identity, grade Excellent, in force. Grades make that checkable. | هوية غرفة تجارة صنف (ممتاز) نافذة | views/legal_document_type_views.xml |
| Baghdad Chamber of Commerce Identity 2026 | هوية غرفة تجارة بغداد 2026 | views/legal_document_views.xml |
| ... Company Ltd. | شركة ... المحدودة | views/legal_entity_views.xml |
| A branch of a foreign company files audited accounts and an activity report with the Registrar within eight months of the year end, and notifies a change of branch manager within sixty working days (Foreign Companies Branches Regulation 2 of 2017, Articles 7 and 8). | نظام فروع الشركات الأجنبية رقم 2 لسنة 2017، المادتان 7 و 8 | views/legal_entity_views.xml |
| General Commission for Taxes | الهيئة العامة للضرائب | views/legal_gov_body_views.xml |
| Taxes | الضرائب | views/legal_gov_body_views.xml |
| 08:30 - 14:15, closed Friday and Saturday | 08:30 - 14:15، عطلة الجمعة والسبت | views/legal_gov_body_views.xml |
| Ministry of Finance\nGeneral Commission for Taxes\nCompanies Section | وزارة المالية\nالهيئة العامة للضرائب\nقسم الشركات | views/legal_gov_body_views.xml |
| Managing Director | المدير المفوض | views/legal_signatory_views.xml |
| An Iraqi official letter is constituted by the letterhead, the signature and the seal printed together. A letter without the seal is a draft, and the counter will say so. | الختم (كتاب رسمي بلا ختم مسودة) | views/legal_signatory_views.xml |
| Official Seal | الختم | views/legal_signatory_views.xml |

Kept in Arabic deliberately (domain content, NOT to be translated away in source):
- `data/legal_document_kind_data.xml`, `data/legal_gov_body_type_data.xml`,
  `data/legal_jurisdiction_data.xml` - data record values (`translate=True` fields;
  Arabic is the stored base value).
- `models/res_company.py` `legal_letterhead_line1` default `جمهورية العراق` and
  `models/legal_gov_body.py` `salutation` default `السيد المدير العام المحترم` -
  field DEFAULT VALUES printed on official letters, not labels; defaults are data,
  not translatable source strings.
- Arabic inside Python docstrings and XML comments (explicitly exempt).
